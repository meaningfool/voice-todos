from __future__ import annotations

import hashlib
import json
from pathlib import Path

from logfire.experimental.api_client import LogfireAPIClient

from app.backend_env import BACKEND_ROOT, read_backend_env_var
from app.logfire_setup import get_logfire_api_url


def _read_logfire_credentials_token() -> str | None:
    credentials_path = BACKEND_ROOT / ".logfire" / "logfire_credentials.json"
    if not credentials_path.exists():
        return None
    try:
        credentials = json.loads(credentials_path.read_text())
    except json.JSONDecodeError:
        return None
    token = credentials.get("token")
    return token if isinstance(token, str) and token else None


def get_logfire_datasets_api_key() -> str | None:
    return (
        read_backend_env_var("LOGFIRE_DATASETS_TOKEN")
        or read_backend_env_var("LOGFIRE_TOKEN")
        or _read_logfire_credentials_token()
    )


def build_logfire_api_client() -> LogfireAPIClient:
    api_key = get_logfire_datasets_api_key()
    if not api_key:
        raise RuntimeError(
            "A dataset-scoped Logfire API key is required for hosted dataset access"
        )
    return LogfireAPIClient(
        api_key=api_key,
        base_url=get_logfire_api_url(),
    )


def export_hosted_dataset(dataset_id: str) -> dict:
    client = build_logfire_api_client()
    exported = client.export_dataset(dataset_id)
    if not isinstance(exported, dict):
        raise RuntimeError("Unexpected hosted dataset payload")
    return exported


def serialize_dataset_payload(payload: dict) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def canonical_dataset_hash(payload: dict) -> str:
    return hashlib.sha256(serialize_dataset_payload(payload)).hexdigest()
