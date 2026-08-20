"""OpenTelemetry wiring for the lab broker.

Same contract as the API's: inert unless an OTLP endpoint is configured, so the
default `--profile labs` run has no exporters and no background threads.

The metrics here are the ones that decide whether the lab plane is healthy.
`lab_provision_duration_seconds` is the one to watch: a slow lab start is the
single most reliable way to lose a learner, and it degrades gradually — image
pulls getting slower, the runtime under pressure — so it is invisible without a
percentile on a graph.
"""

from __future__ import annotations

import logging
from functools import cache

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

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
    )
    trace.set_tracer_provider(provider)

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
    if not _configured:
        return
    log = structlog.get_logger(__name__)
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app, excluded_urls="health")
    except Exception:
        log.warning("otel_fastapi_instrumentation_failed", exc_info=True)


# ------------------------------------------------------------------- metrics


@cache
def _meter() -> metrics.Meter:
    return metrics.get_meter("groundwork.lab_broker")


@cache
def _provision_duration() -> metrics.Histogram:
    return _meter().create_histogram(
        "lab_provision_duration_seconds",
        unit="s",
        description="Time from session request to an attachable container",
    )


@cache
def _session_duration() -> metrics.Histogram:
    return _meter().create_histogram(
        "lab_session_duration_seconds",
        unit="s",
        description="How long lab sessions actually last, versus their TTL",
    )


@cache
def _sessions_total() -> metrics.Counter:
    return _meter().create_counter(
        "lab_sessions_total",
        description="Sessions created, labelled by lab and outcome",
    )


@cache
def _check_results() -> metrics.Counter:
    return _meter().create_counter(
        "lab_check_results_total",
        description="Step verifications, labelled by pass or fail",
    )


def record_provision(seconds: float, lab: str, *, ok: bool) -> None:
    _provision_duration().record(seconds, {"lab": lab})
    _sessions_total().add(1, {"lab": lab, "outcome": "created" if ok else "failed"})


def record_session_ended(seconds: float, lab: str, reason: str) -> None:
    _session_duration().record(seconds, {"lab": lab, "reason": reason})


def record_check(lab: str, step: str, *, passed: bool) -> None:
    # Aggregated per step, because a step that nearly everyone fails is an
    # instruction problem rather than a learner problem — and that is only
    # visible with the step in the labels.
    _check_results().add(1, {"lab": lab, "step": step, "passed": str(passed).lower()})


__all__ = [
    "add_trace_context",
    "attach_log_handler",
    "configure_telemetry",
    "instrument_app",
    "record_check",
    "record_provision",
    "record_session_ended",
]
