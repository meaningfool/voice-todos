from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    soniox_api_key: str
    gemini_api_key: str
    record_sessions: bool = False
    soniox_stop_timeout_seconds: float = 30.0

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache
def get_settings() -> Settings:
    return Settings()
