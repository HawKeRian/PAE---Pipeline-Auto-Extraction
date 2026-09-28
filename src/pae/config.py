"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings with safe local-development defaults."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="PAE_", extra="ignore")

    app_name: str = "Pipeline Auto Extraction"
    environment: str = "development"
    log_level: str = "INFO"
    enable_mock_ui: bool = False
    model_path: Path | None = None
    ai_provider: str = "ollama"
    ai_model: str = "llama3.1:8b"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ai_timeout_seconds: float = 120
    data_dir: Path = Path("data")
    generated_dir: Path = Path("generated")
    database_path: Path | None = None
    queue_capacity: int = 20
    bootstrap_user_id: str = "local-admin"
    bootstrap_user_name: str = "Local Administrator"
    bootstrap_token: SecretStr | None = None
    max_upload_bytes: int = Field(default=50 * 1024 * 1024, ge=1)
    max_sample_rows: int = Field(default=100_000, ge=1, le=100_000)
    max_sample_columns: int = Field(default=1_000, ge=1, le=10_000)
    sample_retention_hours: int = Field(default=24, ge=1, le=720)
    database_allowed_hosts: str = ""
    database_allow_private_hosts: bool = False
    database_query_timeout_seconds: int = Field(default=30, ge=1, le=300)
    database_sample_rows: int = Field(default=10_000, ge=1, le=100_000)
    sandbox_timeout_seconds: float = Field(default=5, gt=0, le=30)
    sandbox_memory_mb: int = Field(default=256, ge=32, le=2_048)
    sandbox_cpu_seconds: float = Field(default=5, gt=0, le=30)
    sandbox_output_mb: int = Field(default=5, ge=1, le=100)
    rate_limit_requests: int = Field(default=300, ge=1, le=100_000)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3_600)
    readiness_require_model: bool = False
    readiness_model_timeout_seconds: float = Field(default=2, gt=0, le=30)
    alert_queue_depth: int = Field(default=15, ge=1, le=100_000)
    alert_webhook_url: SecretStr | None = None
    alert_webhook_timeout_seconds: float = Field(default=3, gt=0, le=30)
    alert_webhook_cooldown_seconds: float = Field(default=300, ge=0, le=86_400)
    structured_logging: bool = True

    @field_validator("bootstrap_token", "alert_webhook_url", mode="before")
    @classmethod
    def empty_secret_is_disabled(cls, value: object) -> object:
        """Allow documented blank secret values without creating invalid credentials."""

        return None if value == "" else value

    @field_validator("alert_webhook_url")
    @classmethod
    def alert_webhook_uses_tls(cls, value: SecretStr | None) -> SecretStr | None:
        """Require encrypted alert delivery because webhook URLs may embed credentials."""

        if value is not None and not value.get_secret_value().startswith("https://"):
            raise ValueError("alert_webhook_url must use https")
        return value

    @property
    def mock_ui_enabled(self) -> bool:
        """Allow the prototype only in explicitly non-production environments."""

        return self.enable_mock_ui and self.environment in {"development", "testing"}

    @property
    def resolved_database_path(self) -> Path:
        """Return an explicit database path or a local path below the data directory."""

        return self.database_path or self.data_dir / "pae.sqlite3"

    @property
    def sample_storage_path(self) -> Path:
        """Keep temporary uploaded samples below the configured data directory."""

        return self.data_dir / "samples"

    @property
    def sandbox_workspace_path(self) -> Path:
        """Keep disposable execution workspaces below the configured data directory."""

        return self.data_dir / "workspaces"

    @property
    def database_host_allowlist(self) -> tuple[str, ...]:
        """Return normalized exact hostnames configured for database egress."""

        return tuple(
            host.strip().lower() for host in self.database_allowed_hosts.split(",") if host.strip()
        )


@lru_cache
def get_settings() -> Settings:
    """Return one immutable-by-convention settings instance per process."""

    return Settings()
