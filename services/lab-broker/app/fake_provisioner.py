"""An in-memory provisioner.

Exists for two reasons, and the second one is the important one:

1. Tests. Session lifecycle, quotas, TTL reaping and check dispatch are all
   runtime-independent, so testing them against a real Docker daemon would be
   slow and would prove nothing extra.
2. **It proves the `Provisioner` seam is real.** If the broker only ever worked
   against Docker, "we can move to Kubernetes later" would be a claim rather
   than a fact. A second working implementation is the evidence.

It simulates a filesystem and a command table well enough to exercise every
check type without executing anything.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from app.provisioner import ExecResult, LabHandle, LabSpec


@dataclass
class FakeContainer:
    files: dict[str, str] = field(default_factory=dict)
    modes: dict[str, str] = field(default_factory=dict)
    commands: dict[str, tuple[int, str]] = field(default_factory=dict)
    history: list[str] = field(default_factory=list)
    processes: list[str] = field(default_factory=list)
    ports: list[int] = field(default_factory=list)
    running: bool = True


class FakeProvisioner:
    name = "fake"

    def __init__(self) -> None:
        self.containers: dict[str, FakeContainer] = {}
        self.created: list[LabSpec] = []
        self.destroyed: list[str] = []

    async def create(self, spec: LabSpec, session_id: uuid.UUID) -> LabHandle:
        ref = f"fake-{session_id}"
        self.containers[ref] = FakeContainer()
        self.created.append(spec)
        return LabHandle(session_id=session_id, container_ref=ref, network_ref=f"net-{session_id}")

    async def exec(self, handle: LabHandle, argv: list[str], timeout: int = 15) -> ExecResult:
        container = self.containers.get(handle.container_ref)
        if container is None or not container.running:
            return ExecResult(1, "", "container is not running")

        # test -e <path>
        if argv[:2] == ["test", "-e"]:
            return ExecResult(0 if argv[2] in container.files else 1, "", "")

        # cat <path>
        if argv[0] == "cat" and len(argv) == 2:
            content = container.files.get(argv[1])
            if content is None:
                return ExecResult(1, "", "no such file")
            return ExecResult(0, content, "")

        # stat -c %a <path>
        if argv[:3] == ["stat", "-c", "%a"]:
            mode = container.modes.get(argv[3])
            return ExecResult(0, mode, "") if mode else ExecResult(1, "", "no such file")

        if argv[:2] == ["/bin/sh", "-lc"]:
            return self._shell(container, argv[2])

        if argv[0] == "curl":
            url = argv[-1]
            code, body = container.commands.get(f"HTTP {url}", (0, "200"))
            return ExecResult(code, body, "")

        return ExecResult(127, "", f"fake: unknown command {argv[0]}")

    def _shell(self, container: FakeContainer, command: str) -> ExecResult:
        container.history.append(command)

        if "bash_history" in command:
            return ExecResult(0, "\n".join(container.history), "")
        if command.startswith("ps -eo"):
            return ExecResult(0, "\n".join(container.processes), "")
        if command.startswith("ss -lntu") or command.startswith("netstat"):
            listing = "\n".join(f"tcp LISTEN 0 0 0.0.0.0:{port}" for port in container.ports)
            return ExecResult(0, listing, "")

        if command in container.commands:
            code, output = container.commands[command]
            return ExecResult(code, output, "")
        return ExecResult(0, "", "")

    async def destroy(self, handle: LabHandle) -> None:
        self.containers.pop(handle.container_ref, None)
        self.destroyed.append(handle.container_ref)

    async def is_alive(self, handle: LabHandle) -> bool:
        container = self.containers.get(handle.container_ref)
        return bool(container and container.running)

    async def health(self) -> str:
        return f"fake provisioner ({len(self.containers)} containers)"

    # ------------------------------------------------------------ test helpers

    def seed(self, handle: LabHandle) -> FakeContainer:
        return self.containers[handle.container_ref]

    def matches_history(self, handle: LabHandle, pattern: str) -> bool:
        container = self.containers[handle.container_ref]
        return any(re.search(pattern, entry) for entry in container.history)
