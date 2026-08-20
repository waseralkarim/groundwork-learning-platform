"""Application settings.

Every value comes from the environment. There are no defaults here that would be
valid in production — if a secret is missing the process refuses to start, which
is the behaviour we want and the behaviour the security track teaches.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    # -- general ------------------------------------------------------------
    groundwork_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    project_name: str = "Groundwork"
    api_v1_prefix: str = "/v1"

    # -- security -----------------------------------------------------------
    secret_key: str = Field(min_length=16)
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    # -- postgres -----------------------------------------------------------
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "db"
    postgres_port: int = 5432

    # -- valkey -------------------------------------------------------------
    valkey_host: str = "cache"
    valkey_port: int = 6379

    # -- content ------------------------------------------------------------
    content_dir: str = "/content"

    # -- telemetry ----------------------------------------------------------
    # Unset means no collector, no exporters, no background threads. The
    # observability profile sets it; nothing else has to change.
    otel_exporter_otlp_endpoint: str | None = None
    otel_service_name: str = "groundwork-api"

    @computed_field
    @property
    def database_url(self) -> str:
        """Async DSN used by the application."""
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.postgres_user,
                password=self.postgres_password,
                host=self.postgres_host,
                port=self.postgres_port,
                path=self.postgres_db,
            )
        )

    @computed_field
    @property
    def valkey_url(self) -> str:
        return f"redis://{self.valkey_host}:{self.valkey_port}/0"

    @computed_field
    @property
    def is_production(self) -> bool:
        return self.groundwork_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
