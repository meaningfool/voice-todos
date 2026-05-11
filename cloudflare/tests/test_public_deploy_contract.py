from __future__ import annotations

import json
from pathlib import Path


WRANGLER_CONFIG = Path(__file__).resolve().parents[1] / "wrangler.jsonc"


def _load_wrangler_config() -> dict:
    return json.loads(WRANGLER_CONFIG.read_text())


def test_required_secrets_only_include_provider_api_keys() -> None:
    config = _load_wrangler_config()

    assert config["secrets"]["required"] == [
        "SONIOX_API_KEY",
        "GEMINI_API_KEY",
        "MISTRAL_API_KEY",
    ]


def test_workers_dev_is_disabled_for_public_domain_deploys() -> None:
    config = _load_wrangler_config()

    assert config["workers_dev"] is False
