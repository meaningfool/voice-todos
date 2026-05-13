import asyncio
import io
from types import SimpleNamespace

import pytest
from evals.resolution import resolve_entry_config
from evals.run import run_benchmark
from evals.storage import load_benchmark_by_id


def test_extraction_benchmark_entry_resolves_current_runner_contract():
    benchmark = load_benchmark_by_id("todo_extraction_bench_v1")
    entry = next(
        candidate
        for candidate in benchmark.entries
        if candidate.id == "gemini3_flash_default"
    )
    resolved = resolve_entry_config(benchmark=benchmark, entry=entry)

    assert resolved.suite == "extraction_quality"
    assert resolved.provider == "google-gla"
    assert resolved.model_name == "gemini-3-flash-preview"
    assert resolved.prompt_version == "v1"


def test_extraction_benchmark_entry_resolves_deepinfra_family_contract():
    benchmark = load_benchmark_by_id("todo_extraction_bench_v1")
    entry = next(
        candidate
        for candidate in benchmark.entries
        if candidate.id == "deepinfra_qwen35_4b_provider_json_schema"
    )
    resolved = resolve_entry_config(benchmark=benchmark, entry=entry)

    assert resolved.suite == "extraction_quality"
    assert resolved.provider == "deepinfra"
    assert resolved.model_name == "Qwen/Qwen3.5-4B"
    assert resolved.prompt_version == "v1"
    assert resolved.implementation_family == "deepinfra-provider-json-schema"
    assert resolved.model_settings == {
        "temperature": 0,
        "max_tokens": 512,
        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
    }


def test_extraction_runner_passes_entry_context_without_benchmark_leakage(
    monkeypatch, tmp_path
):
    calls = []
    opened_leases = []
    closed_leases = []

    async def fake_launch(**kwargs):
        calls.append(kwargs)
        return {"entry_id": kwargs["entry"].id}

    async def fake_open_managed_session(*, resolved_config):
        lease = SimpleNamespace(
            base_url="https://modal.test/v1",
            api_key="lease-key",
            headers={"Modal-Session-ID": resolved_config.model_name},
        )
        opened_leases.append(lease)
        return lease

    async def fake_close_managed_session(lease):
        closed_leases.append(lease)

    monkeypatch.setattr(
        "evals.run.load_current_benchmark_state",
        lambda benchmark: SimpleNamespace(current_entry_ids=set()),
    )
    monkeypatch.setattr("evals.run.open_managed_session", fake_open_managed_session)
    monkeypatch.setattr("evals.run.close_managed_session", fake_close_managed_session)
    monkeypatch.setattr("evals.run.launch_extraction_entry", fake_launch)

    result = asyncio.run(
        run_benchmark(
            benchmark_id="todo_extraction_bench_v1",
            all_entries=True,
            dataset_path=tmp_path / "dataset.json",
            allow_untracked=True,
        )
    )

    assert result.executed_entry_ids
    assert calls[0]["entry"].id == "gemini3_flash_default"
    assert "benchmark" not in calls[0]
    assert len(opened_leases) == len(closed_leases)


def test_managed_modal_entry_resolves_runtime_contract():
    benchmark = load_benchmark_by_id("todo_extraction_bench_v1")
    entry = next(
        candidate
        for candidate in benchmark.entries
        if candidate.id == "modal_outlines_qwen35_4b"
    )
    resolved = resolve_entry_config(benchmark=benchmark, entry=entry)

    assert resolved.suite == "extraction_quality"
    assert resolved.provider == "managed-openai"
    assert resolved.model_name == "Qwen/Qwen3.5-4B"
    assert resolved.prompt_version == "v1"
    assert resolved.implementation_family == "modal-outlines"
    assert resolved.model_settings == {
        "temperature": 0,
        "max_tokens": 512,
        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
    }
    assert resolved.managed_session.model_dump() == {
        "stack": "sglang-outlines",
        "host": "modal",
        "gpu": "L40S",
        "context_window": 4096,
    }


