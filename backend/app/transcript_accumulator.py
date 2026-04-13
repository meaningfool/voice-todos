from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.stt import BoundaryState, SttEvent, SttToken


@dataclass(slots=True)
class TranscriptAccumulatorResult:
    tokens: list[dict[str, str | bool]]
    has_fin: bool
    has_endpoint: bool
    final_token_count: int


@dataclass
class TranscriptAccumulator:
    final_parts: list[str] = field(default_factory=list)
    interim_parts: list[str] = field(default_factory=list)

    def reset(self) -> None:
        self.final_parts.clear()
        self.interim_parts.clear()

    def apply_event(self, event: dict[str, Any]) -> TranscriptAccumulatorResult:
        raw_tokens = []
        has_fin = False
        has_endpoint = False
        for token in event.get("tokens", []):
            if not isinstance(token, dict) or not isinstance(token.get("text"), str):
                continue
            text = token["text"]
            if text == "<fin>":
                has_fin = True
                continue
            if text == "<end>":
                has_endpoint = True
                continue
            raw_tokens.append(
                SttToken(text=text, is_final=bool(token.get("is_final", False)))
            )
        return self.apply_stt_event(
            SttEvent(
                tokens=raw_tokens,
                finalization_state=(
                    BoundaryState.OBSERVED
                    if has_fin
                    else BoundaryState.NOT_OBSERVED
                ),
                endpoint_state=(
                    BoundaryState.OBSERVED
                    if has_endpoint
                    else BoundaryState.NOT_OBSERVED
                ),
                is_finished=bool(event.get("finished")),
            )
        )

    def apply_stt_event(self, event: SttEvent) -> TranscriptAccumulatorResult:
        has_fin = event.finalization_state is BoundaryState.OBSERVED
        has_endpoint = event.endpoint_state is BoundaryState.OBSERVED
        tokens = [
            {"text": token.text, "is_final": token.is_final}
            for token in event.tokens
        ]
        final_token_count = sum(1 for token in tokens if token.get("is_final", False))

        if has_fin:
            self.interim_parts.clear()

        if tokens:
            saw_final = False
            for token in tokens:
                if token.get("is_final", False):
                    saw_final = True
                    self.final_parts.append(token["text"])

            interim_text = "".join(
                token["text"] for token in tokens if not token.get("is_final", False)
            )
            if interim_text:
                self.interim_parts.clear()
                self.interim_parts.append(interim_text)
            elif saw_final:
                self.interim_parts.clear()

        return TranscriptAccumulatorResult(
            tokens=[
                {"text": token["text"], "is_final": token.get("is_final", False)}
                for token in tokens
            ],
            has_fin=has_fin,
            has_endpoint=has_endpoint,
            final_token_count=final_token_count,
        )

    @property
    def full_text(self) -> str:
        transcript = "".join(self.final_parts)
        if self.interim_parts:
            transcript += "".join(self.interim_parts)
        return transcript
