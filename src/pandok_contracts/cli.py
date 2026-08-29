"""Command-line interface for validating telemetry JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from .errors import ReasonCode, ValidationIssue
from .validator import validate_event, validate_sequence


Validator = Callable[[Any], list[ValidationIssue]]


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _output(valid: bool, issues: list[ValidationIssue], event_count: int) -> None:
    print(
        json.dumps(
            {
                "valid": valid,
                "event_count": event_count,
                "issues": [issue.as_dict() for issue in issues],
            },
            ensure_ascii=False,
        )
    )


def _run(path: Path, validator: Validator, sequence: bool) -> int:
    try:
        value = _read_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        issue = ValidationIssue(ReasonCode.INVALID_JSON, str(exc))
        _output(False, [issue], 0)
        return 1

    issues = validator(value)
    count = len(value) if sequence and isinstance(value, list) else 1
    _output(not issues, issues, count)
    return 1 if issues else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pandok-contract",
        description="Validate PANDOK telemetry contract v1 JSON files.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    event_parser = subparsers.add_parser("validate-event", help="Validate one event object")
    event_parser.add_argument("path", type=Path)

    sequence_parser = subparsers.add_parser(
        "validate-sequence", help="Validate an array containing one Run sequence"
    )
    sequence_parser.add_argument("path", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate-event":
        return _run(args.path, validate_event, sequence=False)
    return _run(args.path, validate_sequence, sequence=True)


if __name__ == "__main__":
    raise SystemExit(main())
