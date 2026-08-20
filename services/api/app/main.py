"""Groundwork API application."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.telemetry import attach_log_handler, configure_telemetry, instrument_app
from app.db.session import dispose_engine

settings = get_settings()

# Before logging, so the first line the process emits already carries trace
# context when telemetry is on.
telemetry_on = configure_telemetry(
    settings.otel_service_name,
    settings.otel_exporter_otlp_endpoint,
    settings.groundwork_env,
)
configure_logging(settings.log_level, json_output=settings.groundwork_env != "development")
# After configure_logging, which clears root.handlers.
attach_log_handler()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    log.info("api_starting", environment=settings.groundwork_env, telemetry=telemetry_on)
    yield
    await dispose_engine()
    log.info("api_stopped")


app = FastAPI(
    title="Groundwork API",
    description="Content, progress and assessment for the Groundwork learning platform.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
    openapi_url="/openapi.json",
)


# After construction: instrumentation wraps the app's middleware stack, and
# FastAPI will not accept new middleware once it has started.
instrument_app(app)


@app.middleware("http")
async def request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Bind a request id to every log line and time the request.

    Every log emitted downstream carries request_id, which is what makes the
    logs actually joinable once they land in Loki.
    """
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )

    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        log.exception("request_failed", duration_ms=elapsed_ms)
        raise

    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers["x-request-id"] = request_id

    # Health checks poll constantly; logging them at INFO buries everything else.
    level = log.debug if request.url.path.startswith("/v1/health") else log.info
    level("request_completed", status_code=response.status_code, duration_ms=duration_ms)
    return response


app.include_router(api_router, prefix=settings.api_v1_prefix)
