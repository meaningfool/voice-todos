from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

from benchmark_live_validation_lib import (
    available_entry_definition,
    cleanup_dataset,
    create_temp_hosted_dataset,
    load_lock_payload,
    run_benchmark_run_cli,
    write_temp_benchmark,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
for candidate in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.live_eval_env import hosted_dataset_locking_validation_warning


def main() -> int:
    warning = hosted_dataset_locking_validation_warning()
    if warning is not None:
        print(f"WARN: {warning}")
        return 0

    benchmark_id = f"hosted_dataset_locking_{uuid.uuid4().hex[:8]}"
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
        result = run_benchmark_run_cli(benchmark_id=benchmark_id)
        if result.returncode != 0:
            print(
                "FAIL: benchmark run failed\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
            return 1

        lock_payload = load_lock_payload(benchmark_id)
        if lock_payload["_benchmark_lock"]["hosted_dataset"] != dataset_id:
            print("FAIL: lock file does not reference the hosted dataset ID")
            return 1
        if len(lock_payload["rows"]) != 1:
            print("FAIL: lock file does not contain the expected case count")
            return 1

        print(
            "PASS: hosted dataset locking created a benchmark lock "
            f"for {benchmark_id}"
        )
        return 0
    finally:
        os.environ.pop("EVALS_BENCHMARKS_DIR", None)
        cleanup_dataset(client, dataset_id, benchmark_id, tempdir)


if __name__ == "__main__":
    raise SystemExit(main())
