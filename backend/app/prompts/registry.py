from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PromptRef:
    family: str
    version: str
    path: Path
    content: str
    sha256: str


_PROMPT_ROOT = Path(__file__).resolve().parent
_PROMPT_PATHS: dict[tuple[str, str], Path] = {
    ("todo_extraction", "v1"): _PROMPT_ROOT / "todo_extraction" / "v1.md",
}


def _available_families() -> list[str]:
    return sorted({family for family, _ in _PROMPT_PATHS})


def _available_versions(*, family: str) -> list[str]:
    return sorted(
        version
        for registered_family, version in _PROMPT_PATHS
        if registered_family == family
    )


def get_prompt_ref(*, family: str, version: str) -> PromptRef:
    try:
        path = _PROMPT_PATHS[(family, version)]
    except KeyError as exc:
        families = _available_families()
        versions = _available_versions(family=family)
        if versions:
            raise ValueError(
                f"Unsupported prompt version for family {family!r}: {version!r}. "
                f"Available versions: {', '.join(versions)}"
            ) from exc
        raise ValueError(
            f"Unsupported prompt family: {family!r}. "
            f"Available families: {', '.join(families)}"
        ) from exc

    content = path.read_text(encoding="utf-8")
    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    return PromptRef(
        family=family,
        version=version,
        path=path,
        content=content,
        sha256=sha256,
    )