@pytest.mark.asyncio
async def test_run_benchmark_reuses_managed_lease_for_same_model_and_session(
    monkeypatch, tmp_path
):
    benchmark = SimpleNamespace(
        benchmark_id="managed-grouping",
        repeat=1,
        task_retries=0,
        max_concurrency=1,
        entries=[
            SimpleNamespace(id="modal_outlines_qwen35_4b_a"),
            SimpleNamespace(id="modal_outlines_qwen35_4b_b"),
        ],
    )
    resolved = SimpleNamespace(
        suite="extraction_quality",
        provider="managed-openai",
        model_name="Qwen/Qwen3.5-4B",
        prompt_version="v1",
        implementation_family="modal-outlines",
        model_settings={"temperature": 0, "max_tokens": 1024},
        managed_session=SimpleNamespace(
            stack="sglang-outlines",
            host="modal",
            gpu="L40S",
            context_window=4096,
        ),
    )
    opened_leases = []
    closed_leases = []
    launch_calls = []

    async def fake_open_managed_session(*, resolved_config):
        lease = SimpleNamespace(
            base_url=f"https://modal.test/{len(opened_leases)}",
            api_key=f"lease-{len(opened_leases)}",
            headers={"Modal-Session-ID": f"session-{len(opened_leases)}"},
        )
        opened_leases.append((resolved_config.model_name, lease))
        return lease

    async def fake_close_managed_session(lease):
        closed_leases.append(lease)

    async def fake_launch_extraction_entry(**kwargs):
        launch_calls.append(kwargs)
        return {"entry_id": kwargs["entry"].id, "batch_id": "batch"}

    monkeypatch.setattr(
        "evals.run.load_benchmark_by_id", lambda benchmark_id: benchmark
    )
    monkeypatch.setattr(
        "evals.run.load_current_benchmark_state",
        lambda benchmark: SimpleNamespace(current_entry_ids=set()),
    )
    monkeypatch.setattr(
        "evals.run.resolve_entry_config",
        lambda benchmark, entry: resolved,
    )
    monkeypatch.setattr("evals.run.open_managed_session", fake_open_managed_session)
    monkeypatch.setattr("evals.run.close_managed_session", fake_close_managed_session)
    monkeypatch.setattr(
        "evals.run.launch_extraction_entry", fake_launch_extraction_entry
    )

    result = await run_benchmark(
        benchmark_id="managed-grouping",
        all_entries=True,
        dataset_path=tmp_path / "dataset.json",
        allow_untracked=True,
    )

    assert result.executed_entry_ids == [
        "modal_outlines_qwen35_4b_a",
        "modal_outlines_qwen35_4b_b",
    ]
    assert [model_name for model_name, _lease in opened_leases] == ["Qwen/Qwen3.5-4B"]
    assert len(launch_calls) == 2
    assert launch_calls[0]["managed_lease"] is launch_calls[1]["managed_lease"]
    assert closed_leases == [opened_leases[0][1]]


@pytest.mark.asyncio
async def test_run_benchmark_opens_managed_lease_before_entry_execution(
    monkeypatch, tmp_path
):
    benchmark = SimpleNamespace(
        benchmark_id="managed-ordering",
        repeat=1,
        task_retries=0,
        max_concurrency=1,
        entries=[SimpleNamespace(id="modal_outlines_qwen35_4b")],
    )
    resolved = SimpleNamespace(
        suite="extraction_quality",
        provider="managed-openai",
        model_name="Qwen/Qwen3.5-4B",
        prompt_version="v1",
        implementation_family="modal-outlines",
        model_settings={"temperature": 0, "max_tokens": 1024},
        managed_session=SimpleNamespace(
            stack="sglang-outlines",
            host="modal",
            gpu="L40S",
            context_window=4096,
        ),
    )
    events = []

    async def fake_open_managed_session(*, resolved_config):
        events.append(("open", resolved_config.model_name))
        return SimpleNamespace(
            base_url="https://modal.test/v1",
            api_key="lease-key",
            headers={"Modal-Session-ID": "session-123"},
        )

    async def fake_close_managed_session(lease):
        events.append(("close", lease.base_url))

    async def fake_launch_extraction_entry(**kwargs):
        events.append(("launch", kwargs["entry"].id, kwargs["managed_lease"].base_url))
        return {"entry_id": kwargs["entry"].id, "batch_id": "batch"}

    monkeypatch.setattr(
        "evals.run.load_benchmark_by_id", lambda benchmark_id: benchmark
    )
    monkeypatch.setattr(
        "evals.run.load_current_benchmark_state",
        lambda benchmark: SimpleNamespace(current_entry_ids=set()),
    )
    monkeypatch.setattr(
        "evals.run.resolve_entry_config",
        lambda benchmark, entry: resolved,
    )
    monkeypatch.setattr("evals.run.open_managed_session", fake_open_managed_session)
    monkeypatch.setattr("evals.run.close_managed_session", fake_close_managed_session)
    monkeypatch.setattr(
        "evals.run.launch_extraction_entry", fake_launch_extraction_entry
    )

    await run_benchmark(
        benchmark_id="managed-ordering",
        all_entries=True,
        dataset_path=tmp_path / "dataset.json",
        allow_untracked=True,
    )

    assert events == [
        ("open", "Qwen/Qwen3.5-4B"),
        ("launch", "modal_outlines_qwen35_4b", "https://modal.test/v1"),
        ("close", "https://modal.test/v1"),
    ]


