from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.stt import BoundaryState, SttCapabilities, SttEvent, SttToken

SONIOX_CAPABILITIES = SttCapabilities(
    exposes_finalization_boundary=True,
    exposes_endpoint_boundary=True,
)


def build_soniox_config(api_key: str) -> dict[str, Any]:
    return {
        "api_key": api_key,
        "model": "stt-rt-v4",
        "audio_format": "pcm_s16le",
        "sample_rate": 16000,
        "num_channels": 1,
        "enable_endpoint_detection": True,
        "max_endpoint_delay_ms": 1000,
        "context": {
            "general": [
                {
                    "key": "topic",
                    "value": (
                        "The user is dictating tasks and todos "
                        "into a voice-driven todo list application."
                    ),
                },
            ],
        },
    }


def translate_soniox_event(raw_event: Mapping[str, Any]) -> SttEvent:
    if raw_event.get("finished"):
        return SttEvent(is_finished=True)

    raw_tokens = [
        token
        for token in raw_event.get("tokens", [])
        if isinstance(token, Mapping) and isinstance(token.get("text"), str)
    ]
    finalization_state = (
        BoundaryState.OBSERVED
        if any(token["text"] == "<fin>" for token in raw_tokens)
        else BoundaryState.NOT_OBSERVED
    )
    endpoint_state = (
        BoundaryState.OBSERVED
        if any(token["text"] == "<end>" for token in raw_tokens)
        else BoundaryState.NOT_OBSERVED
    )
    tokens = [
        SttToken(text=token["text"], is_final=bool(token.get("is_final", False)))
        for token in raw_tokens
        if token["text"] not in {"<fin>", "<end>"}
    ]
    return SttEvent(
        tokens=tokens,
        finalization_state=finalization_state,
        endpoint_state=endpoint_state,
        is_finished=False,
    )
