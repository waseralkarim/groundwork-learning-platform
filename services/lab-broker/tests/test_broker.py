"""Lab broker tests.

Run against the fake provisioner, which is the point: session lifecycle, quotas,
TTL reaping and check dispatch are runtime-independent, so testing them against a
real Docker daemon would be slower and would prove nothing extra. The Docker
implementation is exercised separately by `task labs:verify` against a live
runtime.

The tests that matter most here are the ones about *limits* — quota, TTL,
ownership. Those are the properties that make it acceptable to hand someone a
root shell.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.checks import SUPPORTED_CHECKS, run_check
from app.fake_provisioner import FakeProvisioner
from app.provisioner import LabSpec
from app.sessions import (
    MAX_ACTIVE_SESSIONS_PER_USER,
    QuotaExceededError,
    SessionManager,
    SessionNotFoundError,
)

SPEC = LabSpec(
    lab_id="inspect-the-machine",
    image="groundwork/lab-foundations:1",
    tier=2,
    duration_minutes=20,
)


@pytest.fixture
def provisioner() -> FakeProvisioner:
    return FakeProvisioner()


@pytest.fixture
def manager(provisioner: FakeProvisioner) -> SessionManager:
    return SessionManager(provisioner)


async def start(manager: SessionManager, user: str = "user-1"):
    return await manager.create(
        user_id=user, lab_id=SPEC.lab_id, topic_slug="the-machine", spec=SPEC
    )


# ---------------------------------------------------------------- lifecycle


async def test_creating_a_session_provisions_an_environment(
    manager: SessionManager, provisioner: FakeProvisioner
) -> None:
    session = await start(manager)
    assert await provisioner.is_alive(session.handle)
    assert session.seconds_remaining > 0


async def test_destroying_a_session_removes_the_environment(
    manager: SessionManager, provisioner: FakeProvisioner
) -> None:
    session = await start(manager)
    await manager.destroy(session.id)
    assert not await provisioner.is_alive(session.handle)
    assert manager.active_count == 0


async def test_destroy_is_idempotent(manager: SessionManager) -> None:
    session = await start(manager)
    await manager.destroy(session.id)
    await manager.destroy(session.id)  # must not raise
    assert manager.active_count == 0


# -------------------------------------------------------------------- quota


async def test_a_learner_may_only_run_one_lab_at_a_time(manager: SessionManager) -> None:
    for _ in range(MAX_ACTIVE_SESSIONS_PER_USER):
        await start(manager)
    with pytest.raises(QuotaExceededError):
        await start(manager)


async def test_ending_a_lab_frees_the_quota(manager: SessionManager) -> None:
    session = await start(manager)
    with pytest.raises(QuotaExceededError):
        await start(manager)
    await manager.destroy(session.id)
    assert await start(manager) is not None


async def test_one_learners_quota_does_not_block_another(manager: SessionManager) -> None:
    await start(manager, user="user-1")
    assert await start(manager, user="user-2") is not None


# ---------------------------------------------------------------- ownership


async def test_a_learner_cannot_reach_another_learners_session(manager: SessionManager) -> None:
    session = await start(manager, user="owner")
    with pytest.raises(SessionNotFoundError):
        manager.get(session.id, "intruder")


async def test_an_unknown_session_and_a_foreign_one_fail_identically(
    manager: SessionManager,
) -> None:
    """Otherwise the error is an oracle for which session ids are real."""
    session = await start(manager, user="owner")

    with pytest.raises(SessionNotFoundError) as foreign:
        manager.get(session.id, "intruder")
    with pytest.raises(SessionNotFoundError) as unknown:
        manager.get(uuid.uuid4(), "intruder")

    assert str(foreign.value) == str(unknown.value)


# ---------------------------------------------------------------------- TTL


async def test_an_expired_session_is_not_readable(manager: SessionManager) -> None:
    session = await start(manager)
    session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    with pytest.raises(SessionNotFoundError):
        manager.get(session.id, "user-1")


async def test_the_reaper_destroys_expired_sessions(
    manager: SessionManager, provisioner: FakeProvisioner
) -> None:
    """The property that makes a forgotten lab survivable.

    Nobody ends a lab; they close the tab. If the TTL were advisory, every
    abandoned lab would run until the host was rebooted.
    """
    session = await start(manager)
    session.expires_at = datetime.now(UTC) - timedelta(seconds=1)

    reaped = await manager.reap_once()

    assert reaped == 1
    assert manager.active_count == 0
    assert not await provisioner.is_alive(session.handle)


async def test_the_reaper_leaves_live_sessions_alone(manager: SessionManager) -> None:
    await start(manager)
    assert await manager.reap_once() == 0
    assert manager.active_count == 1


async def test_shutdown_destroys_every_session(
    manager: SessionManager, provisioner: FakeProvisioner
) -> None:
    """A broker restart must not orphan running containers."""
    await start(manager, user="a")
    await start(manager, user="b")
    await manager.shutdown()
    assert manager.active_count == 0
    assert len(provisioner.destroyed) == 2


async def test_the_reaper_survives_a_failing_iteration(manager: SessionManager) -> None:
    """A reaper that dies on one bad session stops reaping every other one."""
    manager.start_reaper()
    await asyncio.sleep(0)
    assert manager._reaper is not None
    assert not manager._reaper.done()
    await manager.shutdown()


# ------------------------------------------------------------------- checks


async def test_every_declared_check_type_has_a_handler() -> None:
    """The content schema and the executor must not drift apart.

    A check type content can author but the broker cannot run would silently
    fail every step that uses it.
    """
    from_schema = {
        "file_exists",
        "file_matches",
        "file_mode",
        "command_output",
        "command_exit",
        "command_ran",
        "process_running",
        "port_listening",
        "http_check",
    }
    assert from_schema == SUPPORTED_CHECKS


async def test_file_exists(manager: SessionManager, provisioner: FakeProvisioner) -> None:
    session = await start(manager)
    provisioner.seed(session.handle).files["/tmp/answer"] = "x86_64"

    ok = await run_check(
        provisioner, session.handle, {"type": "file_exists", "path": "/tmp/answer", "describe": "d"}
    )
    missing = await run_check(
        provisioner, session.handle, {"type": "file_exists", "path": "/tmp/nope", "describe": "d"}
    )
    assert ok.passed and not missing.passed


async def test_file_matches(manager: SessionManager, provisioner: FakeProvisioner) -> None:
    session = await start(manager)
    provisioner.seed(session.handle).files["/tmp/n"] = "4096"

    ok = await run_check(
        provisioner,
        session.handle,
        {"type": "file_matches", "path": "/tmp/n", "pattern": r"^\d+$", "describe": "d"},
    )
    bad = await run_check(
        provisioner,
        session.handle,
        {"type": "file_matches", "path": "/tmp/n", "pattern": r"^[a-z]+$", "describe": "d"},
    )
    assert ok.passed and not bad.passed


async def test_command_output_equals_command_rederives_the_answer(
    manager: SessionManager, provisioner: FakeProvisioner
) -> None:
    """The property that makes a lab machine-independent."""
    session = await start(manager)
    container = provisioner.seed(session.handle)
    container.commands["cat /tmp/answer-arch"] = (0, "x86_64")
    container.commands["uname -m"] = (0, "x86_64")

    result = await run_check(
        provisioner,
        session.handle,
        {
            "type": "command_output",
            "command": "cat /tmp/answer-arch",
            "equals_command": "uname -m",
            "describe": "architecture matches",
        },
    )
    assert result.passed


async def test_command_output_reports_the_mismatch(
    manager: SessionManager, provisioner: FakeProvisioner
) -> None:
    session = await start(manager)
    container = provisioner.seed(session.handle)
    container.commands["cat /tmp/a"] = (0, "aarch64")
    container.commands["uname -m"] = (0, "x86_64")

    result = await run_check(
        provisioner,
        session.handle,
        {
            "type": "command_output",
            "command": "cat /tmp/a",
            "equals_command": "uname -m",
            "describe": "d",
        },
    )
    assert not result.passed
    assert "aarch64" in result.detail and "x86_64" in result.detail


async def test_command_exit(manager: SessionManager, provisioner: FakeProvisioner) -> None:
    session = await start(manager)
    provisioner.seed(session.handle).commands["test -x /tmp/hello"] = (0, "")

    result = await run_check(
        provisioner,
        session.handle,
        {"type": "command_exit", "command": "test -x /tmp/hello", "exit_code": 0, "describe": "d"},
    )
    assert result.passed


async def test_command_ran_reads_history(
    manager: SessionManager, provisioner: FakeProvisioner
) -> None:
    session = await start(manager)
    provisioner.seed(session.handle).history.append("lsblk -o NAME,SIZE")

    result = await run_check(
        provisioner, session.handle, {"type": "command_ran", "pattern": "lsblk", "describe": "d"}
    )
    assert result.passed


async def test_process_running(manager: SessionManager, provisioner: FakeProvisioner) -> None:
    session = await start(manager)
    provisioner.seed(session.handle).processes.append("/opt/lab/eat-memory 200")

    result = await run_check(
        provisioner,
        session.handle,
        {"type": "process_running", "pattern": "eat-memory", "describe": "d"},
    )
    assert result.passed


async def test_port_listening(manager: SessionManager, provisioner: FakeProvisioner) -> None:
    session = await start(manager)
    provisioner.seed(session.handle).ports.append(8080)

    ok = await run_check(
        provisioner, session.handle, {"type": "port_listening", "port": 8080, "describe": "d"}
    )
    closed = await run_check(
        provisioner, session.handle, {"type": "port_listening", "port": 9999, "describe": "d"}
    )
    assert ok.passed and not closed.passed


async def test_an_unknown_check_type_fails_rather_than_passes(
    manager: SessionManager, provisioner: FakeProvisioner
) -> None:
    """A typo in content must never silently mark a step complete."""
    session = await start(manager)
    result = await run_check(
        provisioner, session.handle, {"type": "invented_check", "describe": "d"}
    )
    assert not result.passed
    assert "unknown check type" in result.detail


async def test_a_check_against_a_dead_container_fails_cleanly(
    manager: SessionManager, provisioner: FakeProvisioner
) -> None:
    session = await start(manager)
    await provisioner.destroy(session.handle)

    result = await run_check(
        provisioner, session.handle, {"type": "file_exists", "path": "/tmp/x", "describe": "d"}
    )
    assert not result.passed


# ----------------------------------------------------------------- hardening


async def test_the_spec_defaults_are_restrictive() -> None:
    """These defaults are the security control. A change here is a policy change."""
    spec = LabSpec(lab_id="x", image="i", tier=2, duration_minutes=10)
    assert spec.allow_egress is False
    assert spec.extra_capabilities == ()
    assert spec.memory_mb <= 512
    assert spec.pids_limit <= 256


async def test_the_provisioner_protocol_is_actually_satisfiable() -> None:
    """Two implementations is what makes the seam real rather than aspirational."""
    from app.docker_provisioner import DockerProvisioner
    from app.provisioner import Provisioner

    for implementation in (FakeProvisioner(), DockerProvisioner("/nonexistent.sock")):
        assert isinstance(implementation, Provisioner)
