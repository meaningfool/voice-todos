from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
for candidate in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.logfire_setup import (
    get_logfire_api_url,
    get_logfire_project_name,
    get_logfire_read_token,
    has_logfire_write_credentials,
)
from evals.logfire_query import DEFAULT_LOGFIRE_QUERY_URL, normalize_benchmark_rows


def validation_warning() -> str | None:
    if not has_logfire_write_credentials():
        return (
            "requires LOGFIRE_TOKEN via env/backend/.env or "
            "backend/.logfire/logfire_credentials.json"
        )
    if not get_logfire_read_token():
        return "requires LOGFIRE_READ_TOKEN via env or backend/.env"
    if not get_logfire_project_name():
        return (
            "requires LOGFIRE_PROJECT_NAME via env, backend/.env, or "
            "backend/.logfire/logfire_credentials.json"
        )
    return None


def query_url() -> str:
    api_url = get_logfire_api_url()
    if not api_url:
        return DEFAULT_LOGFIRE_QUERY_URL
    return api_url.rstrip("/") + "/v1/query"


def emit_environment_record(*, environment: str, validation_tag: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["LOGFIRE_ENVIRONMENT"] = environment
    code = """
from app.logfire_setup import configure_logfire
import logfire

configure_logfire(environment={environment!r})
logfire.info(
    "environment tagging validation",
    marker={validation_tag!r},
    _tags=["environment-tagging-validation", {validation_tag!r}],
)
logfire.force_flush()
logfire.shutdown()
""".strip().format(environment=environment, validation_tag=validation_tag)
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def fetch_environment_rows(*, validation_tag: str) -> list[dict]:
    response = httpx.get(
        query_url(),
        params={
            "sql": (
                "SELECT deployment_environment, tags, start_timestamp "
                "FROM records "
                f"WHERE array_has(tags, '{validation_tag}') "
                "ORDER BY start_timestamp DESC "
                "LIMIT 20"
            ),
            "row_oriented": "true",
            "project_name": get_logfire_project_name(),
        },
        headers={
            "Authorization": f"Bearer {get_logfire_read_token()}",
            "Accept": "application/json",
        },
        timeout=30.0,
    )
    response.raise_for_status()
    return normalize_benchmark_rows(response.json())


def main() -> int:
    warning = validation_warning()
    if warning is not None:
        print(f"WARN: {warning}")
        return 0

    suffix = uuid.uuid4().hex[:8]
    dev_environment = f"env-tag-dev-{suffix}"
    prod_environment = f"env-tag-prod-{suffix}"
    validation_tag = f"environment-tagging-validation-{suffix}"

    dev = emit_environment_record(
        environment=dev_environment,
        validation_tag=validation_tag,
    )
    if dev.returncode != 0:
        print(
            "FAIL: could not emit development environment record\n"
            f"stdout:\n{dev.stdout}\n"
            f"stderr:\n{dev.stderr}"
        )
        return 1

    prod = emit_environment_record(
        environment=prod_environment,
        validation_tag=validation_tag,
    )
    if prod.returncode != 0:
        print(
            "FAIL: could not emit production environment record\n"
            f"stdout:\n{prod.stdout}\n"
            f"stderr:\n{prod.stderr}"
        )
        return 1

    deadline = time.time() + 30
    last_rows: list[dict] = []
    while time.time() < deadline:
        last_rows = fetch_environment_rows(validation_tag=validation_tag)
        found = {
            row.get("deployment_environment")
            for row in last_rows
            if isinstance(row.get("deployment_environment"), str)
        }
        if {dev_environment, prod_environment}.issubset(found):
            print(
                "PASS: environment tagging is queryable in Logfire for "
                f"{dev_environment} and {prod_environment}"
            )
            return 0
        time.sleep(2)

    print(
        "FAIL: environment tagging records did not become queryable in Logfire\n"
        f"expected: {dev_environment}, {prod_environment}\n"
        f"rows: {last_rows}"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