@pytest.mark.asyncio
async def test_run_benchmark_closes_managed_lease_after_launch_failure(
    monkeypatch, tmp_path
):
    benchmark = SimpleNamespace(
        benchmark_id="managed-failure-cleanup",
        repeat=1,
        task_retries=0,
        max_concurrency=1,
        entries=[SimpleNamespace(id="modal_outlines_qwen35_4b")],
    )
    resolved = SimpleNamespace(
        suite="extraction_quality",
        provider="managed-openai",
        model_name="Qwen/Qwen3.5-4B",
        prompt_version="v1",
        implementation_family="modal-outlines",
        model_settings={"temperature": 0, "max_tokens": 1024},
        managed_session=SimpleNamespace(
            stack="sglang-outlines",
            host="modal",
            gpu="L40S",
            context_window=4096,
        ),
    )
    opened_leases = []
    closed_leases = []

    async def fake_open_managed_session(*, resolved_config):
        lease = SimpleNamespace(
            base_url="https://modal.test/failure",
            api_key="lease-key",
            headers={"Modal-Session-ID": "session-failure"},
        )
        opened_leases.append(lease)
        return lease

    async def fake_close_managed_session(lease):
        closed_leases.append(lease)

    async def failing_launch_extraction_entry(**kwargs):
        raise RuntimeError("benchmark entry failed")

    monkeypatch.setattr(
        "evals.run.load_benchmark_by_id", lambda benchmark_id: benchmark
    )
    monkeypatch.setattr(
        "evals.run.load_current_benchmark_state",
        lambda benchmark: SimpleNamespace(current_entry_ids=set()),
    )
    monkeypatch.setattr(
        "evals.run.resolve_entry_config",
        lambda benchmark, entry: resolved,
    )
    monkeypatch.setattr("evals.run.open_managed_session", fake_open_managed_session)
    monkeypatch.setattr("evals.run.close_managed_session", fake_close_managed_session)
    monkeypatch.setattr(
        "evals.run.launch_extraction_entry", failing_launch_extraction_entry
    )

    with pytest.raises(RuntimeError, match="benchmark entry failed"):
        await run_benchmark(
            benchmark_id="managed-failure-cleanup",
            all_entries=True,
            dataset_path=tmp_path / "dataset.json",
            allow_untracked=True,
        )

    assert len(opened_leases) == 1
    assert closed_leases == opened_leases


