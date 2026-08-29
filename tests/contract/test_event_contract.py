from __future__ import annotations

from copy import deepcopy

import pytest

from pandok_contracts.errors import ReasonCode
from pandok_contracts.validator import validate_event

from conftest import FIXTURES, read_json


def test_all_six_p0_event_types_are_valid(valid_sequence):
    assert {event["event_name"] for event in valid_sequence} == {
        "session_started",
        "run_started",
        "upgrade_options_shown",
        "upgrade_selected",
        "run_checkpoint",
        "run_ended",
    }
    for event in valid_sequence:
        assert validate_event(event) == []


def test_developer_pending_checkpoint_fields_are_optional(valid_sequence):
    checkpoint = deepcopy(valid_sequence[-2])
    for field in (
        "player_level",
        "current_xp",
        "xp_to_next_level",
        "hp_percent",
        "total_kills",
        "total_xp_collected",
        "gold_earned",
        "miniboss_waves_cleared",
        "active_upgrades",
    ):
        checkpoint.pop(field)
    assert validate_event(checkpoint) == []


def test_unsupported_schema_version_is_rejected(valid_sequence):
    event = deepcopy(valid_sequence[1])
    event["schema_version"] = "2.0"
    issues = validate_event(event)
    assert issues and issues[0].code == ReasonCode.SCHEMA_INVALID


def test_unknown_field_is_rejected(valid_sequence):
    event = deepcopy(valid_sequence[1])
    event["unreviewed_field"] = "surprise"
    issues = validate_event(event)
    assert issues and issues[0].code == ReasonCode.SCHEMA_INVALID


@pytest.mark.parametrize(
    ("filename", "reason"),
    [
        ("event_with_steam_id.json", ReasonCode.PROHIBITED_FIELD),
        ("missing_event_id.json", ReasonCode.SCHEMA_INVALID),
        ("invalid_hp_percent.json", ReasonCode.SCHEMA_INVALID),
        ("unsupported_schema_version.json", ReasonCode.SCHEMA_INVALID),
    ],
)
def test_saved_invalid_fixtures_are_rejected(filename, reason):
    issues = validate_event(read_json(FIXTURES / "invalid" / filename))
    assert issues and issues[0].code == reason


REQUIRED_FIELDS = {
    "session_started": (),
    "run_started": ("run_id",),
    "upgrade_options_shown": (
        "run_id",
        "choice_id",
        "choice_sequence",
        "run_elapsed_seconds",
        "options",
    ),
    "upgrade_selected": (
        "run_id",
        "choice_id",
        "choice_sequence",
        "run_elapsed_seconds",
        "selected_slot",
        "selected_item_id",
        "selected_rarity",
    ),
    "run_checkpoint": ("run_id", "checkpoint_number", "run_elapsed_seconds"),
    "run_ended": ("run_id", "end_reason", "run_duration_seconds"),
}


@pytest.mark.parametrize(
    "common_field",
    (
        "event_id",
        "event_name",
        "event_time",
        "anonymous_user_id",
        "session_id",
        "game_version",
        "schema_version",
    ),
)
def test_every_common_required_field_is_enforced(valid_sequence, common_field):
    for original in valid_sequence:
        event = deepcopy(original)
        event.pop(common_field)
        assert validate_event(event), (event.get("event_name"), common_field)


def test_every_event_specific_required_field_is_enforced(valid_sequence):
    for original in valid_sequence:
        for field in REQUIRED_FIELDS[original["event_name"]]:
            event = deepcopy(original)
            event.pop(field)
            assert validate_event(event), (original["event_name"], field)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("event_time", "2026-09-01 12:30:10"),
        ("event_id", "not-a-uuid"),
        ("event_name", "enemy_killed"),
        ("schema_version", "99.0"),
    ],
)
def test_malformed_common_values_are_rejected(valid_sequence, field, value):
    event = deepcopy(valid_sequence[1])
    event[field] = value
    assert validate_event(event)


@pytest.mark.parametrize(
    ("event_index", "field", "value"),
    [
        (2, "run_elapsed_seconds", -1),
        (4, "checkpoint_number", 0),
        (4, "total_kills", -1),
        (4, "hp_percent", 100.1),
        (5, "run_duration_seconds", -1),
    ],
)
def test_malformed_ranges_are_rejected(valid_sequence, event_index, field, value):
    event = deepcopy(valid_sequence[event_index])
    event[field] = value
    assert validate_event(event)
