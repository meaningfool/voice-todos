from __future__ import annotations

import httpx

from app.logfire_setup import (
    get_logfire_api_url,
    get_logfire_project_name,
    get_logfire_read_token,
)

from evals.models import EntryQuerySelector

DEFAULT_LOGFIRE_QUERY_URL = "https://logfire-api.pydantic.dev/v1/query"


def _sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def build_candidate_runs_query(selectors: list[EntryQuerySelector]) -> str:
    conditions = []
    for selector in selectors:
        conditions.append(
            "("
            f"attributes->'metadata'->>'suite' = {_sql_quote(selector.suite)} "
            f"AND attributes->'metadata'->>'dataset_sha' = {_sql_quote(selector.dataset_sha)} "
            f"AND attributes->'metadata'->>'evaluator_contract_sha' = {_sql_quote(selector.evaluator_contract_sha)} "
            f"AND attributes->'metadata'->>'model_name' = {_sql_quote(selector.model_name)} "
            f"AND attributes->'metadata'->>'prompt_sha' = {_sql_quote(selector.prompt_sha)} "
            f"AND attributes->'metadata'->>'config_fingerprint' = {_sql_quote(selector.config_fingerprint)} "
            f"AND attributes->'metadata'->>'repeat' = {_sql_quote(str(selector.repeat))} "
            f"AND attributes->'metadata'->>'task_retries' = {_sql_quote(str(selector.task_retries))}"
            ")"
        )
    where_clause = " OR ".join(conditions) if conditions else "FALSE"

    return f"""
SELECT
  start_timestamp,
  attributes->'metadata'->>'experiment_run_id' AS experiment_run_id,
  attributes->'metadata'->>'suite' AS suite,
  attributes->'metadata'->>'dataset_sha' AS dataset_sha,
  attributes->'metadata'->>'evaluator_contract_sha' AS evaluator_contract_sha,
  attributes->'metadata'->>'model_name' AS model_name,
  attributes->'metadata'->>'prompt_sha' AS prompt_sha,
  attributes->'metadata'->>'config_fingerprint' AS config_fingerprint,
  attributes->'metadata'->>'repeat' AS repeat,
  attributes->'metadata'->>'task_retries' AS task_retries
FROM records
WHERE {where_clause}
ORDER BY start_timestamp DESC
LIMIT 200
""".strip()


def normalize_benchmark_rows(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        rows = payload.get("rows")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
        columns = payload.get("columns")
        if isinstance(columns, list):
            return _rows_from_columnar_payload(columns)
    raise RuntimeError("Unexpected Logfire query response format")


def _rows_from_columnar_payload(columns: list[object]) -> list[dict]:
    named_columns: list[tuple[str, list[object]]] = []
    row_count = 0
    for column in columns:
        if not isinstance(column, dict):
            continue
        name = column.get("name")
        values = column.get("values")
        if not isinstance(name, str) or not isinstance(values, list):
            continue
        named_columns.append((name, values))
        row_count = max(row_count, len(values))

    rows: list[dict] = []
    for row_index in range(row_count):
        row = {}
        for name, values in named_columns:
            row[name] = values[row_index] if row_index < len(values) else None
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
    ) -> None:
        self.read_token = read_token or get_logfire_read_token()
        self.project_name = project_name or get_logfire_project_name()
        self.query_url = query_url or _default_query_url()
        self.timeout = timeout

    def fetch_candidate_runs(
        self,
        selectors: list[EntryQuerySelector],
    ) -> list[dict]:
        if not selectors:
            return []
        if not self.read_token:
            raise RuntimeError("LOGFIRE_READ_TOKEN is required for benchmark reporting")

        response = httpx.get(
            self.query_url,
            params={
                "sql": build_candidate_runs_query(selectors),
                "row_oriented": "true",
                **(
                    {"project_name": self.project_name}
                    if self.project_name
                    else {}
                ),
            },
            headers={
                "Authorization": f"Bearer {self.read_token}",
                "Accept": "application/json",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return normalize_benchmark_rows(response.json())


def _default_query_url() -> str:
    api_url = get_logfire_api_url()
    if not api_url:
        return DEFAULT_LOGFIRE_QUERY_URL
    return api_url.rstrip("/") + "/v1/query"
