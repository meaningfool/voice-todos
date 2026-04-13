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

from app.live_eval_env import stale_benchmark_actions_validation_warning
from benchmark_locking_live_validation_lib import (
    available_entry_definition,
    cleanup_dataset,
    create_temp_hosted_dataset,
    load_lock_payload,
    mutate_temp_hosted_dataset,
    run_benchmark_cli,
    write_temp_benchmark,
)


def main() -> int:
    warning = stale_benchmark_actions_validation_warning()
    if warning is not None:
        print(f"WARN: {warning}")
        return 0

    benchmark_id = f"stale_benchmark_actions_{uuid.uuid4().hex[:8]}"
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
        initial = run_benchmark_cli(benchmark_id=benchmark_id)
        if initial.returncode != 0:
            print(
                "FAIL: phase 3 initial benchmark run failed\n"
                f"stdout:\n{initial.stdout}\n"
                f"stderr:\n{initial.stderr}"
            )
            return 1

        old_lock = load_lock_payload(benchmark_id)
        old_hash = old_lock["_benchmark_lock"]["dataset_hash"]

        mutate_temp_hosted_dataset(
            client=client,
            dataset_id=dataset_id,
            transcript="Call Mom tomorrow morning.",
        )

        allow_stale = run_benchmark_cli(
            benchmark_id=benchmark_id,
            args=["--allow-stale"],
        )
        if allow_stale.returncode != 0:
            print(
                "FAIL: phase 3 --allow-stale run failed\n"
                f"stdout:\n{allow_stale.stdout}\n"
                f"stderr:\n{allow_stale.stderr}"
            )
            return 1

        after_allow_stale = load_lock_payload(benchmark_id)
        if after_allow_stale["_benchmark_lock"]["dataset_hash"] != old_hash:
            print("FAIL: --allow-stale unexpectedly rewrote the benchmark lock")
            return 1

        rebase = run_benchmark_cli(
            benchmark_id=benchmark_id,
            args=["--rebase"],
        )
        if rebase.returncode != 0:
            print(
                "FAIL: phase 3 --rebase run failed\n"
                f"stdout:\n{rebase.stdout}\n"
                f"stderr:\n{rebase.stderr}"
            )
            return 1

        after_rebase = load_lock_payload(benchmark_id)
        new_hash = after_rebase["_benchmark_lock"]["dataset_hash"]
        new_transcript = after_rebase["rows"][0]["input"]["transcript"]
        if new_hash == old_hash:
            print("FAIL: --rebase did not rewrite the benchmark lock hash")
            return 1
        if new_transcript != "Call Mom tomorrow morning.":
            print("FAIL: --rebase did not adopt the current hosted dataset payload")
            return 1

        print(
            "PASS: stale benchmark actions preserved the stale lock for --allow-stale and rewrote it "
            f"for --rebase on {benchmark_id}"
        )
        return 0
    finally:
        os.environ.pop("EVALS_BENCHMARKS_DIR", None)
        cleanup_dataset(client, dataset_id, benchmark_id, tempdir)


if __name__ == "__main__":
    raise SystemExit(main())
