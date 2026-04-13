from __future__ import annotations


def main(argv: list[str] | None = None) -> int:
    raise SystemExit(
        "Deprecated benchmark entrypoint. "
        "Use `cd backend && uv run python ../evals/cli.py benchmark ...`."
    )


if __name__ == "__main__":
    raise SystemExit(main())
