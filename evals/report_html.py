from __future__ import annotations

import json
import re
import subprocess
import webbrowser
from pathlib import Path

from evals.report import ensure_benchmark_report
from evals.storage import benchmark_html_report_path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = REPO_ROOT / "frontend"
VIEWER_ENTRY_HTML = FRONTEND_ROOT / "benchmark-report.html"
VIEWER_VITE_CONFIG = FRONTEND_ROOT / "vite.benchmark-report.config.ts"
VIEWER_DIST_DIR = FRONTEND_ROOT / "dist-benchmark-report"
BOOTSTRAP_PLACEHOLDER = "__BENCHMARK_REPORT_BOOTSTRAP__"

_STYLESHEET_PATTERN = re.compile(
    r'<link rel="stylesheet"[^>]*href="(?P<href>[^"]+)"[^>]*>'
)
_MODULE_SCRIPT_PATTERN = re.compile(
    r'<script type="module"[^>]*src="(?P<src>[^"]+)"[^>]*></script>'
)


def ensure_benchmark_report_html(
    benchmark_id: str,
    query_client: object | None = None,
) -> Path:
    _report, report_path, _ = ensure_benchmark_report(
        benchmark_id=benchmark_id,
        query_client=query_client,
    )
    shell_html = _load_viewer_shell_html()
    bootstrap_payload = json.dumps(
        {
            "reportPath": str(report_path),
            "report": json.loads(report_path.read_text()),
        },
        separators=(",", ":"),
    )
    html = shell_html.replace(
        BOOTSTRAP_PLACEHOLDER,
        _escape_script_json(bootstrap_payload),
    )
    output_path = benchmark_html_report_path(benchmark_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)
    return output_path


def open_benchmark_report_html(
    benchmark_id: str,
    query_client: object | None = None,
) -> Path:
    html_path = ensure_benchmark_report_html(
        benchmark_id=benchmark_id,
        query_client=query_client,
    )
    if not webbrowser.open(html_path.resolve().as_uri()):
        raise RuntimeError(f"failed to open benchmark report in browser: {html_path}")
    return html_path


def _load_viewer_shell_html() -> str:
    dist_html_path = _build_viewer_shell()
    return _inline_vite_assets(dist_html_path)


def _build_viewer_shell() -> Path:
    if not VIEWER_ENTRY_HTML.exists():
        raise RuntimeError(f"missing benchmark viewer entry HTML: {VIEWER_ENTRY_HTML}")
    if not VIEWER_VITE_CONFIG.exists():
        raise RuntimeError(
            f"missing benchmark viewer Vite config: {VIEWER_VITE_CONFIG}"
        )

    command = ["pnpm", "run", "build:benchmark-report"]
    result = subprocess.run(
        command,
        cwd=FRONTEND_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "benchmark report UI build failed\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    dist_html_path = VIEWER_DIST_DIR / "benchmark-report.html"
    if not dist_html_path.exists():
        raise RuntimeError(
            f"benchmark report viewer build did not produce {dist_html_path}"
        )
    return dist_html_path


def _inline_vite_assets(dist_html_path: Path) -> str:
    html = dist_html_path.read_text()
    html = _STYLESHEET_PATTERN.sub(
        lambda match: _inline_stylesheet_tag(dist_html_path, match.group("href")),
        html,
    )
    html = _MODULE_SCRIPT_PATTERN.sub(
        lambda match: _inline_module_script_tag(dist_html_path, match.group("src")),
        html,
    )
    return html


def _inline_stylesheet_tag(dist_html_path: Path, href: str) -> str:
    asset_path = _resolve_dist_asset_path(dist_html_path, href)
    return f"<style>{asset_path.read_text()}</style>"


def _inline_module_script_tag(dist_html_path: Path, src: str) -> str:
    asset_path = _resolve_dist_asset_path(dist_html_path, src)
    return f"<script type=\"module\">{asset_path.read_text()}</script>"


def _resolve_dist_asset_path(dist_html_path: Path, reference: str) -> Path:
    normalized = reference.removeprefix("./").removeprefix("/")
    return dist_html_path.parent / normalized


def _escape_script_json(value: str) -> str:
    return value.replace("</", "<\\/")
