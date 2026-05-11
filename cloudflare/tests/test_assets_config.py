from __future__ import annotations

from pathlib import Path


WRANGLER_CONFIG = Path(__file__).resolve().parents[1] / "wrangler.jsonc"


def test_wrangler_config_serves_public_assets_with_spa_fallback() -> None:
    text = WRANGLER_CONFIG.read_text()

    assert '"directory": "./public"' in text
    assert '"binding": "ASSETS"' in text
    assert '"not_found_handling": "single-page-application"' in text


def test_wrangler_config_runs_worker_first_for_ws() -> None:
    text = WRANGLER_CONFIG.read_text()

    assert '"run_worker_first": ["/ws"]' in text
