"""Lab broker.

Sits between the browser and a container runtime. Its whole job is to be the
only thing in the system that touches the runtime, and to be narrow enough that
holding that access is defensible.

What it does: authorise, enforce quota, provision, relay a terminal, run
declarative checks, reap on TTL.

What it deliberately does not do: interpret learner input, execute
content-supplied shell on the host, hold database credentials, or proxy
arbitrary runtime calls. A learner reaching this service can start a lab they
are entitled to and nothing else.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiohttp
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import BaseModel, Field

from app.checks import SUPPORTED_CHECKS, run_check
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.telemetry import (
    attach_log_handler,
    configure_telemetry,
    instrument_app,
    record_check,
    record_provision,
)
from app.provisioner import LabSpec, Provisioner, ProvisionerError
from app.sessions import QuotaExceededError, SessionManager, SessionNotFoundError

settings = get_settings()
telemetry_on = configure_telemetry(
    settings.otel_service_name,
    settings.otel_exporter_otlp_endpoint,
    settings.groundwork_env,
)
configure_logging(settings.log_level, json_output=settings.groundwork_env != "development")
attach_log_handler()
log = get_logger(__name__)

SESSION_COOKIE = "gw_session"

_provisioner: Provisioner
_manager: SessionManager


def _build_provisioner() -> Provisioner:
    if settings.provisioner == "fake":
        from app.fake_provisioner import FakeProvisioner

        log.warning("using_fake_provisioner", reason="no container runtime configured")
        return FakeProvisioner()

    from app.docker_provisioner import DockerProvisioner

    return DockerProvisioner(settings.docker_socket)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _provisioner, _manager
    _provisioner = _build_provisioner()
    _manager = SessionManager(_provisioner)

    try:
        status_line = await _provisioner.health()
        log.info("lab_runtime_ready", runtime=_provisioner.name, detail=status_line)
    except Exception as exc:
        # Starting without a runtime is correct: /health/ready reports the
        # failure and the labs profile degrades instead of taking the stack down.
        log.error("lab_runtime_unavailable", runtime=_provisioner.name, error=str(exc)[:200])

    # Anything left over from an unclean shutdown is not ours to keep.
    sweep = getattr(_provisioner, "sweep_orphans", None)
    if sweep is not None:
        try:
            await sweep(set())
        except Exception:
            log.warning("orphan_sweep_failed")

    _manager.start_reaper()
    yield

    await _manager.shutdown()
    close = getattr(_provisioner, "close", None)
    if close is not None:
        await close()


app = FastAPI(
    title="Groundwork lab broker",
    description="Provisions, attaches to and verifies ephemeral lab environments.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
)

router = APIRouter(prefix="/labs")


# ---------------------------------------------------------------------- auth


async def _resolve_user(cookie: str | None) -> str:
    """Ask the API who this is.

    The broker validates nothing itself. One service owns authentication, and a
    second copy of those rules is a second place for them to be wrong.
    """
    if not cookie:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not signed in")

    try:
        async with (
            aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as client,
            client.get(
                f"{settings.api_internal_url}/v1/auth/me",
                headers={"cookie": f"{SESSION_COOKIE}={cookie}"},
            ) as response,
        ):
            if response.status != 200:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not signed in")
            body = await response.json()
    except aiohttp.ClientError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not verify your session"
        ) from exc

    return str(body["id"])


async def current_user(request: Request) -> str:
    return await _resolve_user(request.cookies.get(SESSION_COOKIE))


# -------------------------------------------------------------------- health


# Registered on both paths on purpose: the container healthcheck hits
# /health/live directly, while Caddy routes /labs/* here *without* stripping the
# prefix, so anything reachable through the proxy must answer under /labs.
@app.get("/health/live")
@app.get("/labs/health/live")
async def liveness() -> dict:
    return {"status": "alive"}


@app.get("/health/ready")
@app.get("/labs/health/ready")
async def readiness() -> dict:
    try:
        detail = await _provisioner.health()
        return {"status": "ready", "runtime": _provisioner.name, "detail": detail}
    except Exception as exc:
        return {"status": "degraded", "runtime": _provisioner.name, "detail": str(exc)[:200]}


@app.get("/health/sessions")
@app.get("/labs/health/sessions")
async def session_stats() -> dict:
    return {"active": _manager.active_count, "runtime": _provisioner.name}


# ------------------------------------------------------------------ sessions


class CreateSessionIn(BaseModel):
    topic_slug: str = Field(min_length=1, max_length=120)
    lab_slug: str = Field(min_length=1, max_length=120)


class SessionOut(BaseModel):
    session_id: str
    lab_id: str
    expires_in_seconds: int
    terminal_url: str
    runtime: str


async def _fetch_lab(topic_slug: str, lab_slug: str) -> dict:
    """Load the lab definition from the API.

    The broker never reads content from disk. The API is the only thing that
    parses and serves curriculum, so a lab cannot be started that the content
    pipeline has not validated.
    """
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as client:
        url = f"{settings.api_internal_url}/v1/topics/{topic_slug}/labs/{lab_slug}"
        async with client.get(url) as response:
            if response.status == 404:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="lab not found")
            if response.status != 200:
                raise HTTPException(
                    status.HTTP_502_BAD_GATEWAY, detail="could not load the lab definition"
                )
            return await response.json()


async def _fetch_lab_resources(topic_slug: str, lab_slug: str) -> tuple[list[str], int | None]:
    """The lab's setup commands and any resource it asks for, in one call.

    Setup is not in the public lab payload — a scenario that seeds a broken
    system would give the answer away. It is fetched from the internal endpoint,
    which the edge blocks, and run once before the learner attaches.

    `disk_mb` comes from the same place. Most labs leave it unset and take the
    default; a lab whose teaching depends on filling a filesystem has to ask for
    a small one, because the default writable space is larger than the memory
    limit and a tmpfs is memory — so the OOM killer arrives before ENOSPC does.
    """
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as client:
        url = f"{settings.api_internal_url}/v1/internal/topics/{topic_slug}/labs/{lab_slug}/spec"
        async with client.get(url) as response:
            if response.status != 200:
                log.warning("lab_spec_unavailable", lab=lab_slug, status=response.status)
                return [], None
            body = await response.json()

    spec = body.get("spec", {})
    setup = [str(command) for command in (spec.get("setup") or [])]
    disk_mb = spec.get("disk_mb")
    return setup, int(disk_mb) if disk_mb else None


@router.post("/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(body: CreateSessionIn, user_id: str = Depends(current_user)) -> SessionOut:
    lab = await _fetch_lab(body.topic_slug, body.lab_slug)

    if lab["tier"] > 2:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                f"This lab needs isolation tier {lab['tier']} (nested containers), which "
                "requires a Linux lab host running Sysbox. Run it on your own machine for now."
            ),
        )

    setup, disk_mb = await _fetch_lab_resources(body.topic_slug, lab["slug"])
    spec = LabSpec(
        lab_id=lab["slug"],
        image=lab["image"],
        tier=lab["tier"],
        duration_minutes=lab["duration_minutes"],
        setup=setup,
        **({"disk_mb": disk_mb} if disk_mb else {}),
    )

    started = time.perf_counter()
    try:
        session = await _manager.create(
            user_id=user_id, lab_id=lab["slug"], topic_slug=body.topic_slug, spec=spec
        )
    except QuotaExceededError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except ProvisionerError as exc:
        # Timed even on failure: a provisioner that fails slowly is a different
        # operational problem from one that fails fast, and the difference is
        # invisible if only successes are measured.
        record_provision(time.perf_counter() - started, lab["slug"], ok=False)
        log.error("lab_provision_failed", error=str(exc)[:300])
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not start a lab environment. The lab runtime may be unavailable.",
        ) from exc

    record_provision(time.perf_counter() - started, lab["slug"], ok=True)

    return SessionOut(
        session_id=str(session.id),
        lab_id=session.lab_id,
        expires_in_seconds=session.seconds_remaining,
        terminal_url=f"/labs/sessions/{session.id}/terminal",
        runtime=_provisioner.name,
    )


@router.get("/sessions/{session_id}", response_model=SessionOut)
async def get_session(session_id: uuid.UUID, user_id: str = Depends(current_user)) -> SessionOut:
    try:
        session = _manager.get(session_id, user_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return SessionOut(
        session_id=str(session.id),
        lab_id=session.lab_id,
        expires_in_seconds=session.seconds_remaining,
        terminal_url=f"/labs/sessions/{session.id}/terminal",
        runtime=_provisioner.name,
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def end_session(session_id: uuid.UUID, user_id: str = Depends(current_user)) -> None:
    try:
        _manager.get(session_id, user_id)
    except SessionNotFoundError:
        return  # Already gone. Ending a dead lab is not an error.
    await _manager.destroy(session_id, reason="learner_ended")


# --------------------------------------------------------------------- checks


class CheckResultOut(BaseModel):
    passed: bool
    describe: str
    detail: str


class StepResultOut(BaseModel):
    step_id: str
    passed: bool
    checks: list[CheckResultOut]


@router.post("/sessions/{session_id}/steps/{step_id}/check", response_model=StepResultOut)
async def check_step(
    session_id: uuid.UUID, step_id: str, user_id: str = Depends(current_user)
) -> StepResultOut:
    try:
        session = _manager.get(session_id, user_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    lab = await _fetch_lab(session.topic_slug, session.lab_id)
    steps = {step["id"]: step for step in lab.get("steps", [])}
    if step_id not in steps:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"step '{step_id}' not found")

    # The public lab endpoint omits verify specs, so fetch them from the
    # authoritative endpoint. The learner's browser never sees this payload.
    checks = await _fetch_step_checks(session.topic_slug, session.lab_id, step_id)

    outcomes = [await run_check(_provisioner, session.handle, check) for check in checks]
    results = [
        CheckResultOut(passed=o.passed, describe=o.describe, detail=o.detail) for o in outcomes
    ]
    passed = bool(outcomes) and all(o.passed for o in outcomes)

    session.step_results[step_id] = [r.model_dump() for r in results]
    record_check(session.lab_id, step_id, passed=passed)
    log.info(
        "lab_step_checked",
        session_id=str(session_id),
        step_id=step_id,
        passed=passed,
        checks=len(results),
    )
    return StepResultOut(step_id=step_id, passed=passed, checks=results)


async def _fetch_step_checks(topic_slug: str, lab_slug: str, step_id: str) -> list[dict]:
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as client:
        url = (
            f"{settings.api_internal_url}/v1/internal/topics/{topic_slug}"
            f"/labs/{lab_slug}/steps/{step_id}/checks"
        )
        async with client.get(url) as response:
            if response.status != 200:
                raise HTTPException(
                    status.HTTP_502_BAD_GATEWAY, detail="could not load verification checks"
                )
            checks = await response.json()

    unsupported = [c["type"] for c in checks if c.get("type") not in SUPPORTED_CHECKS]
    if unsupported:
        log.warning("unsupported_check_types", types=unsupported)
    return checks


# ------------------------------------------------------------------- terminal


@app.websocket("/labs/sessions/{session_id}/terminal")
async def terminal(websocket: WebSocket, session_id: uuid.UUID) -> None:
    """Relay the browser's terminal to the lab's TTY.

    The browser talks to this broker; the broker talks to the runtime. There is
    no path from a browser to a container, which is what makes handing someone a
    root shell acceptable.
    """
    cookie = websocket.cookies.get(SESSION_COOKIE)
    try:
        user_id = await _resolve_user(cookie)
        session = _manager.get(session_id, user_id)
    except (HTTPException, SessionNotFoundError):
        await websocket.close(code=4401, reason="not authorised for this lab")
        return

    attach = getattr(_provisioner, "attach", None)
    if attach is None:
        await websocket.close(code=4503, reason="this runtime has no terminal")
        return

    await websocket.accept()
    log.info("lab_terminal_attached", session_id=str(session_id))

    try:
        upstream = await attach(session.handle)
    except Exception:
        log.exception("lab_attach_failed", session_id=str(session_id))
        await websocket.close(code=4503, reason="could not attach to the lab")
        return

    # Ask readline to redraw. The shell is interactive but has not written a
    # prompt to the TTY, so a learner opening the lab would see an empty
    # rectangle and reasonably conclude the terminal is broken. Ctrl-L redraws
    # the current line without submitting it, which also restores the prompt
    # intact if they are reattaching mid-command — a bare newline would run
    # whatever they had half-typed.
    with contextlib.suppress(Exception):
        await upstream.write(b"")

    async def browser_to_lab() -> None:
        while True:
            data = await websocket.receive_text()
            await upstream.write(data.encode())

    async def lab_to_browser() -> None:
        while True:
            chunk = await upstream.read()
            if not chunk:
                # The TTY closed — the learner ran `exit`, or the container is
                # gone. Either way there is nothing left to relay.
                break
            # "replace" because a chunk boundary can land mid-character, and a
            # terminal that dies on a split multibyte sequence is worse than one
            # that shows a replacement glyph for a moment.
            await websocket.send_text(chunk.decode("utf-8", "replace"))

    async def enforce_ttl() -> None:
        """The terminal does not outlive the session, even mid-keystroke."""
        while not session.expired:
            await asyncio.sleep(5)
        await websocket.send_text("\r\n\r\n*** This lab has expired. ***\r\n")

    tasks = [
        asyncio.create_task(browser_to_lab()),
        asyncio.create_task(lab_to_browser()),
        asyncio.create_task(enforce_ttl()),
    ]
    try:
        _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
    except WebSocketDisconnect:
        pass
    finally:
        for task in tasks:
            task.cancel()
        await upstream.close()
        log.info("lab_terminal_detached", session_id=str(session_id))


app.include_router(router)

# After the routes exist: instrumentation wraps the middleware stack, and
# FastAPI refuses new middleware once the app has started.
instrument_app(app)
