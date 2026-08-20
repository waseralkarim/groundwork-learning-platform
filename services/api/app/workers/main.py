"""Worker entrypoint.

Deliberately not the `arq` CLI. That CLI applies its own `dictConfig` after our
modules are imported, which both overrides our structlog setup and attaches a
second handler — so every line was emitted twice, once structured and once not.
Calling `run_worker` directly leaves logging configuration ours alone.
"""

from __future__ import annotations

from arq import run_worker

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.workers.settings import WorkerSettings


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, json_output=settings.groundwork_env != "development")
    get_logger(__name__).info("worker_entrypoint", environment=settings.groundwork_env)
    run_worker(WorkerSettings)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
