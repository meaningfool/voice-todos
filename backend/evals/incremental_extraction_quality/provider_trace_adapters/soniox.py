from __future__ import annotations

from typing import Any

from app.extraction_thresholds import EXTRACTION_TOKEN_THRESHOLD
from app.stt_soniox import translate_soniox_event
from app.transcript_accumulator import TranscriptAccumulator


def build_soniox_checkpoint_candidates(
    messages: list[dict[str, Any]],
    *,
    token_threshold: int = EXTRACTION_TOKEN_THRESHOLD,
) -> list[str]:
    """Return deterministic checkpoint candidates for replay dataset seeding.

    These snapshots mirror the transcript states that could trigger extraction in the
    live Soniox path, but they intentionally do not model 1:1 runtime extraction
    invocations when live backpressure collapses in-flight triggers.
    """
    transcript = TranscriptAccumulator()
    tokens_since_last_extraction = 0
    checkpoint_candidates: list[str] = []

    for event in messages:
        if event.get("finished"):
            break

        result = transcript.apply_stt_event(translate_soniox_event(event))
        snapshot = transcript.full_text

        if result.has_endpoint:
            if snapshot.strip():
                checkpoint_candidates.append(snapshot)
            tokens_since_last_extraction = 0
            continue

        if result.final_token_count <= 0:
            continue

        tokens_since_last_extraction += result.final_token_count
        if tokens_since_last_extraction < token_threshold:
            continue

        if snapshot.strip():
            checkpoint_candidates.append(snapshot)
        tokens_since_last_extraction = 0

    return checkpoint_candidates