@pytest.mark.asyncio
async def test_run_benchmark_keeps_only_one_managed_lease_active(monkeypatch, tmp_path):
    benchmark = SimpleNamespace(
        benchmark_id="managed-single-active",
        repeat=1,
        task_retries=0,
        max_concurrency=1,
        entries=[
            SimpleNamespace(id="modal_outlines_qwen35_4b"),
            SimpleNamespace(id="modal_outlines_qwen35_9b"),
        ],
    )
    resolved_by_entry_id = {
        "modal_outlines_qwen35_4b": SimpleNamespace(
            suite="extraction_quality",
            provider="managed-openai",
            model_name="Qwen/Qwen3.5-4B",
            prompt_version="v1",
            implementation_family="modal-outlines",
            model_settings={"temperature": 0, "max_tokens": 1024},
            managed_session=SimpleNamespace(
                stack="sglang-outlines",
                host="modal",
                gpu="L40S",
                context_window=4096,
            ),
        ),
        "modal_outlines_qwen35_9b": SimpleNamespace(
            suite="extraction_quality",
            provider="managed-openai",
            model_name="Qwen/Qwen3.5-9B",
            prompt_version="v1",
            implementation_family="modal-outlines",
            model_settings={"temperature": 0, "max_tokens": 1024},
            managed_session=SimpleNamespace(
                stack="sglang-outlines",
                host="modal",
                gpu="L40S",
                context_window=4096,
            ),
        ),
    }
    active_leases = 0
    max_active_leases = 0

    async def fake_open_managed_session(*, resolved_config):
        nonlocal active_leases, max_active_leases
        active_leases += 1
        max_active_leases = max(max_active_leases, active_leases)
        return SimpleNamespace(
            base_url=f"https://modal.test/{resolved_config.model_name}",
            api_key="lease-key",
            headers={"Modal-Session-ID": resolved_config.model_name},
        )

    async def fake_close_managed_session(lease):
        nonlocal active_leases
        active_leases -= 1

    async def fake_launch_extraction_entry(**kwargs):
        assert active_leases == 1
        return {"entry_id": kwargs["entry"].id, "batch_id": "batch"}

    monkeypatch.setattr(
        "evals.run.load_benchmark_by_id", lambda benchmark_id: benchmark
    )
    monkeypatch.setattr(
        "evals.run.load_current_benchmark_state",
        lambda benchmark: SimpleNamespace(current_entry_ids=set()),
    )
    monkeypatch.setattr(
        "evals.run.resolve_entry_config",
        lambda benchmark, entry: resolved_by_entry_id[entry.id],
    )
    monkeypatch.setattr("evals.run.open_managed_session", fake_open_managed_session)
    monkeypatch.setattr("evals.run.close_managed_session", fake_close_managed_session)
    monkeypatch.setattr(
        "evals.run.launch_extraction_entry", fake_launch_extraction_entry
    )

    await run_benchmark(
        benchmark_id="managed-single-active",
        all_entries=True,
        dataset_path=tmp_path / "dataset.json",
        allow_untracked=True,
    )

    assert max_active_leases == 1
    assert active_leases == 0


def test_managed_session_launcher_reads_ready_payload(monkeypatch):
    from evals.managed_sessions import open_managed_session

    captured_cmd = []

    class FakeProcess:
        def __init__(self):
            self.stdout = io.StringIO(
                "booting modal app\n"
                '{"status":"ready","base_url":"https://modal.test/v1",'
                '"api_key":"managed-test-key",'
                '"headers":{"Modal-Session-ID":"session-123"}}\n'
            )
            self.pid = 12345

        def poll(self):
            return None

    def fake_popen(cmd, **kwargs):
        captured_cmd.append((cmd, kwargs))
        return FakeProcess()

    monkeypatch.setattr("evals.managed_sessions.subprocess.Popen", fake_popen)

    resolved_config = SimpleNamespace(
        model_name="Qwen/Qwen3.5-4B",
        managed_session=SimpleNamespace(
            stack="sglang-outlines",
            host="modal",
            gpu="L40S",
            context_window=4096,
        ),
    )

    lease = asyncio.run(open_managed_session(resolved_config=resolved_config))

    assert lease.base_url == "https://modal.test/v1"
    assert lease.api_key == "managed-test-key"
    assert lease.headers == {"Modal-Session-ID": "session-123"}
    assert captured_cmd
    assert captured_cmd[0][0][:3] == [
        "modal",
        "run",
        "scripts/qwen_sglang_outlines_smoke.py",
    ]
    assert "--mode" in captured_cmd[0][0]
    assert "serve" in captured_cmd[0][0]
    assert "--model-name" in captured_cmd[0][0]
    assert "Qwen/Qwen3.5-4B" in captured_cmd[0][0]


def test_managed_session_launcher_terminates_process_on_close():
    from evals.managed_sessions import ManagedSessionLease, close_managed_session

    class FakeProcess:
        def __init__(self):
            self.terminated = False
            self.wait_calls = []

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            self.wait_calls.append(timeout)

    process = FakeProcess()
    lease = ManagedSessionLease(
        base_url="https://modal.test/v1",
        api_key="managed-test-key",
        headers={"Modal-Session-ID": "session-123"},
        process=process,
    )

    asyncio.run(close_managed_session(lease))

    assert process.terminated is True
    assert process.wait_calls
