#!/usr/bin/env python3
"""Check that the committed OpenAPI contract matches the live FastAPI schema."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from warroom_api.app import app

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "openapi.json"


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="refresh the committed contract")
    args = parser.parse_args()
    generated = canonical(app.openapi())
    if args.write:
        CONTRACT.write_text(generated, encoding="utf-8")
        print(f"wrote {CONTRACT}")
        return 0
    if not CONTRACT.is_file():
        print(f"missing contract: {CONTRACT}", file=sys.stderr)
        return 1
    committed = CONTRACT.read_text(encoding="utf-8")
    if committed != generated:
        print(
            "OpenAPI contract drift detected; run: "
            "uv run python ops/check-openapi-contract.py --write",
            file=sys.stderr,
        )
        return 1
    print(f"OpenAPI contract matches ({len(app.openapi()['paths'])} paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
