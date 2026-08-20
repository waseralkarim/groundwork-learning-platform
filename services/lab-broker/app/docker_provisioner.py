"""Docker-backed lab provisioning (isolation tier 2).

Talks to the Docker Engine API directly over a unix socket. No SDK: the surface
we need is five endpoints, and a thin client keeps it obvious exactly which
runtime calls this service can make — which matters when the service holds a
socket that is, by construction, a privilege boundary.

**The hardening below is the security control, not a performance tweak.** Every
flag is there because removing it opens something specific:

- `NetworkMode` on a private internal network — no route to Postgres, the API,
  or the internet
- `CapDrop: ALL` — no NET_RAW, no SYS_ADMIN, no mount
- `no-new-privileges` — setuid binaries cannot escalate
- `ReadonlyRootfs` + tmpfs — nothing persists, nothing is written outside RAM
- `PidsLimit` — a fork bomb hits a wall instead of the host
- `Memory` / `NanoCpus` — one learner cannot starve another
- No bind mounts, ever — the host filesystem is not reachable
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import shlex
import uuid
from typing import Any

import aiohttp

from app.core.logging import get_logger
from app.provisioner import ExecResult, LabHandle, LabSpec, ProvisionerError

log = get_logger(__name__)

DOCKER_API_VERSION = "v1.45"
LABEL_MANAGED = "groundwork.lab"
LABEL_SESSION = "groundwork.session"


class TerminalStream:
    """A raw, bidirectional byte stream to a container's TTY.

    Deliberately tiny and transport-agnostic: the relay in main.py only needs
    read, write and close, so a future provisioner (Sysbox, Kubernetes exec) can
    satisfy the same three methods without the relay knowing what is underneath.
    """

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._reader = reader
        self._writer = writer

    async def read(self, limit: int = 4096) -> bytes:
        """Return whatever the TTY has produced. Empty bytes means it closed."""
        return await self._reader.read(limit)

    async def write(self, data: bytes) -> None:
        self._writer.write(data)
        await self._writer.drain()

    async def close(self) -> None:
        with contextlib.suppress(Exception):
            self._writer.close()
            await self._writer.wait_closed()


class DockerProvisioner:
    name = "docker"

    def __init__(self, socket_path: str = "/var/run/docker.sock") -> None:
        self._socket_path = socket_path
        self._session: aiohttp.ClientSession | None = None

    async def _client(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.UnixConnector(path=self._socket_path)
            self._session = aiohttp.ClientSession(
                connector=connector, timeout=aiohttp.ClientTimeout(total=60)
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    def _url(self, path: str) -> str:
        # The host is ignored for a unix socket but aiohttp requires one.
        return f"http://localhost/{DOCKER_API_VERSION}{path}"

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        client = await self._client()
        async with client.request(method, self._url(path), **kwargs) as response:
            body = await response.text()
            if response.status >= 400:
                raise ProvisionerError(f"docker {method} {path} -> {response.status}: {body[:300]}")
            return json.loads(body) if body.strip() else None

    # ------------------------------------------------------------------ health

    async def health(self) -> str:
        info = await self._request("GET", "/version")
        return f"docker {info.get('Version', '?')} (api {info.get('ApiVersion', '?')})"

    # ------------------------------------------------------------------ create

    async def create(self, spec: LabSpec, session_id: uuid.UUID) -> LabHandle:
        network = f"gw-lab-{session_id}"
        await self._request(
            "POST",
            "/networks/create",
            json={
                "Name": network,
                "Driver": "bridge",
                # The single most important line in this file. An internal
                # network has no gateway to the outside world and no route to
                # any other Compose network, so a lab container cannot reach
                # the API, the database, or the internet.
                "Internal": not spec.allow_egress,
                "Labels": {LABEL_MANAGED: "1", LABEL_SESSION: str(session_id)},
            },
        )

        config = {
            "Image": spec.image,
            # A login shell with a TTY. The browser attaches to this.
            "Cmd": ["/bin/bash", "-l"],
            "Tty": True,
            "OpenStdin": True,
            "StdinOnce": False,
            "User": "10001:10001",
            "WorkingDir": "/home/learner",
            "Env": [
                "TERM=xterm-256color",
                "HOME=/home/learner",
                "PS1=lab:\\w$ ",
            ],
            "Labels": {LABEL_MANAGED: "1", LABEL_SESSION: str(session_id)},
            "HostConfig": {
                "NetworkMode": network,
                "AutoRemove": False,
                "ReadonlyRootfs": True,
                # `exec` is deliberate and load-bearing. Docker defaults tmpfs
                # to noexec, which is good hardening on a server and fatal here:
                # half this curriculum has the learner compile a program and run
                # it. A lab where `gcc hello.c && ./a.out` fails with Permission
                # denied is not a lab.
                #
                # `nosuid` and `nodev` stay — those are the options that prevent
                # privilege escalation. Running your own binary inside your own
                # disposable, capability-less, network-isolated sandbox is the
                # entire point of the sandbox.
                "Tmpfs": {
                    "/tmp": f"rw,exec,nosuid,nodev,size={spec.disk_mb}m,mode=1777",
                    "/home/learner": (
                        f"rw,exec,nosuid,nodev,size={spec.disk_mb}m,uid=10001,gid=10001"
                    ),
                    # /run holds no learner content and never needs to execute.
                    "/run": "rw,noexec,nosuid,nodev,size=16m",
                },
                "CapDrop": ["ALL"],
                "CapAdd": list(spec.extra_capabilities),
                "SecurityOpt": ["no-new-privileges:true"],
                "Memory": spec.memory_mb * 1024 * 1024,
                "MemorySwap": spec.memory_mb * 1024 * 1024,  # equal = no swap
                "NanoCpus": int(spec.cpus * 1_000_000_000),
                "PidsLimit": spec.pids_limit,
                "Ulimits": [
                    {"Name": "nofile", "Soft": 1024, "Hard": 1024},
                    {"Name": "nproc", "Soft": spec.pids_limit, "Hard": spec.pids_limit},
                ],
                # No Binds key at all. The host filesystem is not reachable, and
                # its absence here is the reason.
                "RestartPolicy": {"Name": "no"},
            },
        }

        try:
            created = await self._request(
                "POST", f"/containers/create?name=gw-lab-{session_id}", json=config
            )
            container_id = created["Id"]
            await self._request("POST", f"/containers/{container_id}/start")
        except Exception:
            # Never leave a network behind if the container failed to start.
            await self._remove_network(network)
            raise

        handle = LabHandle(session_id=session_id, container_ref=container_id, network_ref=network)

        for command in spec.setup:
            result = await self.exec(handle, ["/bin/sh", "-lc", command], timeout=60)
            if not result.ok:
                log.warning(
                    "lab_setup_failed",
                    session_id=str(session_id),
                    command=command,
                    stderr=result.stderr[:200],
                )

        log.info(
            "lab_created",
            session_id=str(session_id),
            lab_id=spec.lab_id,
            image=spec.image,
            memory_mb=spec.memory_mb,
        )
        return handle

    # -------------------------------------------------------------------- exec

    async def exec(self, handle: LabHandle, argv: list[str], timeout: int = 15) -> ExecResult:
        created = await self._request(
            "POST",
            f"/containers/{handle.container_ref}/exec",
            json={
                "AttachStdout": True,
                "AttachStderr": True,
                "Tty": False,
                "Cmd": argv,
                "User": "10001:10001",
            },
        )
        exec_id = created["Id"]

        client = await self._client()
        try:
            async with client.post(
                self._url(f"/exec/{exec_id}/start"),
                json={"Detach": False, "Tty": False},
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                raw = await response.read()
        except TimeoutError as exc:
            raise ProvisionerError(f"exec timed out after {timeout}s: {shlex.join(argv)}") from exc

        stdout, stderr = _demultiplex(raw)
        inspected = await self._request("GET", f"/exec/{exec_id}/json")
        return ExecResult(
            exit_code=inspected.get("ExitCode") or 0,
            stdout=stdout,
            stderr=stderr,
        )

    # ----------------------------------------------------------------- destroy

    async def destroy(self, handle: LabHandle) -> None:
        """Idempotent. A reaper that throws on an already-gone container is useless."""
        # Suppressed on purpose: a reaper that throws on an already-gone
        # container stops reaping every container after it.
        with contextlib.suppress(ProvisionerError):
            await self._request("POST", f"/containers/{handle.container_ref}/kill?signal=SIGKILL")
        with contextlib.suppress(ProvisionerError):
            await self._request("DELETE", f"/containers/{handle.container_ref}?force=true&v=true")
        if handle.network_ref:
            await self._remove_network(handle.network_ref)
        log.info("lab_destroyed", session_id=str(handle.session_id))

    async def _remove_network(self, network: str) -> None:
        with contextlib.suppress(ProvisionerError):
            await self._request("DELETE", f"/networks/{network}")

    async def is_alive(self, handle: LabHandle) -> bool:
        try:
            state = await self._request("GET", f"/containers/{handle.container_ref}/json")
        except ProvisionerError:
            return False
        return bool(state.get("State", {}).get("Running"))

    # --------------------------------------------------------------- terminal

    async def attach(self, handle: LabHandle) -> TerminalStream:
        """Attach to the container's TTY, using the hijacked HTTP attach.

        Not `/attach/ws`, which is the obvious choice and does not work: it
        completes its handshake, reports no error, and then moves no bytes in
        either direction. Every layer looks healthy — the container is running,
        the broker logs an attach, the browser gets its 101 — and the learner
        sees a blank terminal. This is the endpoint `docker attach` itself uses,
        and it is the one that works.

        The container is created with `Tty: True`, so this stream is raw. When a
        container has no TTY, Docker multiplexes stdout and stderr behind an
        8-byte frame header that would have to be parsed here.

        The browser never reaches this. The broker sits in the middle and pumps
        bytes, which is what makes handing someone a root shell acceptable.
        """
        reader, writer = await asyncio.open_unix_connection(self._socket_path)
        path = (
            f"/{DOCKER_API_VERSION}/containers/{handle.container_ref}"
            # `logs=1` replays what the TTY has already produced — the shell's
            # first prompt, printed when the container started, before any
            # browser was attached. Without it the learner opens the lab to a
            # blank rectangle and has to press Enter to discover it works.
            "/attach?logs=1&stream=1&stdin=1&stdout=1&stderr=1"
        )
        request = (
            f"POST {path} HTTP/1.1\r\n"
            "Host: docker\r\n"
            "Connection: Upgrade\r\n"
            "Upgrade: tcp\r\n"
            "Content-Length: 0\r\n"
            "\r\n"
        )
        writer.write(request.encode())
        await writer.drain()

        try:
            header = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=10)
        except (TimeoutError, asyncio.IncompleteReadError) as exc:
            writer.close()
            raise ProvisionerError("docker did not respond to the attach request") from exc

        status_line = header.split(b"\r\n", 1)[0].decode(errors="replace")
        if "101" not in status_line:
            writer.close()
            raise ProvisionerError(f"docker refused the attach: {status_line}")

        return TerminalStream(reader, writer)

    # ------------------------------------------------------------- orphan sweep

    async def sweep_orphans(self, known: set[str]) -> int:
        """Destroy labelled containers the broker has forgotten.

        A broker restart must not leave learner containers running forever. This
        is the backstop the TTL reaper cannot provide, because the reaper only
        knows about sessions still in its own state.
        """
        filters = json.dumps({"label": [f"{LABEL_MANAGED}=1"]})
        containers = await self._request("GET", f"/containers/json?all=true&filters={filters}")
        removed = 0
        for container in containers or []:
            session = container.get("Labels", {}).get(LABEL_SESSION, "")
            if session in known:
                continue
            await self.destroy(
                LabHandle(
                    session_id=uuid.UUID(session) if _is_uuid(session) else uuid.uuid4(),
                    container_ref=container["Id"],
                    network_ref=f"gw-lab-{session}" if session else None,
                )
            )
            removed += 1
        if removed:
            log.info("lab_orphans_swept", count=removed)
        return removed


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError):
        return False
    return True


def _demultiplex(raw: bytes) -> tuple[str, str]:
    """Split Docker's multiplexed exec stream into stdout and stderr.

    Without a TTY, Docker frames output as an 8-byte header (stream type, then a
    big-endian length) followed by the payload. Reading it as plain text gives
    you the header bytes interleaved with the content.
    """
    stdout: list[bytes] = []
    stderr: list[bytes] = []
    offset = 0

    while offset + 8 <= len(raw):
        stream_type = raw[offset]
        length = int.from_bytes(raw[offset + 4 : offset + 8], "big")
        payload = raw[offset + 8 : offset + 8 + length]
        (stderr if stream_type == 2 else stdout).append(payload)
        offset += 8 + length

    if offset == 0 and raw:
        # Not framed after all (a TTY exec, or a runtime that does not frame).
        return raw.decode("utf-8", "replace"), ""

    return (
        b"".join(stdout).decode("utf-8", "replace"),
        b"".join(stderr).decode("utf-8", "replace"),
    )


async def probe(socket_path: str = "/var/run/docker.sock") -> str:
    """Standalone reachability check, used by `task labs:verify`."""
    provisioner = DockerProvisioner(socket_path)
    try:
        return await provisioner.health()
    finally:
        await provisioner.close()


if __name__ == "__main__":  # pragma: no cover - operator convenience
    print(asyncio.run(probe()))
