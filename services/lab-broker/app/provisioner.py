"""Lab provisioning.

The one seam in the platform that matters for portability. Everything above this
protocol — session lifecycle, quotas, TTL reaping, check execution, the terminal
proxy — is runtime-agnostic. Moving labs from a local Docker socket to a remote
lab host, to Kubernetes, or to Firecracker microVMs replaces an implementation
here and nothing else.

Threat model reminder (docs/architecture/06-lab-architecture.md): the learner has
root inside the lab and is assumed hostile. Every implementation must satisfy:

1. No credentials in the container.
2. No route to the application network, no egress by default.
3. Resource caps that hold against a fork bomb or a disk filler.
4. A hard TTL, enforced from outside.
5. The grading logic is not derivable from inside.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class LabSpec:
    """What to provision. Derived from a lab's content definition."""

    lab_id: str
    image: str
    tier: int
    duration_minutes: int
    setup: list[str] = field(default_factory=list)

    # Hardening. These are defaults, not suggestions — a caller may tighten them
    # but the provisioner refuses to loosen past its own floor.
    memory_mb: int = 512
    cpus: float = 0.5
    pids_limit: int = 256
    disk_mb: int = 2048
    # Networking labs need NET_ADMIN; nothing else gets a capability back.
    extra_capabilities: tuple[str, ...] = ()
    allow_egress: bool = False


@dataclass(frozen=True)
class LabHandle:
    """An opaque reference to a running lab, meaningful only to its provisioner."""

    session_id: uuid.UUID
    container_ref: str
    network_ref: str | None = None


@dataclass(frozen=True)
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    @property
    def output(self) -> str:
        return (self.stdout or self.stderr).strip()


class ProvisionerError(Exception):
    pass


# runtime_checkable so a test can assert an implementation actually satisfies
# this. It only verifies method names, not signatures — a weak guarantee, but it
# catches the case that matters: a new provisioner that forgot to implement one.
@runtime_checkable
class Provisioner(Protocol):
    """The runtime boundary.

    Implementations: DockerProvisioner (tier 2, local or remote daemon),
    SysboxProvisioner (tier 3, nested Docker/k3s), K8sProvisioner,
    FirecrackerProvisioner (tier 4). Only the first two are in scope.
    """

    name: str

    async def create(self, spec: LabSpec, session_id: uuid.UUID) -> LabHandle:
        """Provision an isolated environment and start it."""
        ...

    async def exec(self, handle: LabHandle, argv: list[str], timeout: int = 15) -> ExecResult:
        """Run a command inside the lab and capture its output.

        `argv` is a list, never a string: there is no shell interpolation, so a
        path or pattern from a content file cannot become a command.
        """
        ...

    async def destroy(self, handle: LabHandle) -> None:
        """Remove the environment and everything it created. Must be idempotent."""
        ...

    async def is_alive(self, handle: LabHandle) -> bool: ...

    async def health(self) -> str:
        """Human-readable runtime status, for /health/ready."""
        ...
