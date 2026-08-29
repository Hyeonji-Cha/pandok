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
    events[3]["selected_item_id"] = "blood_scent"
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
    session, start, *_middle, ended = deepcopy(valid_sequence)
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


def test_choice_sequence_must_increase(valid_sequence):
    events = deepcopy(valid_sequence)
    shown = deepcopy(events[2])
    selected = deepcopy(events[3])
    shown["event_id"] = "00000000-0000-4000-8000-000000000007"
    shown["choice_id"] = "40000000-0000-4000-8000-000000000002"
    shown["event_time"] = "2026-09-01T12:31:20Z"
    shown["choice_sequence"] = 1
    selected["event_id"] = "00000000-0000-4000-8000-000000000008"
    selected["choice_id"] = shown["choice_id"]
    selected["event_time"] = "2026-09-01T12:31:21Z"
    selected["choice_sequence"] = 1
    events[-1:-1] = [shown, selected]
    issues = validate_sequence(events)
    assert any(issue.code == ReasonCode.COUNTER_DECREASED for issue in issues)
