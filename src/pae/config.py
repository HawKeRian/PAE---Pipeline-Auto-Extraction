"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings with safe local-development defaults."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="PAE_", extra="ignore")

    app_name: str = "Pipeline Auto Extraction"
    environment: str = "development"
    log_level: str = "INFO"
    model_path: Path | None = None
    data_dir: Path = Path("data")
    generated_dir: Path = Path("generated")


@lru_cache
def get_settings() -> Settings:
    """Return one immutable-by-convention settings instance per process."""

    return Settings()
