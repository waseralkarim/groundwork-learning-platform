"""OpenTelemetry wiring.

Off unless `OTEL_EXPORTER_OTLP_ENDPOINT` is set, which means the default
`docker compose up` has no collector, no exporters and no background threads
trying to reach a host that is not there. Starting the observability profile
sets the variable and everything begins reporting — nothing else changes.

Traces, metrics and logs are deliberately joined on `trace_id`: the logging
processor below copies the active span's ids into every log line, so a slow
request found on a dashboard leads to its trace, and the trace leads to the
exact log lines that request produced. A platform that teaches this and does not
do it would not be worth reading.
"""

from __future__ import annotations

import logging

import structlog
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_configured = False
_logger_provider = None


def add_trace_context(_logger: object, _name: str, event: dict) -> dict:
    """structlog processor: stamp every line with the active span's ids.

    This is the join key for the whole observability story. Without it, logs and
    traces are two piles of data about the same incident that nobody can line up.
    """
    span = trace.get_current_span()
    context = span.get_span_context()
    if context.is_valid:
        event["trace_id"] = format(context.trace_id, "032x")
        event["span_id"] = format(context.span_id, "016x")
    return event


def _configure_logs(resource: Resource, endpoint: str) -> None:
    """Ship logs over OTLP as well as to stdout.

    Both, deliberately. stdout stays the source of truth — `docker compose logs`
    must keep working, and a log pipeline that only exists inside the
    observability profile is one that fails silently when the profile is off.
    This adds a second destination so Loki can join a log line to the trace it
    came from.
    """
    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

    global _logger_provider
    provider = LoggerProvider(resource=resource)
    provider.add_log_record_processor(
        BatchLogRecordProcessor(OTLPLogExporter(endpoint=endpoint, insecure=True))
    )
    set_logger_provider(provider)
    _logger_provider = provider


def attach_log_handler() -> None:
    """Add the OTLP handler to the root logger.

    Separate from configure_telemetry, and called *after* configure_logging,
    because that function clears root.handlers to take ownership of the output
    format. Attaching before it means the handler is silently discarded and logs
    never leave the process — which looks exactly like a broken collector.
    """
    if _logger_provider is None:
        return
    from opentelemetry.sdk._logs import LoggingHandler

    logging.getLogger().addHandler(
        LoggingHandler(level=logging.INFO, logger_provider=_logger_provider)
    )


def configure_telemetry(
    service_name: str, endpoint: str | None, environment: str = "development"
) -> bool:
    """Set up providers and exporters. Returns whether telemetry is on.

    Idempotent: calling it twice does nothing the second time, because the API
    process and its test client both reach this path.
    """
    global _configured
    if _configured or not endpoint:
        return _configured

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": "0.1.0",
            "deployment.environment": environment,
        }
    )

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
    )
    trace.set_tracer_provider(tracer_provider)

    metrics.set_meter_provider(
        MeterProvider(
            resource=resource,
            metric_readers=[
                PeriodicExportingMetricReader(
                    OTLPMetricExporter(endpoint=endpoint, insecure=True),
                    export_interval_millis=15000,
                )
            ],
        )
    )

    _configure_logs(resource, endpoint)

    _configured = True
    return True


def instrument_app(app: object) -> None:
    """Instrument FastAPI, SQLAlchemy and httpx if telemetry is configured.

    Imported lazily so the packages are only touched when they are wanted, and
    each guarded separately: a version skew in one instrumentation must not take
    the whole application down at import time. Telemetry that can crash the
    service it observes is a liability, not an asset.
    """
    if not _configured:
        return

    log = structlog.get_logger(__name__)

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(
            app,
            # Health checks are 90% of the span volume and 0% of the value.
            excluded_urls="health,healthz,metrics",
        )
    except Exception:
        log.warning("otel_fastapi_instrumentation_failed", exc_info=True)

    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        from app.db.session import get_engine

        SQLAlchemyInstrumentor().instrument(engine=get_engine().sync_engine)
    except Exception:
        log.warning("otel_sqlalchemy_instrumentation_failed", exc_info=True)

    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
    except Exception:
        log.warning("otel_httpx_instrumentation_failed", exc_info=True)


__all__ = [
    "add_trace_context",
    "attach_log_handler",
    "configure_telemetry",
    "instrument_app",
]
