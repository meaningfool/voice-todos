from __future__ import annotations

import sys
from pathlib import Path


def bootstrap_repo_imports() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    repo_path = str(repo_root)
    if repo_path not in sys.path:
        sys.path.append(repo_path)
    return repo_root
