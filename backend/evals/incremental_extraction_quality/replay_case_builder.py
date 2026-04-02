from __future__ import annotations


def build_replay_steps(
    checkpoint_candidates: list[str],
    *,
    final_transcript: str,
) -> list[str]:
    replay_steps: list[str] = []

    for snapshot in checkpoint_candidates:
        if not snapshot.strip():
            continue
        if replay_steps and replay_steps[-1] == snapshot:
            continue
        replay_steps.append(snapshot)

    if final_transcript.strip() and (
        not replay_steps or replay_steps[-1] != final_transcript
    ):
        replay_steps.append(final_transcript)

    return replay_steps
