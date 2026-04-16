from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

from benchmark_live_validation_lib import (
    available_entry_definition,
    cleanup_dataset,
    create_temp_hosted_dataset,
    run_benchmark_report_cli,
    run_benchmark_run_cli,
    write_temp_benchmark,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
for candidate in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.live_eval_env import benchmark_run_skip_reason


def main() -> int:
    warning = benchmark_run_skip_reason()
    if warning is not None:
        print(f"WARN: {warning}")
        return 0

    benchmark_id = f"benchmark_run_report_smoke_{uuid.uuid4().hex[:8]}"
    client, dataset_id, _dataset_name = create_temp_hosted_dataset(
        transcript="Call Mom tonight.",
    )
    tempdir, benchmark_path = write_temp_benchmark(
        benchmark_id=benchmark_id,
        hosted_dataset=dataset_id,
        entry=available_entry_definition(),
    )

    try:
        os.environ["EVALS_BENCHMARKS_DIR"] = str(benchmark_path.parent)

        run_result = run_benchmark_run_cli(benchmark_id=benchmark_id)
        if run_result.returncode != 0:
            print(
                "FAIL: benchmark run failed\n"
                f"stdout:\n{run_result.stdout}\n"
                f"stderr:\n{run_result.stderr}"
            )
            return 1

        report_result = run_benchmark_report_cli(
            benchmark_id=benchmark_id,
            json_output=True,
        )
        if report_result.returncode != 0:
            print(
                "FAIL: benchmark report failed\n"
                f"stdout:\n{report_result.stdout}\n"
                f"stderr:\n{report_result.stderr}"
            )
            return 1

        payload = json.loads(report_result.stdout)
        if payload.get("benchmark_id") != benchmark_id:
            print("FAIL: benchmark report JSON did not include the benchmark ID")
            return 1

        entries = payload.get("entries")
        if not isinstance(entries, list) or not entries:
            print("FAIL: benchmark report JSON did not include entry state payload")
            return 1

        first_entry = entries[0]
        if (
            not isinstance(first_entry, dict)
            or "entry_id" not in first_entry
            or "status" not in first_entry
        ):
            print("FAIL: benchmark report JSON entry state payload was malformed")
            return 1

        print(
            "PASS: benchmark run and report completed with entry state payload "
            f"for {benchmark_id}"
        )
        return 0
    finally:
        os.environ.pop("EVALS_BENCHMARKS_DIR", None)
        cleanup_dataset(client, dataset_id, benchmark_id, tempdir)


if __name__ == "__main__":
    raise SystemExit(main())
