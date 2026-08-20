"""Lab verification.

**Design revision, recorded.** The architecture doc specified a `labcheck` binary
injected into each lab, reading a manifest and returning JSON. Building it made
the cost clear: another artifact to compile, ship, version and keep in step with
the check vocabulary that already exists in the API's content schema — and a
binary sitting in the container for a motivated learner to reverse.

The broker interprets checks instead and issues narrow `exec` calls. For seven
checks a lab the round trips are irrelevant, there is nothing to build, the
vocabulary lives in one place, and **no part of the answer ever rests inside the
container**. See docs/architecture/06-lab-architecture.md §6.5.

Two rules govern every check type below:

1. **`argv` lists, never shell strings.** A `path` or `pattern` from a content
   file is passed as an argument, so it cannot become a command. The one
   exception is `command_output`, where running a command *is* the check — and
   those commands come from content we author, never from a learner.
2. **Prefer re-deriving over hard-coding.** `equals_command` compares against a
   reference command run in the same container, so a lab works on any machine
   rather than asserting one operator's numbers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.logging import get_logger
from app.provisioner import LabHandle, Provisioner

log = get_logger(__name__)

MAX_OUTPUT = 4000


@dataclass(frozen=True)
class CheckOutcome:
    passed: bool
    describe: str
    detail: str = ""


class CheckError(Exception):
    pass


async def run_check(provisioner: Provisioner, handle: LabHandle, check: dict) -> CheckOutcome:
    kind = check.get("type", "")
    describe = check.get("describe", kind)

    handler = _HANDLERS.get(kind)
    if handler is None:
        # An unknown check type must fail, not pass. A typo in content should
        # never silently mark a step complete.
        return CheckOutcome(False, describe, f"unknown check type '{kind}'")

    try:
        return await handler(provisioner, handle, check, describe)
    except Exception as exc:
        log.warning("check_errored", type=kind, error=str(exc)[:200])
        return CheckOutcome(False, describe, f"check could not run: {type(exc).__name__}")


# ----------------------------------------------------------------- filesystem


async def _file_exists(p: Provisioner, h: LabHandle, check: dict, describe: str) -> CheckOutcome:
    result = await p.exec(h, ["test", "-e", check["path"]])
    return CheckOutcome(result.ok, describe, "" if result.ok else f"{check['path']} not found")


async def _file_matches(p: Provisioner, h: LabHandle, check: dict, describe: str) -> CheckOutcome:
    result = await p.exec(h, ["cat", check["path"]])
    if not result.ok:
        return CheckOutcome(False, describe, f"could not read {check['path']}")

    pattern = re.compile(check["pattern"], re.MULTILINE)
    content = result.stdout.strip()
    if pattern.search(content):
        return CheckOutcome(True, describe)
    return CheckOutcome(False, describe, f"contents did not match: {_clip(content)}")


async def _file_mode(p: Provisioner, h: LabHandle, check: dict, describe: str) -> CheckOutcome:
    result = await p.exec(h, ["stat", "-c", "%a", check["path"]])
    actual = result.output
    expected = str(check["mode"]).lstrip("0") or "0"
    if result.ok and actual.lstrip("0") == expected:
        return CheckOutcome(True, describe)
    return CheckOutcome(False, describe, f"mode is {actual or 'unknown'}, expected {check['mode']}")


# -------------------------------------------------------------------- commands


async def _command_output(p: Provisioner, h: LabHandle, check: dict, describe: str) -> CheckOutcome:
    result = await p.exec(h, ["/bin/sh", "-lc", check["command"]])
    actual = result.output

    if (reference := check.get("equals_command")) is not None:
        # Re-derive rather than hard-code, so the lab is machine-independent.
        expected_result = await p.exec(h, ["/bin/sh", "-lc", reference])
        expected = expected_result.output
        if actual == expected:
            return CheckOutcome(True, describe)
        return CheckOutcome(False, describe, f"got {_clip(actual)}, expected {_clip(expected)}")

    if (expected := check.get("equals")) is not None:
        if actual == str(expected):
            return CheckOutcome(True, describe)
        return CheckOutcome(
            False, describe, f"got {_clip(actual)}, expected {_clip(str(expected))}"
        )

    if (pattern := check.get("pattern")) is not None:
        if re.search(pattern, actual, re.MULTILINE):
            return CheckOutcome(True, describe)
        return CheckOutcome(False, describe, f"output did not match: {_clip(actual)}")

    return CheckOutcome(False, describe, "check has no comparison")


async def _command_exit(p: Provisioner, h: LabHandle, check: dict, describe: str) -> CheckOutcome:
    result = await p.exec(h, ["/bin/sh", "-lc", check["command"]])
    expected = int(check["exit_code"])
    if result.exit_code == expected:
        return CheckOutcome(True, describe)
    return CheckOutcome(False, describe, f"exited {result.exit_code}, expected {expected}")


async def _command_ran(p: Provisioner, h: LabHandle, check: dict, describe: str) -> CheckOutcome:
    """Did the learner use the right tool, not just reach the right answer?

    Reads shell history. Deliberately forgiving — this exists to teach a habit,
    and failing someone who used an equivalent tool would be pedantry.
    """
    result = await p.exec(h, ["/bin/sh", "-lc", "cat ~/.bash_history 2>/dev/null || true"])
    if re.search(check["pattern"], result.stdout, re.MULTILINE):
        return CheckOutcome(True, describe)
    return CheckOutcome(False, describe, "no matching command found in this session's history")


# --------------------------------------------------------------------- system


async def _process_running(
    p: Provisioner, h: LabHandle, check: dict, describe: str
) -> CheckOutcome:
    result = await p.exec(h, ["/bin/sh", "-lc", "ps -eo args"])
    if re.search(check["pattern"], result.stdout, re.MULTILINE):
        return CheckOutcome(True, describe)
    return CheckOutcome(False, describe, "no matching process is running")


async def _port_listening(p: Provisioner, h: LabHandle, check: dict, describe: str) -> CheckOutcome:
    port = int(check["port"])
    result = await p.exec(h, ["/bin/sh", "-lc", "ss -lntu 2>/dev/null || netstat -lntu"])
    if re.search(rf"[:.]{port}\b", result.stdout):
        return CheckOutcome(True, describe)
    return CheckOutcome(False, describe, f"nothing is listening on port {port}")


async def _http_check(p: Provisioner, h: LabHandle, check: dict, describe: str) -> CheckOutcome:
    expected = int(check.get("status", 200))
    result = await p.exec(
        h,
        ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "10", check["url"]],
        timeout=20,
    )
    actual = result.output
    if actual == str(expected):
        return CheckOutcome(True, describe)
    return CheckOutcome(False, describe, f"got HTTP {actual or 'no response'}, expected {expected}")


_HANDLERS = {
    "file_exists": _file_exists,
    "file_matches": _file_matches,
    "file_mode": _file_mode,
    "command_output": _command_output,
    "command_exit": _command_exit,
    "command_ran": _command_ran,
    "process_running": _process_running,
    "port_listening": _port_listening,
    "http_check": _http_check,
}

SUPPORTED_CHECKS = frozenset(_HANDLERS)


def _clip(value: str) -> str:
    value = value.strip()
    return value if len(value) <= 120 else value[:117] + "..."
