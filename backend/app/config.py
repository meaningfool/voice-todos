from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    stt_provider: str = "soniox"
    soniox_api_key: str
    gemini_api_key: str
    google_cloud_project_id: str | None = None
    mistral_api_key: str | None = None
    record_sessions: bool = False
    stop_timeout_seconds: float = Field(
        default=30.0,
        validation_alias=AliasChoices(
            "STOP_TIMEOUT_SECONDS",
            "SONIOX_STOP_TIMEOUT_SECONDS",
        ),
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # ty: ignore[missing-argument]
