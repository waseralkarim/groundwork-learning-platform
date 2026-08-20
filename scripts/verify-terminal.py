#!/usr/bin/env python3
"""Prove the lab terminal actually carries bytes, both ways.

The failure this exists to catch: the WebSocket upgrades, the broker logs an
attach, the container is running, every health check is green — and not a single
byte moves. Nothing in the system reports an error, and the learner sees a blank
rectangle. That is exactly what happened with Docker's `/attach/ws` endpoint,
which completes its handshake and then does nothing.

So this does not check that the socket opened. It types a command and asserts
the shell's answer comes back.

    python scripts/verify-terminal.py
    python scripts/verify-terminal.py --topic processes --lab make-a-zombie
"""

from __future__ import annotations

import argparse
import base64
import http.cookiejar
import json
import os
import socket
import struct
import sys
import urllib.error
import urllib.request
import uuid

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"
MARKER = "GROUNDWORK-TERMINAL-OK"


def frame(payload: bytes) -> bytes:
    """A masked client text frame. Client frames must be masked."""
    mask = os.urandom(4)
    masked = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
    if len(payload) < 126:
        header = bytes([0x81, 0x80 | len(payload)])
    else:
        header = bytes([0x81, 0xFE]) + struct.pack(">H", len(payload))
    return header + mask + masked


def read_frame(sock: socket.socket) -> bytes:
    head = sock.recv(2)
    if len(head) < 2:
        return b""
    length = head[1] & 0x7F
    if length == 126:
        length = struct.unpack(">H", sock.recv(2))[0]
    elif length == 127:
        length = struct.unpack(">Q", sock.recv(8))[0]
    out = b""
    while len(out) < length:
        chunk = sock.recv(length - len(out))
        if not chunk:
            break
        out += chunk
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the lab terminal end to end")
    parser.add_argument("--base", default="http://localhost:8080")
    parser.add_argument("--topic", default="processes")
    parser.add_argument("--lab", default="make-a-zombie")
    args = parser.parse_args()

    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def call(method: str, path: str, body: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(args.base + path, data=data, method=method)
        request.add_header("content-type", "application/json")
        request.add_header("origin", args.base)
        try:
            with opener.open(request, timeout=30) as response:
                raw = response.read().decode()
                return response.status, (json.loads(raw) if raw.strip() else None)
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode()[:200]
        except urllib.error.URLError as error:
            print(f"{RED}Cannot reach {args.base}: {error.reason}{RESET}", file=sys.stderr)
            sys.exit(2)

    print("Terminal check")

    email = f"terminal-{uuid.uuid4().hex[:10]}@example.com"
    status, _ = call(
        "POST",
        "/api/v1/auth/register",
        {"email": email, "password": "terminal-check-passphrase", "display_name": "Terminal check"},
    )
    if status != 201:
        print(f"  {RED}FAIL{RESET}  could not create an account ({status})")
        return 1

    status, session = call(
        "POST", "/labs/sessions", {"topic_slug": args.topic, "lab_slug": args.lab}
    )
    if status != 201 or not isinstance(session, dict):
        print(f"  {RED}FAIL{RESET}  could not start a lab session ({status}: {session})")
        print(f"  {DIM}is the labs profile running? task labs:up{RESET}")
        return 1
    session_id = session["session_id"]
    print(f"  {GREEN} ok {RESET}  lab session started")

    host = args.base.split("://", 1)[1]
    hostname, _, port = host.partition(":")
    cookies = "; ".join(f"{c.name}={c.value}" for c in jar)

    sock = socket.create_connection((hostname, int(port or 80)), timeout=20)
    sock.sendall(
        (
            f"GET /labs/sessions/{session_id}/terminal HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {base64.b64encode(os.urandom(16)).decode()}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            f"Cookie: {cookies}\r\n\r\n"
        ).encode()
    )
    handshake = sock.recv(4096).decode(errors="replace").split("\r\n")[0]
    if "101" not in handshake:
        print(f"  {RED}FAIL{RESET}  websocket did not upgrade: {handshake}")
        call("DELETE", f"/labs/sessions/{session_id}")
        return 1
    print(f"  {GREEN} ok {RESET}  websocket upgraded")

    # A learner opens the lab and looks at the screen before touching the
    # keyboard. If no prompt is there they conclude it is broken, so this is a
    # real check rather than a cosmetic one.
    sock.settimeout(10)
    opening = ""
    try:
        for _ in range(3):
            opening += read_frame(sock).decode("utf-8", "replace")
            if "$" in opening:
                break
    except TimeoutError:
        pass

    if "$" in opening:
        print(f"  {GREEN} ok {RESET}  a prompt is visible before the learner types")
    else:
        print(f"  {RED}FAIL{RESET}  no prompt on open — the learner sees a blank rectangle")

    # The part that actually matters. An upgraded socket that carries nothing
    # looks identical to a working one from every other vantage point.
    sock.sendall(frame(f"echo {MARKER}\n".encode()))

    seen = ""
    try:
        for _ in range(8):
            chunk = read_frame(sock)
            if not chunk:
                break
            seen += chunk.decode("utf-8", "replace")
            # The echo of the typed command contains the marker too, so wait for
            # it to appear a second time — that occurrence is the shell's output.
            if seen.count(MARKER) >= 2:
                break
    except TimeoutError:
        pass
    finally:
        sock.close()
        call("DELETE", f"/labs/sessions/{session_id}")

    if seen.count(MARKER) >= 2 and "$" in opening:
        print(f"  {GREEN} ok {RESET}  the shell received a command and answered")
        print()
        print(f"{GREEN}Terminal check passed.{RESET}")
        return 0

    if MARKER in seen:
        print(f"  {RED}FAIL{RESET}  keystrokes reach the shell but its output does not come back")
    elif seen.strip():
        print(f"  {RED}FAIL{RESET}  the terminal sent something unexpected: {seen[:120]!r}")
    else:
        print(f"  {RED}FAIL{RESET}  the socket upgraded but no bytes moved in either direction")
    print()
    print(f"{RED}Terminal check FAILED.{RESET}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
