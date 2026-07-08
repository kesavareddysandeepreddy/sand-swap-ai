"""
Global application settings.

All configuration must be accessed through this module.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    app_name: str = Field(default="SandSwap AI")
    app_version: str = Field(default="0.1.0")
    environment: str = Field(default="development")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
