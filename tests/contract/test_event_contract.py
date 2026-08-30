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


def test_implementation_required_checkpoint_fields_are_optional(valid_sequence):
    checkpoint = deepcopy(valid_sequence[-2])
    for field in (
        "total_xp_collected",
        "total_gold_collected",
        "miniboss_waves_cleared",
        "active_upgrades",
    ):
        assert field not in checkpoint
    assert validate_event(checkpoint) == []


def test_optional_acquisition_and_boolean_effect_state_is_valid(valid_sequence):
    selected = deepcopy(
        next(
            event
            for event in valid_sequence
            if event["event_name"] == "upgrade_selected"
            and event["choice_source"] == "statue"
        )
    )
    selected.update(
        acquisition_count_before=0,
        acquisition_count_after=1,
        effect_type="time_slow_enabled",
        effect_value_before=False,
        effect_value_after=True,
    )
    assert validate_event(selected) == []


def test_source_specific_valid_choice_shapes_are_accepted(valid_sequence):
    shown = [
        event
        for event in valid_sequence
        if event["event_name"] == "upgrade_options_shown"
    ]
    assert {(event["choice_source"], len(event["options"])) for event in shown} == {
        ("level_up_weapon", 2),
        ("statue", 3),
    }
    assert all(validate_event(event) == [] for event in shown)


def test_statue_selection_can_use_slot_three(valid_sequence):
    selected = deepcopy(
        next(
            event
            for event in valid_sequence
            if event["event_name"] == "upgrade_selected"
            and event["choice_source"] == "statue"
        )
    )
    selected["selected_slot"] = 3
    selected["selected_item_id"] = "gold_ingot"
    selected["selected_rarity"] = "rare"
    assert validate_event(selected) == []


def test_player_restart_is_a_supported_end_reason(valid_sequence):
    ended = deepcopy(valid_sequence[-1])
    ended["end_reason"] = "player_restart"
    assert validate_event(ended) == []


@pytest.mark.parametrize(
    "filename",
    [
        "statue_selected_with_effect_state.json",
        "run_ended_player_restart.json",
    ],
)
def test_saved_optional_state_and_restart_examples_are_valid(filename):
    assert validate_event(read_json(FIXTURES / "valid" / filename)) == []


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
        ("statue_with_two_options.json", ReasonCode.SCHEMA_INVALID),
        ("level_up_with_three_options.json", ReasonCode.SCHEMA_INVALID),
        ("unsupported_rarity.json", ReasonCode.SCHEMA_INVALID),
        ("statue_with_duplicate_items.json", ReasonCode.CHOICE_MISMATCH),
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
        "choice_source",
        "run_elapsed_seconds",
        "options",
    ),
    "upgrade_selected": (
        "run_id",
        "choice_id",
        "choice_sequence",
        "choice_source",
        "run_elapsed_seconds",
        "selected_slot",
        "selected_item_id",
        "selected_rarity",
    ),
    "run_checkpoint": (
        "run_id",
        "checkpoint_number",
        "run_elapsed_seconds",
        "player_level",
        "current_xp",
        "xp_to_next_level",
        "hp_percent",
        "total_kills",
        "current_gold",
    ),
    "run_ended": (
        "run_id",
        "end_reason",
        "run_duration_seconds",
        "final_level",
        "total_kills",
        "current_gold",
    ),
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
    ("event_name", "field"),
    [
        ("session_started", "anonymous_user_id"),
        ("session_started", "session_id"),
        ("run_started", "run_id"),
        ("upgrade_options_shown", "choice_id"),
    ],
)
def test_every_uuid_field_rejects_malformed_values(valid_sequence, event_name, field):
    event = deepcopy(
        next(item for item in valid_sequence if item["event_name"] == event_name)
    )
    event[field] = "not-a-uuid"
    assert validate_event(event)


@pytest.mark.parametrize(
    ("event_index", "field", "value"),
    [
        (1, "run_elapsed_seconds", -1),
        (6, "checkpoint_number", 0),
        (6, "total_kills", -1),
        (6, "current_xp", -1),
        (6, "xp_to_next_level", 0),
        (6, "current_gold", -1),
        (6, "hp_percent", 100.1),
        (7, "run_duration_seconds", -1),
        (7, "final_level", -1),
        (7, "current_gold", -1),
    ],
)
def test_malformed_ranges_are_rejected(valid_sequence, event_index, field, value):
    event = deepcopy(valid_sequence[event_index])
    event[field] = value
    assert validate_event(event)


@pytest.mark.parametrize(
    ("source", "options"),
    [
        (
            "statue",
            [
                {"slot": 1, "item_id": "sword", "rarity": "common"},
                {"slot": 2, "item_id": "hourglass", "rarity": "uncommon"},
                {"slot": 2, "item_id": "gold_ingot", "rarity": "rare"},
            ],
        ),
        (
            "level_up_upgrade",
            [
                {"slot": 1, "item_id": "upgrade_a", "rarity": "common"},
                {"slot": 1, "item_id": "upgrade_b", "rarity": "uncommon"},
            ],
        ),
    ],
)
def test_each_source_requires_its_complete_slot_set(valid_sequence, source, options):
    shown = deepcopy(
        next(
            event
            for event in valid_sequence
            if event["event_name"] == "upgrade_options_shown"
        )
    )
    shown["choice_source"] = source
    shown["options"] = options
    assert validate_event(shown)


def test_statue_rejects_item_outside_chest_item_type(valid_sequence):
    shown = deepcopy(
        next(
            event
            for event in valid_sequence
            if event.get("choice_source") == "statue"
            and event["event_name"] == "upgrade_options_shown"
        )
    )
    shown["options"][0]["item_id"] = "unknown_statue_item"
    assert validate_event(shown)


@pytest.mark.parametrize("field", ["slot", "item_id", "rarity"])
def test_every_upgrade_option_required_field_is_enforced(valid_sequence, field):
    shown = deepcopy(
        next(
            event
            for event in valid_sequence
            if event.get("choice_source") == "statue"
            and event["event_name"] == "upgrade_options_shown"
        )
    )
    shown["options"][0].pop(field)
    assert validate_event(shown)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("acquisition_count_before", -1),
        ("acquisition_count_after", 0),
        ("effect_type", "Not Stable"),
        ("effect_value_after", "enabled"),
    ],
)
def test_invalid_acquisition_and_effect_state_is_rejected(
    valid_sequence, field, value
):
    selected = deepcopy(
        next(
            event
            for event in valid_sequence
            if event["event_name"] == "upgrade_selected"
            and event["choice_source"] == "statue"
        )
    )
    selected.update(
        acquisition_count_before=0,
        acquisition_count_after=1,
        effect_type="time_slow_enabled",
        effect_value_before=False,
        effect_value_after=True,
    )
    selected[field] = value
    assert validate_event(selected)


def test_upgrade_state_required_fields_are_enforced(valid_sequence):
    checkpoint = deepcopy(
        next(
            event
            for event in valid_sequence
            if event["event_name"] == "run_checkpoint"
        )
    )
    checkpoint["active_upgrades"] = [{"item_id": "sword"}]
    assert validate_event(checkpoint)
