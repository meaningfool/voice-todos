from __future__ import annotations

import sys
from pathlib import Path

import repo_bootstrap


def test_bootstrap_backend_imports_preserves_cloudflare_src_precedence(
    monkeypatch,
):
    src_path = str(Path(repo_bootstrap.__file__).resolve().parent)
    backend_path = str(Path(repo_bootstrap.__file__).resolve().parents[2] / "backend")

    monkeypatch.setattr(sys, "path", [src_path, "/tmp/already-there"])

    repo_bootstrap.bootstrap_backend_imports()

    assert sys.path.index(src_path) < sys.path.index(backend_path)
