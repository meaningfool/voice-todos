from types import SimpleNamespace

from evals.cli import main


def test_benchmark_list_prints_known_ids(capsys):
    exit_code = main(["benchmark", "list"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "extraction_llm_matrix_v1" in captured.out
    assert "replay_llm_matrix_v1" in captured.out


def test_benchmark_show_prints_entry_labels_and_config(capsys):
    exit_code = main(["benchmark", "show", "extraction_llm_matrix_v1"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Gemini 3 Flash / default" in captured.out
    assert "prompt_version" in captured.out


def test_benchmark_run_defaults_to_missing_entries(monkeypatch):
    planned = []
    monkeypatch.setattr(
        "evals.cli.run_benchmark",
        lambda **kwargs: planned.append(kwargs)
        or SimpleNamespace(executed_entry_ids=["mistral_small_4_default"]),
    )

    main(["benchmark", "run", "extraction_llm_matrix_v1"])

    assert planned[0]["all_entries"] is False
