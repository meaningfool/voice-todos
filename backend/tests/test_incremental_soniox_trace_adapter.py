from evals.incremental_extraction_quality.provider_trace_adapters.soniox import (
    build_soniox_checkpoint_candidates,
)


def _event(
    *tokens: str,
    endpoint: bool = False,
    fin: bool = False,
) -> dict[str, list[dict[str, str | bool]]]:
    payload = [{"text": token, "is_final": True} for token in tokens]
    if endpoint:
        payload.append({"text": "<end>", "is_final": True})
    if fin:
        payload.append({"text": "<fin>", "is_final": True})
    return {"tokens": payload}


def test_soniox_adapter_emits_expected_checkpoint_candidates():
    messages = [
        _event(
            "Call",
            " mom",
            " tonight",
            ".",
            " Send",
            " memo",
            " soon",
            ".",
            " Check",
            " quote",
            " now",
            ".",
            " Buy",
            " oat",
            " milk",
        ),
        _event(" please", " today", "."),
        _event(" Also", " email", " Sam", ".", endpoint=True),
        _event(fin=True),
    ]

    checkpoint_candidates = build_soniox_checkpoint_candidates(messages)

    assert checkpoint_candidates == [
        "Call mom tonight. Send memo soon. Check quote now. Buy oat milk",
        "Call mom tonight. Send memo soon. Check quote now. Buy oat milk please today. Also email Sam.",
    ]
