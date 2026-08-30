from __future__ import annotations

import json

from pandok_contracts.cli import main

from conftest import FIXTURES


def test_valid_sequence_cli_returns_structured_success(capsys):
    result = main(
        [
            "validate-sequence",
            str(FIXTURES / "valid" / "p0_run_sequence.json"),
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert output == {"valid": True, "event_count": 8, "issues": []}


def test_invalid_event_cli_returns_structured_failure(capsys):
    result = main(
        [
            "validate-event",
            str(FIXTURES / "invalid" / "event_with_steam_id.json"),
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert result == 1
    assert output["valid"] is False
    assert output["issues"][0]["code"] == "prohibited_field"
