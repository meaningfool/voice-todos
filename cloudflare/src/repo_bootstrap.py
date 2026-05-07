from __future__ import annotations

import sys
from pathlib import Path


def bootstrap_backend_imports() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    backend_root = repo_root / "backend"
    backend_path = str(backend_root)
    if backend_path not in sys.path:
        sys.path.append(backend_path)
    return repo_root
