from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_bootstrap_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "bootstrap_logfire_hosted_datasets.py"
    spec = importlib.util.spec_from_file_location("bootstrap_logfire_hosted_datasets", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bootstrap_converts_canonical_rows_to_logfire_cases():
    module = _load_bootstrap_module()
    payload = {
        "name": "todo_extraction",
        "version": "v1",
        "rows": [
            {
                "id": "case-a",
                "input": {"transcript": "hello"},
                "expected_output": [{"text": "Call Mom"}],
                "metadata": {"source_fixture": "fixture-a"},
            }
        ],
    }

    cases = module.dataset_rows_to_logfire_cases(payload)

    assert cases == [
        {
            "name": "case-a",
            "inputs": {"transcript": "hello"},
            "expected_output": {"todos": [{"text": "Call Mom"}]},
            "metadata": {"source_fixture": "fixture-a"},
        }
    ]


def test_bootstrap_can_patch_benchmark_yaml_with_returned_dataset_ids(tmp_path):
    module = _load_bootstrap_module()
    benchmark_path = tmp_path / "benchmark.yaml"
    benchmark_path.write_text(
        "\n".join(
            [
                "benchmark_id: extraction_llm_matrix_v1",
                "hosted_dataset: ds_placeholder",
                "dataset_family: extraction",
                "focus: model",
                "headline_metric: todo_count_match",
                "repeat: 1",
                "task_retries: 1",
                "max_concurrency: 1",
                "entries: []",
            ]
        )
    )

    module.update_benchmark_hosted_dataset_id(
        benchmark_path=benchmark_path,
        dataset_id="ds_real_123",
    )

    contents = benchmark_path.read_text()
    assert "hosted_dataset: ds_real_123" in contents
    assert "dataset_family: extraction" in contents


def test_sync_hosted_dataset_reuses_existing_dataset_and_upserts_cases():
    module = _load_bootstrap_module()

    class FakeClient:
        def __init__(self):
            self.created = []
            self.added = []

        def list_datasets(self):
            return [{"id": "ds_existing", "name": "todo_extraction_v1"}]

        def create_dataset(self, name, **kwargs):
            self.created.append((name, kwargs))
            return {"id": "ds_created", "name": name}

        def add_cases(self, dataset_id_or_name, cases, **kwargs):
            self.added.append((dataset_id_or_name, cases, kwargs))
            return []

    client = FakeClient()
    payload = {
        "name": "todo_extraction",
        "version": "v1",
        "rows": [
            {
                "id": "case-a",
                "input": {"transcript": "hello"},
                "expected_output": [],
                "metadata": {},
            }
        ],
    }

    dataset = module.sync_hosted_dataset(
        client=client,
        dataset_name="todo_extraction_v1",
        dataset_payload=payload,
    )

    assert dataset["id"] == "ds_existing"
    assert client.created == []
    assert client.added[0][0] == "ds_existing"
    assert client.added[0][1][0]["name"] == "case-a"


def test_dataset_api_error_message_mentions_dataset_scopes():
    module = _load_bootstrap_module()

    message = module.dataset_api_error_message("API error 401: {'detail': 'Could not validate credentials'}")

    assert "dataset-scoped Logfire API key" in message
    assert "LOGFIRE_DATASETS_TOKEN" in message
