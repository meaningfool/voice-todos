#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


def present(value: str | None) -> str:
    return "present" if value else "missing"


def read_env_keys(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {"_error": "invalid json"}
    return value if isinstance(value, dict) else {"_error": "not an object"}


def main() -> None:
    backend_env = read_env_keys(ROOT / "backend" / ".env")
    creds = read_json(ROOT / "backend" / ".logfire" / "logfire_credentials.json")

    print("Logfire setup audit")
    print(f"repo: {ROOT}")
    print()
    print("backend/.env")
    for key in ["LOGFIRE_READ_TOKEN", "LOGFIRE_DATASETS_TOKEN", "LOGFIRE_TOKEN", "LOGFIRE_MCP_TOKEN"]:
        print(f"  {key}: {present(backend_env.get(key))}")
    print()
    print("backend/.logfire/logfire_credentials.json")
    print(f"  project_name: {creds.get('project_name', '<missing>')}")
    print(f"  project_url: {creds.get('project_url', '<missing>')}")
    print(f"  logfire_api_url: {creds.get('logfire_api_url', '<missing>')}")
    print(f"  token: {present(creds.get('token') if isinstance(creds.get('token'), str) else None)}")
    print()
    print("process environment")
    for key in ["LOGFIRE_READ_TOKEN", "LOGFIRE_DATASETS_TOKEN", "LOGFIRE_TOKEN", "LOGFIRE_MCP_TOKEN"]:
        print(f"  {key}: {present(os.getenv(key))}")
    print()
    print("codex mcp")
    try:
        output = subprocess.check_output(
            ["codex", "mcp", "list", "--json"],
            cwd=ROOT,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        print(f"  unavailable: {exc}")
    else:
        print(output.strip())


if __name__ == "__main__":
    main()
