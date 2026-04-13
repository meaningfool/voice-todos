from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class BoundaryState(StrEnum):
    UNSUPPORTED = "unsupported"
    NOT_OBSERVED = "not_observed"
    OBSERVED = "observed"


@dataclass(slots=True)
class SttToken:
    text: str
    is_final: bool


@dataclass(slots=True)
class SttEvent:
    tokens: list[SttToken] = field(default_factory=list)
    finalization_state: BoundaryState = BoundaryState.NOT_OBSERVED
    endpoint_state: BoundaryState = BoundaryState.NOT_OBSERVED
    is_finished: bool = False


@dataclass(frozen=True, slots=True)
class SttCapabilities:
    exposes_finalization_boundary: bool
    exposes_endpoint_boundary: bool


class SttSession(Protocol):
    @property
    def capabilities(self) -> SttCapabilities: ...

    async def send_audio(self, chunk: bytes) -> None: ...

    async def request_final_transcript(self) -> None: ...

    async def end_stream(self) -> None: ...

    async def wait_for_final_transcript(self) -> None: ...

    async def close(self) -> None: ...

    def __aiter__(self): ...
