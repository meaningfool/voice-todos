from __future__ import annotations

import httpx

from app.logfire_setup import (
    get_logfire_api_url,
    get_logfire_project_name,
    get_logfire_read_token,
)
from evals.benchmarking.models import AttachedExperimentRef

DEFAULT_LOGFIRE_QUERY_URL = "https://logfire-api.pydantic.dev/v1/query"


def _sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _build_attached_experiments_query(
    attachments: list[AttachedExperimentRef],
) -> str:
    run_ids = ", ".join(
        _sql_quote(attachment.experiment_run_id)
        for attachment in attachments
    )

    return f"""
SELECT
  start_timestamp,
  attributes->'metadata'->>'experiment_run_id' AS experiment_run_id,
  attributes->'metadata'->>'experiment_id' AS experiment_id,
  attributes->'metadata'->>'batch_id' AS batch_id,
  attributes->'metadata'->>'suite' AS suite,
  attributes->'metadata'->>'dataset_sha' AS dataset_sha,
  attributes->'metadata'->>'evaluator_contract_sha' AS evaluator_contract_sha,
  attributes->'metadata'->>'model_name' AS model_name,
  attributes->'metadata'->>'prompt_sha' AS prompt_sha
FROM records
WHERE attributes->'metadata'->>'experiment_run_id' IN ({run_ids})
ORDER BY start_timestamp DESC
""".strip()


def _normalize_query_rows(payload: object) -> list[dict[str, str]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]

    if isinstance(payload, dict):
        rows = payload.get("rows")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]

        columns = payload.get("columns")
        if isinstance(columns, list):
            return _columns_to_rows(columns)

    raise RuntimeError("Unexpected Logfire query response format")


def _columns_to_rows(columns: list[object]) -> list[dict[str, str]]:
    normalized_columns: list[tuple[str, list[object]]] = []
    row_count = 0

    for column in columns:
        if not isinstance(column, dict):
            continue

        name = column.get("name")
        values = column.get("values")
        if not isinstance(name, str) or not isinstance(values, list):
            continue

        normalized_columns.append((name, values))
        row_count = max(row_count, len(values))

    rows: list[dict[str, str]] = []
    for index in range(row_count):
        row: dict[str, str] = {}
        for name, values in normalized_columns:
            value = values[index] if index < len(values) else None
            row[name] = value
        rows.append(row)

    return rows


class LogfireBenchmarkQueryClient:
    def __init__(
        self,
        *,
        read_token: str | None = None,
        project_name: str | None = None,
        query_url: str | None = None,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.read_token = read_token or get_logfire_read_token()
        self.project_name = project_name or get_logfire_project_name()
        self.query_url = query_url or _default_query_url()
        self.timeout = timeout
        self.transport = transport

    async def fetch_attached_experiments(
        self,
        attachments: list[AttachedExperimentRef],
    ) -> list[dict[str, str]]:
        if not attachments:
            return []

        if not self.read_token:
            raise RuntimeError("LOGFIRE_READ_TOKEN is required for benchmark reporting")

        sql = _build_attached_experiments_query(attachments)
        headers = {
            "Authorization": f"Bearer {self.read_token}",
            "Accept": "application/json",
        }
        params = {
            "sql": sql,
            "row_oriented": "true",
        }
        if self.project_name:
            params["project_name"] = self.project_name

        async with httpx.AsyncClient(
            timeout=self.timeout,
            transport=self.transport,
        ) as client:
            response = await client.get(
                self.query_url,
                params=params,
                headers=headers,
            )
            response.raise_for_status()

        return _normalize_query_rows(response.json())


def _default_query_url() -> str:
    api_url = get_logfire_api_url()
    if not api_url:
        return DEFAULT_LOGFIRE_QUERY_URL
    return api_url.rstrip("/") + "/v1/query"
