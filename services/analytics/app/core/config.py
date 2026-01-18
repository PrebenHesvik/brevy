"""Application configuration using Pydantic Settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Brevy Analytics"
    app_version: str = "0.1.0"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8001

    # Database (analytics schema)
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/brevy"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_channel: str = "brevy:clicks"

    # GeoIP
    geoip_database_path: str = ""

    # Observability
    sentry_dsn: str = ""
    otlp_endpoint: str = ""


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
