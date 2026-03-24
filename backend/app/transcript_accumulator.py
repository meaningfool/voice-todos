from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TranscriptAccumulator:
    final_parts: list[str] = field(default_factory=list)
    interim_parts: list[str] = field(default_factory=list)

    def reset(self) -> None:
        self.final_parts.clear()
        self.interim_parts.clear()

    def apply_event(self, event: dict[str, Any]) -> list[dict[str, str | bool]]:
        raw_tokens = [
            token
            for token in event.get("tokens", [])
            if isinstance(token, dict) and isinstance(token.get("text"), str)
        ]
        has_fin = any(token["text"] == "<fin>" for token in raw_tokens)
        tokens = [token for token in raw_tokens if token["text"] != "<fin>"]

        if has_fin:
            self.interim_parts.clear()

        if tokens:
            for token in tokens:
                if token.get("is_final", False):
                    self.final_parts.append(token["text"])

            interim_text = "".join(
                token["text"] for token in tokens if not token.get("is_final", False)
            )
            if interim_text:
                self.interim_parts.clear()
                self.interim_parts.append(interim_text)

        return [
            {"text": token["text"], "is_final": token.get("is_final", False)}
            for token in tokens
        ]

    @property
    def full_text(self) -> str:
        transcript = "".join(self.final_parts)
        if self.interim_parts:
            transcript += "".join(self.interim_parts)
        return transcript
