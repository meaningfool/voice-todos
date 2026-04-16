from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
for candidate in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app.live_eval_env import stale_benchmark_detection_validation_warning
from benchmark_live_validation_lib import (
    available_entry_definition,
    cleanup_dataset,
    create_temp_hosted_dataset,
    mutate_temp_hosted_dataset,
    run_benchmark_run_cli,
    write_temp_benchmark,
)


def main() -> int:
    warning = stale_benchmark_detection_validation_warning()
    if warning is not None:
        print(f"WARN: {warning}")
        return 0

    benchmark_id = f"stale_benchmark_detection_{uuid.uuid4().hex[:8]}"
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
        first = run_benchmark_run_cli(
            benchmark_id=benchmark_id,
            args=["--allow-untracked"],
        )
        if first.returncode != 0:
            print(
                "FAIL: initial benchmark run failed\n"
                f"stdout:\n{first.stdout}\n"
                f"stderr:\n{first.stderr}"
            )
            return 1

        mutate_temp_hosted_dataset(
            client=client,
            dataset_id=dataset_id,
            transcript="Call Mom tomorrow morning.",
        )

        second = run_benchmark_run_cli(
            benchmark_id=benchmark_id,
            args=["--allow-untracked"],
        )
        combined = (second.stdout + second.stderr).lower()
        if second.returncode == 0 or "stale" not in combined:
            print(
                "FAIL: stale benchmark stop was not surfaced\n"
                f"stdout:\n{second.stdout}\n"
                f"stderr:\n{second.stderr}"
            )
            return 1

        print(
            "PASS: stale benchmark detection surfaced dataset drift "
            f"for {benchmark_id}"
        )
        return 0
    finally:
        os.environ.pop("EVALS_BENCHMARKS_DIR", None)
        cleanup_dataset(client, dataset_id, benchmark_id, tempdir)


if __name__ == "__main__":
    raise SystemExit(main())
