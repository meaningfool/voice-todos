from __future__ import annotations

from functools import lru_cache

from settings import CloudflareSettings
from settings import get_settings as get_cloudflare_settings

Settings = CloudflareSettings


@lru_cache
def get_settings() -> Settings:
    return get_cloudflare_settings()
