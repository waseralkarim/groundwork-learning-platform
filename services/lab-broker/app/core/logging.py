"""Structured logging.

One formatter for everything. Logs emitted by our own code via structlog and
logs emitted by third-party libraries via the standard library both end up
rendered by the same processor chain, so the output stream is uniformly JSON in
production rather than JSON interleaved with plain text.

That uniformity is not cosmetic: a stream that is 90% JSON is, for a log
pipeline, an unparseable stream. The Observability track quotes this module.
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.core.telemetry import add_trace_context

# Applied to records from BOTH sources so a line from arq carries the same
# fields as a line from our own code.
SHARED_PROCESSORS: list[structlog.typing.Processor] = [
    structlog.contextvars.merge_contextvars,
    add_trace_context,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.UnicodeDecoder(),
]

# Libraries that install their own handlers. Left alone, each would write its own
# format directly to stdout, bypassing everything above.
NOISY_LIBRARY_LOGGERS = (
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "arq",
    "arq.worker",
    "alembic",
    "sqlalchemy.engine",
)


def configure_logging(level: str = "INFO", *, json_output: bool = True) -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)

    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    # ProcessorFormatter is the bridge: stdlib LogRecords get pushed through
    # foreign_pre_chain, structlog events arrive pre-processed, and both are
    # rendered by the same final processor.
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=SHARED_PROCESSORS,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    for name in NOISY_LIBRARY_LOGGERS:
        library_logger = logging.getLogger(name)
        library_logger.handlers.clear()
        library_logger.propagate = True

    structlog.configure(
        processors=[
            *SHARED_PROCESSORS,
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
