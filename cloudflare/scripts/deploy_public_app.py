#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shlex
import subprocess
import tempfile
from pathlib import Path

REQUIRED_SECRET_NAMES = (
    "SONIOX_API_KEY",
    "GEMINI_API_KEY",
)


def parse_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value[:1] == value[-1:] and value[:1] in {"'", '"'}:
            value = value[1:-1]
        env[key] = value
    return env


def collect_required_secrets(env_file: Path) -> dict[str, str]:
    env = parse_env_file(env_file)
    missing = [name for name in REQUIRED_SECRET_NAMES if not env.get(name)]
    if missing:
        raise ValueError(f"Missing required secrets: {', '.join(missing)}")
    return {name: env[name] for name in REQUIRED_SECRET_NAMES}


def build_deploy_command(
    *,
    public_domain: str,
    secrets_file: Path,
    session_cap_ms: str | None,
    stop_timeout_seconds: str | None,
) -> list[str]:
    command = [
        "uv",
        "run",
        "pywrangler",
        "deploy",
        "--domain",
        public_domain,
        "--secrets-file",
        str(secrets_file),
        "--var",
        "STT_PROVIDER=soniox",
    ]
    if session_cap_ms is not None:
        command.extend(["--var", f"SESSION_CAP_MS={session_cap_ms}"])
    if stop_timeout_seconds is not None:
        command.extend(["--var", f"STOP_TIMEOUT_SECONDS={stop_timeout_seconds}"])
    return command


def write_secrets_file(secrets: dict[str, str], destination: Path) -> None:
    destination.write_text("".join(f"{key}={value}\n" for key, value in secrets.items()))


def run_command(command: list[str], *, cwd: Path) -> None:
    print(f"+ {shlex.join(command)}")
    subprocess.run(command, cwd=cwd, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-domain", required=True)
    parser.add_argument(
        "--backend-env-file",
        default=None,
        help="Path to the backend env file that holds deploy secrets.",
    )
    parser.add_argument("--session-cap-ms", default=None)
    parser.add_argument("--stop-timeout-seconds", default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    cloudflare_dir = Path(__file__).resolve().parents[1]
    repo_root = cloudflare_dir.parent
    frontend_dir = repo_root / "frontend"
    sync_script = cloudflare_dir / "scripts" / "sync_frontend_dist.sh"
    backend_env_file = (
        Path(args.backend_env_file).resolve()
        if args.backend_env_file is not None
        else repo_root / "backend" / ".env"
    )

    secrets = collect_required_secrets(backend_env_file)

    run_command(["pnpm", "build"], cwd=frontend_dir)
    run_command([str(sync_script)], cwd=cloudflare_dir)

    with tempfile.TemporaryDirectory(prefix="voice-todos-public-deploy-") as tmp_dir:
        secrets_file = Path(tmp_dir) / "public.secrets.env"
        write_secrets_file(secrets, secrets_file)
        deploy_command = build_deploy_command(
            public_domain=args.public_domain,
            secrets_file=secrets_file,
            session_cap_ms=args.session_cap_ms,
            stop_timeout_seconds=args.stop_timeout_seconds,
        )

        print(f"Generated temporary secrets file: {secrets_file}")
        print(f"Deploy command: {shlex.join(deploy_command)}")

        if args.dry_run:
            print("Dry run: skipping Cloudflare deploy.")
            return 0

        run_command(deploy_command, cwd=cloudflare_dir)
        print(f"Deployed to https://{args.public_domain}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
