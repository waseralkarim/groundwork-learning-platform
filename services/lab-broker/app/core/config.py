"""Broker settings.

Deliberately minimal. The broker holds no database credentials and no secrets —
it authenticates learners by asking the API, and it stores session state in
memory. There is nothing here worth stealing, which is the point.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    groundwork_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # Where to verify a learner's session cookie. The broker makes no
    # authorisation decisions of its own beyond quota.
    api_internal_url: str = "http://api:8000"

    # "docker" for a real runtime, "fake" for tests and for running the broker
    # before a container runtime is available.
    provisioner: Literal["docker", "fake"] = "docker"
    docker_socket: str = "/var/run/docker.sock"

    # Telemetry. Unset means inert — see app/core/telemetry.py.
    otel_exporter_otlp_endpoint: str | None = None
    otel_service_name: str = "groundwork-lab-broker"

    @property
    def is_production(self) -> bool:
        return self.groundwork_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
