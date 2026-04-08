from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def build_batch_id(now: datetime | None = None) -> str:
    timestamp = (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H-%M-%SZ")
    return f"{timestamp}-{secrets.token_hex(4)}"


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def config_fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return _sha256_bytes(canonical)


def build_experiment_metadata(
    *,
    suite: str,
    dataset_name: str,
    dataset_path: Path,
    evaluators_path: Path,
    experiment_id: str,
    model_name: str,
    prompt_sha: str,
    repeat: int,
    task_retries: int,
    batch_id: str,
    full_config: dict[str, Any],
) -> dict[str, Any]:
    return {
        "suite": suite,
        "dataset_name": dataset_name,
        "dataset_sha": _sha256_bytes(dataset_path.read_bytes()),
        "evaluator_contract_sha": _sha256_bytes(evaluators_path.read_bytes()),
        "experiment_id": experiment_id,
        "model_name": model_name,
        "prompt_sha": prompt_sha,
        "config_fingerprint": config_fingerprint(full_config),
        "repeat": repeat,
        "task_retries": task_retries,
        "batch_id": batch_id,
    }
