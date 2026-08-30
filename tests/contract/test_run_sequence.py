from __future__ import annotations

from copy import deepcopy

from pandok_contracts.errors import ReasonCode
from pandok_contracts.validator import validate_sequence


def test_complete_p0_sequence_is_valid(valid_sequence):
    assert validate_sequence(valid_sequence) == []


def test_arrival_order_does_not_change_event_time_validation(valid_sequence):
    assert validate_sequence(list(reversed(valid_sequence))) == []


def test_selected_item_must_be_one_of_shown_options(valid_sequence):
    events = deepcopy(valid_sequence)
    selected = next(
        event
        for event in events
        if event["event_name"] == "upgrade_selected"
        and event["choice_source"] == "statue"
    )
    selected["selected_item_id"] = "blood_scent"
    issues = validate_sequence(events)
    assert any(issue.code == ReasonCode.CHOICE_MISMATCH for issue in issues)


def test_cumulative_counter_must_not_decrease(valid_sequence):
    events = deepcopy(valid_sequence)
    events[-1]["total_kills"] = 10
    issues = validate_sequence(events)
    assert any(issue.code == ReasonCode.COUNTER_DECREASED for issue in issues)


def test_identical_retry_is_allowed(valid_sequence):
    events = deepcopy(valid_sequence)
    events.append(deepcopy(events[-2]))
    assert validate_sequence(events) == []


def test_same_event_id_with_different_payload_is_conflict(valid_sequence):
    events = deepcopy(valid_sequence)
    conflict = deepcopy(events[-2])
    conflict["total_kills"] += 1
    events.append(conflict)
    issues = validate_sequence(events)
    assert any(issue.code == ReasonCode.DUPLICATE_CONFLICT for issue in issues)


def test_run_can_end_before_first_checkpoint(valid_sequence):
    events = deepcopy(valid_sequence)
    session = next(event for event in events if event["event_name"] == "session_started")
    start = next(event for event in events if event["event_name"] == "run_started")
    ended = next(event for event in events if event["event_name"] == "run_ended")
    ended["event_time"] = "2026-09-01T12:30:40Z"
    ended["run_duration_seconds"] = 30
    assert validate_sequence([session, start, ended]) == []


def test_missing_run_start_is_rejected(valid_sequence):
    issues = validate_sequence([valid_sequence[-1]])
    assert any(issue.code == ReasonCode.MISSING_RUN_START for issue in issues)


def test_checkpoint_occurs_on_its_sixty_second_boundary(valid_sequence):
    events = deepcopy(valid_sequence)
    events[-2]["run_elapsed_seconds"] = 75
    issues = validate_sequence(events)
    assert any(issue.code == ReasonCode.EVENT_ORDER_INVALID for issue in issues)


def test_checkpoint_number_must_strictly_increase(valid_sequence):
    events = deepcopy(valid_sequence)
    checkpoint = deepcopy(
        next(event for event in events if event["event_name"] == "run_checkpoint")
    )
    checkpoint["event_id"] = "00000000-0000-4000-8000-000000000011"
    checkpoint["event_time"] = "2026-09-01T12:31:45Z"
    events.insert(-1, checkpoint)
    issues = validate_sequence(events)
    assert any(issue.code == ReasonCode.COUNTER_DECREASED for issue in issues)


def test_choice_sequence_must_increase(valid_sequence):
    events = deepcopy(valid_sequence)
    shown = deepcopy(
        next(
            event
            for event in events
            if event["event_name"] == "upgrade_options_shown"
            and event["choice_source"] == "statue"
        )
    )
    selected = deepcopy(
        next(
            event
            for event in events
            if event["event_name"] == "upgrade_selected"
            and event["choice_source"] == "statue"
        )
    )
    shown["event_id"] = "00000000-0000-4000-8000-000000000009"
    shown["choice_id"] = "40000000-0000-4000-8000-000000000003"
    shown["event_time"] = "2026-09-01T12:31:20Z"
    shown["choice_sequence"] = 2
    selected["event_id"] = "00000000-0000-4000-8000-000000000010"
    selected["choice_id"] = shown["choice_id"]
    selected["event_time"] = "2026-09-01T12:31:21Z"
    selected["choice_sequence"] = 2
    events[-1:-1] = [shown, selected]
    issues = validate_sequence(events)
    assert any(issue.code == ReasonCode.COUNTER_DECREASED for issue in issues)


def test_selected_choice_source_must_match_shown_source(valid_sequence):
    events = deepcopy(valid_sequence)
    selected = next(
        event
        for event in events
        if event["event_name"] == "upgrade_selected"
        and event["choice_source"] == "statue"
    )
    selected["choice_source"] = "level_up_upgrade"
    issues = validate_sequence(events)
    assert any(issue.code == ReasonCode.CHOICE_MISMATCH for issue in issues)


def test_same_time_choice_link_is_independent_of_arrival_order(valid_sequence):
    events = deepcopy(valid_sequence)
    shown = next(
        event
        for event in events
        if event["event_name"] == "upgrade_options_shown"
        and event["choice_source"] == "statue"
    )
    selected = next(
        event
        for event in events
        if event["event_name"] == "upgrade_selected"
        and event["choice_source"] == "statue"
    )
    selected["event_time"] = shown["event_time"]
    events.remove(selected)
    events.insert(events.index(shown), selected)
    assert validate_sequence(events) == []


def test_selection_cannot_occur_before_its_shown_choice(valid_sequence):
    events = deepcopy(valid_sequence)
    selected = next(
        event
        for event in events
        if event["event_name"] == "upgrade_selected"
        and event["choice_source"] == "statue"
    )
    selected["event_time"] = "2026-09-01T12:31:09Z"
    issues = validate_sequence(events)
    assert any(issue.code == ReasonCode.EVENT_ORDER_INVALID for issue in issues)


def test_choice_id_cannot_identify_different_shown_choices(valid_sequence):
    events = deepcopy(valid_sequence)
    shown = deepcopy(
        next(
            event
            for event in events
            if event["event_name"] == "upgrade_options_shown"
            and event["choice_source"] == "statue"
        )
    )
    shown["event_id"] = "00000000-0000-4000-8000-000000000015"
    shown["event_time"] = "2026-09-01T12:31:20Z"
    shown["options"][0]["rarity"] = "legendary"
    events.insert(-1, shown)
    issues = validate_sequence(events)
    assert any(issue.code == ReasonCode.CHOICE_MISMATCH for issue in issues)


def test_initial_weapon_choice_may_precede_run_started(valid_sequence):
    events = deepcopy(valid_sequence)
    start_time = next(
        event["event_time"] for event in events if event["event_name"] == "run_started"
    )
    initial_choices = [
        event for event in events if event.get("choice_source") == "level_up_weapon"
    ]
    assert len(initial_choices) == 2
    assert all(event["event_time"] < start_time for event in initial_choices)
    assert all(event["run_elapsed_seconds"] == 0 for event in initial_choices)
    assert validate_sequence(events) == []


def test_non_initial_event_must_not_precede_run_started(valid_sequence):
    events = deepcopy(valid_sequence)
    checkpoint = next(
        event for event in events if event["event_name"] == "run_checkpoint"
    )
    checkpoint["event_time"] = "2026-09-01T12:30:07Z"
    issues = validate_sequence(events)
    assert any(issue.code == ReasonCode.EVENT_ORDER_INVALID for issue in issues)
