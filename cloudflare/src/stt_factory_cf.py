from __future__ import annotations

from src.repo_bootstrap import bootstrap_backend_imports

bootstrap_backend_imports()

from app.stt import SttSession


async def create_stt_session(
    settings,
    *,
    recorder=None,
) -> SttSession:
    del recorder

    provider = getattr(settings, "stt_provider", "soniox")
    if provider != "soniox":
        raise ValueError(f"Unsupported hosted STT provider: {provider}")

    raise NotImplementedError("Cloudflare Soniox STT adapter is not implemented yet")
