from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
from logfire.experimental.api_client import DatasetApiError

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
for candidate in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from evals.hosted_datasets import build_logfire_api_client

DATASET_BOOTSTRAP_TARGETS = (
    {
        "dataset_path": REPO_ROOT / "evals/datasets/extraction/todo_extraction_v1.json",
        "benchmark_path": REPO_ROOT / "evals/benchmarks/extraction_llm_matrix_v1.yaml",
    },
    {
        "dataset_path": REPO_ROOT / "evals/datasets/replay/todo_extraction_replay_v1.json",
        "benchmark_path": REPO_ROOT / "evals/benchmarks/replay_llm_matrix_v1.yaml",
    },
)


def load_canonical_dataset(path: Path) -> dict:
    return json.loads(path.read_text())


def hosted_dataset_name(dataset_payload: dict) -> str:
    return f"{dataset_payload['name']}_{dataset_payload['version']}"


def dataset_rows_to_logfire_cases(dataset_payload: dict) -> list[dict]:
    return [
        {
            "name": row["id"],
            "inputs": row["input"],
            "expected_output": {"todos": row["expected_output"]},
            "metadata": row.get("metadata", {}),
        }
        for row in dataset_payload.get("rows", [])
    ]


def sync_hosted_dataset(
    *,
    client,
    dataset_name: str,
    dataset_payload: dict,
) -> dict:
    existing = next(
        (dataset for dataset in client.list_datasets() if dataset.get("name") == dataset_name),
        None,
    )
    dataset = existing or client.create_dataset(
        dataset_name,
        description=f"Bootstrapped from canonical local dataset {dataset_name}",
    )
    client.add_cases(
        dataset.get("id") or dataset_name,
        dataset_rows_to_logfire_cases(dataset_payload),
        on_conflict="update",
    )
    return dataset


def update_benchmark_hosted_dataset_id(*, benchmark_path: Path, dataset_id: str) -> None:
    payload = yaml.safe_load(benchmark_path.read_text())
    payload["hosted_dataset"] = dataset_id
    benchmark_path.write_text(yaml.safe_dump(payload, sort_keys=False))


def dataset_api_error_message(error: str) -> str:
    return (
        "Hosted dataset bootstrap requires a dataset-scoped Logfire API key. "
        "Provide LOGFIRE_DATASETS_TOKEN, or a LOGFIRE_TOKEN / .logfire credential "
        "that includes dataset scopes. Original error: "
        f"{error}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bootstrap Logfire hosted datasets from canonical local JSON datasets.",
    )
    parser.add_argument(
        "--write-benchmarks",
        action="store_true",
        help="Write the resulting hosted dataset IDs back into the benchmark YAML files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        client = build_logfire_api_client()

        results: list[tuple[str, str, Path]] = []
        for target in DATASET_BOOTSTRAP_TARGETS:
            dataset_payload = load_canonical_dataset(target["dataset_path"])
            dataset_name = hosted_dataset_name(dataset_payload)
            dataset = sync_hosted_dataset(
                client=client,
                dataset_name=dataset_name,
                dataset_payload=dataset_payload,
            )
            dataset_id = dataset.get("id")
            if not isinstance(dataset_id, str) or not dataset_id:
                raise RuntimeError(f"Hosted dataset ID missing for {dataset_name}")
            if args.write_benchmarks:
                update_benchmark_hosted_dataset_id(
                    benchmark_path=target["benchmark_path"],
                    dataset_id=dataset_id,
                )
            results.append((dataset_name, dataset_id, target["benchmark_path"]))
    except DatasetApiError as exc:
        print(dataset_api_error_message(str(exc)), file=sys.stderr)
        return 1

    for dataset_name, dataset_id, benchmark_path in results:
        print(f"{dataset_name}: {dataset_id}")
        if args.write_benchmarks:
            print(f"updated {benchmark_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
