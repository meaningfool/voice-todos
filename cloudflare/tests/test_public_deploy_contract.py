from __future__ import annotations

import json
import tomllib
from pathlib import Path


WRANGLER_CONFIG = Path(__file__).resolve().parents[1] / "wrangler.jsonc"
PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _load_wrangler_config() -> dict:
    return json.loads(WRANGLER_CONFIG.read_text())


def _load_pyproject() -> dict:
    return tomllib.loads(PYPROJECT.read_text())


def test_required_secrets_only_include_provider_api_keys() -> None:
    config = _load_wrangler_config()

    assert config["secrets"]["required"] == ["SONIOX_API_KEY", "GEMINI_API_KEY"]


def test_runtime_dependencies_exclude_deferred_bundle_families() -> None:
    pyproject = _load_pyproject()

    dependencies = pyproject["project"]["dependencies"]

    assert not any(dependency.startswith("logfire") for dependency in dependencies)
    assert not any(dependency.startswith("mistralai") for dependency in dependencies)


def test_workers_dev_is_disabled_for_public_domain_deploys() -> None:
    config = _load_wrangler_config()

    assert config["workers_dev"] is False
