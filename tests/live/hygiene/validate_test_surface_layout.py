#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

DISALLOWED_NAME_PATTERN = re.compile(r"(item\d+|phase\d+|rollout)", re.IGNORECASE)
PYTHON_TEST_PATTERN = re.compile(r"^\s*def\s+(test_[A-Za-z0-9_]+)\s*\(", re.MULTILINE)
FRONTEND_TEST_PATTERN = re.compile(
    r"""\b(?:it|test)(?:\.each\([\s\S]*?\))?\(\s*(["'`])(?P<name>.*?)(?<!\\)\1""",
    re.MULTILINE,
)
FORBIDDEN_SCRIPT_BASENAME = re.compile(r"^(test_|validate_)", re.IGNORECASE)


def main() -> int:
    tracked_files = _tracked_files()
    backend_files = _filter_backend_test_files(tracked_files)
    live_files = _filter_live_files(tracked_files)
    frontend_files = _filter_frontend_test_files(tracked_files)
    script_files = _filter_script_files(tracked_files)

    violations: list[str] = []

    violations.extend(_check_file_basenames("backend/tests", backend_files))
    violations.extend(_check_file_basenames("tests/live", live_files))
    violations.extend(_check_file_basenames("frontend tests", frontend_files))
    violations.extend(_check_python_test_names("backend/tests", backend_files))
    violations.extend(_check_python_test_names("tests/live", live_files))
    violations.extend(_check_frontend_test_names(frontend_files))
    violations.extend(_check_scripts(script_files))

    print("Scanned test surface:")
    print(f"- backend/tests Python files: {len(backend_files)}")
    print(f"- tests/live Python files: {len(live_files)}")
    print(f"- frontend test files: {len(frontend_files)}")
    print(f"- scripts files: {len(script_files)}")

    if violations:
        print("\nFAIL: test surface hygiene violations detected")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print("\nPASS: maintained automated test surface uses behavior-based naming and test-owned placement")
    return 0


def _tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [REPO_ROOT / line for line in result.stdout.splitlines() if line]


def _filter_backend_test_files(paths: list[Path]) -> list[Path]:
    return [
        path
        for path in paths
        if path.is_relative_to(REPO_ROOT / "backend/tests") and path.suffix == ".py"
    ]


def _filter_live_files(paths: list[Path]) -> list[Path]:
    return [
        path
        for path in paths
        if path.is_relative_to(REPO_ROOT / "tests/live") and path.suffix == ".py"
    ]


def _filter_frontend_test_files(paths: list[Path]) -> list[Path]:
    return [
        path
        for path in paths
        if path.is_relative_to(REPO_ROOT / "frontend/src")
        and path.name.endswith((".test.ts", ".test.tsx"))
    ]


def _filter_script_files(paths: list[Path]) -> list[Path]:
    return [
        path
        for path in paths
        if path.is_relative_to(REPO_ROOT / "scripts") and path.is_file()
    ]


def _check_file_basenames(label: str, paths: list[Path]) -> list[str]:
    violations: list[str] = []
    for path in paths:
        if DISALLOWED_NAME_PATTERN.search(path.name):
            violations.append(
                f"{label} basename contains rollout label: {path.relative_to(REPO_ROOT)}"
            )
    return violations


def _check_python_test_names(label: str, paths: list[Path]) -> list[str]:
    violations: list[str] = []
    for path in paths:
        content = path.read_text()
        for match in PYTHON_TEST_PATTERN.finditer(content):
            test_name = match.group(1)
            if DISALLOWED_NAME_PATTERN.search(test_name):
                violations.append(
                    f"{label} test function contains rollout label: "
                    f"{path.relative_to(REPO_ROOT)}::{test_name}"
                )
    return violations


def _check_frontend_test_names(paths: list[Path]) -> list[str]:
    violations: list[str] = []
    for path in paths:
        content = path.read_text()
        for match in FRONTEND_TEST_PATTERN.finditer(content):
            test_name = match.group("name")
            if DISALLOWED_NAME_PATTERN.search(test_name):
                violations.append(
                    "frontend test name contains rollout label: "
                    f"{path.relative_to(REPO_ROOT)}::{test_name}"
                )
    return violations


def _check_scripts(paths: list[Path]) -> list[str]:
    violations: list[str] = []
    for path in paths:
        if FORBIDDEN_SCRIPT_BASENAME.search(path.name):
            violations.append(
                f"test-owned script asset still lives under scripts/: {path.relative_to(REPO_ROOT)}"
            )
    return violations


if __name__ == "__main__":
    sys.exit(main())
