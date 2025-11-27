"""Application configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str = "sqlite:///./routeintel.db"

    # API
    api_v1_prefix: str = "/api/v1"
    debug: bool = True

    # App
    app_name: str = "RouteIntel"
    app_version: str = "0.1.0"


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()
