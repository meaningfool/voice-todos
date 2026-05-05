from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description="Hosted websocket smoke scaffold.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--mode", required=True)
    parser.parse_args()
    print("ws-smoke scaffold: not implemented")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
