#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts" / "aggregate-export-v1.schema.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_payload(payload: dict) -> None:
    schema = load_json(SCHEMA_PATH)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.absolute_path))
    if errors:
        lines = []
        for error in errors:
            location = ".".join(str(x) for x in error.absolute_path) or "<root>"
            lines.append(f"{location}: {error.message}")
        raise ValueError("\n".join(lines))


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validate_export.py <aggregate-export.json>")
        return 2

    payload_path = Path(sys.argv[1]).resolve()
    payload = load_json(payload_path)
    validate_payload(payload)
    print(f"VALID: {payload['schema_version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
