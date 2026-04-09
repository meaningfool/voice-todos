from __future__ import annotations

import httpx

from app.logfire_setup import get_logfire_project_name, get_logfire_read_token
from evals.benchmarking.models import AttachedExperimentRef

LOGFIRE_QUERY_URL = "https://logfire-api.pydantic.dev/v1/query"


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
  attributes->>'experiment_run_id' AS experiment_run_id,
  attributes->>'experiment_id' AS experiment_id,
  attributes->>'batch_id' AS batch_id,
  attributes->>'suite' AS suite,
  attributes->>'dataset_sha' AS dataset_sha,
  attributes->>'evaluator_contract_sha' AS evaluator_contract_sha,
  attributes->>'model_name' AS model_name,
  attributes->>'prompt_sha' AS prompt_sha
FROM records
WHERE attributes->>'experiment_run_id' IN ({run_ids})
LIMIT {len(attachments)}
""".strip()


def _normalize_query_rows(payload: object) -> list[dict[str, str]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]

    if isinstance(payload, dict):
        rows = payload.get("rows")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]

    raise RuntimeError("Unexpected Logfire query response format")


class LogfireBenchmarkQueryClient:
    def __init__(
        self,
        *,
        read_token: str | None = None,
        project_name: str | None = None,
        query_url: str = LOGFIRE_QUERY_URL,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.read_token = read_token or get_logfire_read_token()
        self.project_name = project_name or get_logfire_project_name()
        self.query_url = query_url
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
            "limit": str(len(attachments)),
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
