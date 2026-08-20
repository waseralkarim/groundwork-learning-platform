#!/usr/bin/env python3
"""Walk every lab the way a learner would, and assert each step verifies.

The problem this solves: a lab can pass every automated check and still be
broken. In the first eight labs, three were — a path that did not exist, a
demonstration that demonstrated nothing, and an instruction that needed a
capability the sandbox drops. All three passed their checks. All three were
found by hand.

So this runs each step's `walkthrough` — what a learner following the
instruction would actually type — inside a real lab container, then asserts the
step's own checks pass. If the instructions and the checks disagree, this fails.

    python scripts/walk-labs.py                 # every lab
    python scripts/walk-labs.py --topic processes
    python scripts/walk-labs.py --lab make-a-zombie

Requires the labs profile running with a real runtime:

    task labs:up

Note that this reaches the container runtime directly to run walkthroughs. That
is a test-harness privilege, not a platform one — the broker deliberately has no
"run arbitrary command" endpoint, and this script is not part of the running
system.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE = "http://localhost:8080"
PASSWORD = "walk-labs-harness-passphrase"

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def ok(message: str) -> None:
    print(f"  {GREEN} ok {RESET}  {message}")


def bad(message: str) -> None:
    print(f"  {RED}FAIL{RESET}  {message}")


def note(message: str) -> None:
    print(f"  {DIM}{message}{RESET}")


class Client:
    """Minimal cookie-aware HTTP client. No dependencies on purpose."""

    def __init__(self, base: str) -> None:
        self.base = base
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )

    def request(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict | None]:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(f"{self.base}{path}", data=data, method=method)
        request.add_header("content-type", "application/json")
        request.add_header("origin", self.base)
        try:
            with self.opener.open(request, timeout=30) as response:
                raw = response.read().decode()
                return response.status, (json.loads(raw) if raw.strip() else None)
        except urllib.error.HTTPError as error:
            raw = error.read().decode()
            try:
                return error.code, json.loads(raw) if raw.strip() else None
            except json.JSONDecodeError:
                return error.code, {"detail": raw[:200]}
        except urllib.error.URLError as error:
            print(f"{RED}Cannot reach {self.base}: {error.reason}{RESET}", file=sys.stderr)
            sys.exit(2)


def docker(*args: str) -> subprocess.CompletedProcess:
    # encoding is explicit because `text=True` alone decodes with the platform
    # default — cp1252 on Windows — and a lab that prints a hex dump or a £ sign
    # then raises UnicodeDecodeError inside a reader thread, leaving stdout as
    # None and crashing the harness somewhere unrelated. Everything here is
    # UTF-8; `errors="replace"` keeps binary lab output from being fatal.
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )


def fetch_internal(path: str) -> dict | None:
    """Read an internal endpoint from inside the app network.

    The edge deliberately 404s /api/v1/internal/* so a browser can never reach a
    verify spec. Rather than weaken that rule for a test harness, this asks the
    API container to fetch it from itself — which also proves the boundary is
    where it should be.
    """
    reader = (
        "import urllib.request,sys;"
        f"sys.stdout.write(urllib.request.urlopen('http://127.0.0.1:8000/v1{path}',"
        "timeout=15).read().decode())"
    )
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "api", "python", "-c", reader],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if result.returncode != 0 or not result.stdout:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def container_for(session_id: str) -> str | None:
    result = docker("ps", "--filter", f"label=groundwork.session={session_id}", "-q")
    return result.stdout.strip().splitlines()[0] if result.stdout.strip() else None


def run_walkthrough(container: str, script: str) -> tuple[bool, str]:
    """Run a step's walkthrough inside the lab, as the learner's user.

    The script must reach bash with LF endings. Two things would otherwise put a
    CR in it: content authored on Windows, and `text=True`, which translates \\n
    to os.linesep on the way into stdin. Both produce the same baffling failure —
    `$'true\\r': command not found` — so this normalises and then sends bytes.
    """
    clean = script.replace("\r\n", "\n").replace("\r", "\n")

    # A learner's interactive shell records what they typed; `docker exec` runs a
    # non-interactive shell, which keeps no history at all. `command_ran` checks
    # read that history, so the walkthrough writes itself there first — otherwise
    # the harness would fail steps the learner would pass.
    payload = (
        f"cat >> ~/.bash_history <<'GROUNDWORK_WALK_HISTORY'\n"
        f"{clean}\n"
        f"GROUNDWORK_WALK_HISTORY\n"
        f"{clean}"
    ).encode()
    result = subprocess.run(
        ["docker", "exec", "-i", "-u", "10001:10001", container, "bash", "-s"],
        input=payload,
        capture_output=True,
        timeout=180,
    )
    output = (result.stderr or result.stdout).decode(errors="replace")
    return result.returncode == 0, output[-400:]


def walk_lab(client: Client, topic: str, lab: dict, spec: dict) -> bool:
    slug = lab["slug"]
    print(f"\n{lab['title']}  {DIM}({topic}/{slug}){RESET}")

    steps = spec.get("steps", [])
    walkable = [s for s in steps if s.get("walkthrough") and s.get("verify")]
    if not walkable:
        note("no walkable steps — every step needs both a walkthrough and checks")
        return True

    status, session = client.request(
        "POST", "/labs/sessions", {"topic_slug": topic, "lab_slug": slug}
    )
    if status != 201 or not session:
        bad(f"could not start a session ({status}: {(session or {}).get('detail', '')})")
        return False

    session_id = session["session_id"]
    time.sleep(2)
    container = container_for(session_id)
    if not container:
        bad("session started but no container appeared")
        client.request("DELETE", f"/labs/sessions/{session_id}")
        return False

    passed = True
    try:
        for step in steps:
            step_id = step["id"]
            script = step.get("walkthrough")

            if not script:
                if step.get("verify"):
                    bad(f"{step_id}: has checks but no walkthrough — untestable")
                    passed = False
                continue

            ran, output = run_walkthrough(container, script)
            if not ran:
                note(f"{step_id}: walkthrough exited non-zero — {output.strip()[:120]}")

            status, result = client.request(
                "POST", f"/labs/sessions/{session_id}/steps/{step_id}/check"
            )
            if status != 200 or not result:
                bad(f"{step_id}: check request failed ({status})")
                passed = False
                continue

            if result["passed"]:
                ok(f"{step_id}  {step['instruction'].strip().splitlines()[0][:64]}")
            else:
                passed = False
                bad(f"{step_id}  {step['instruction'].strip().splitlines()[0][:64]}")
                for check in result["checks"]:
                    if not check["passed"]:
                        note(f"       {check['describe']} — {check['detail'][:90]}")
    finally:
        client.request("DELETE", f"/labs/sessions/{session_id}")

    return passed


def main() -> int:
    parser = argparse.ArgumentParser(description="Walk labs as a learner would")
    parser.add_argument("--topic", help="only labs in this topic")
    parser.add_argument("--lab", help="only this lab slug")
    parser.add_argument("--base", default=BASE)
    args = parser.parse_args()

    client = Client(args.base)

    status, ready = client.request("GET", "/labs/health/ready")
    if status != 200 or (ready or {}).get("status") != "ready":
        print(f"{RED}Lab broker is not ready. Start it with: task labs:up{RESET}", file=sys.stderr)
        return 2
    if ready.get("runtime") != "docker":
        print(
            f"{YELLOW}Runtime is '{ready.get('runtime')}' — walking labs needs a real "
            f"container runtime. Set LAB_PROVISIONER=docker.{RESET}",
            file=sys.stderr,
        )
        return 2

    # A throwaway account per run, so quota and progress from a previous run
    # cannot affect this one.
    email = f"walk-{uuid.uuid4().hex[:10]}@example.com"
    status, _ = client.request(
        "POST",
        "/api/v1/auth/register",
        {"email": email, "password": PASSWORD, "display_name": "Lab walker"},
    )
    if status != 201:
        print(f"{RED}Could not create a harness account ({status}){RESET}", file=sys.stderr)
        return 2

    status, roadmap = client.request("GET", "/api/v1/roadmap")
    if status != 200 or not roadmap:
        print(f"{RED}Could not load the roadmap{RESET}", file=sys.stderr)
        return 2

    topics = [
        topic["slug"]
        for course in roadmap["courses"]
        for module in course["modules"]
        for topic in module["topics"]
    ]
    if args.topic:
        topics = [t for t in topics if t == args.topic]

    total = failed = skipped = 0

    for topic in topics:
        status, detail = client.request("GET", f"/api/v1/topics/{topic}")
        if status != 200 or not detail:
            continue

        for lab in detail["labs"]:
            if args.lab and lab["slug"] != args.lab:
                continue
            if lab["tier"] > 2:
                print(f"\n{lab['title']}  {DIM}(tier {lab['tier']} — skipped){RESET}")
                skipped += 1
                continue

            # The walkthrough lives on the internal spec, not the public payload.
            spec = fetch_internal(f"/internal/topics/{topic}/labs/{lab['slug']}/spec")
            if not spec:
                print(f"\n{lab['title']}")
                bad("could not load the lab spec from the api container")
                failed += 1
                total += 1
                continue

            total += 1
            if not walk_lab(client, topic, lab, spec.get("spec", {})):
                failed += 1

    print()
    if skipped:
        print(f"{skipped} lab(s) skipped as higher-tier.")
    if failed:
        print(f"{RED}{failed} of {total} labs failed.{RESET}")
        return 1
    print(f"{GREEN}All {total} labs walked cleanly.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
