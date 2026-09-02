# v2 이벤트를 event_sequence 기준으로 복원할 때 정상·미완성·오류 상태를 구분하는지 테스트한다.
# 네트워크 도착 순서가 달라도 Silver가 Run을 일관되게 판정하도록 보장하기 위해 필요하다.

from __future__ import annotations

from copy import deepcopy

from pandok_contracts.errors import ReasonCode, SequenceStatus
from pandok_contracts.validator import validate_anonymous_sequence

from conftest import REPO_ROOT, read_json


SEQUENCE_PATH = (
    REPO_ROOT
    / "tests"
    / "contract"
    / "fixtures"
    / "v2"
    / "valid"
    / "anonymous_p0_run_sequence.json"
)


def _sequence():
    return read_json(SEQUENCE_PATH)


def test_anonymous_sequence_is_valid():
    result = validate_anonymous_sequence(_sequence())

    assert result.status == SequenceStatus.VALID
    assert result.issues == ()


def test_anonymous_sequence_ignores_network_arrival_order():
    events = list(reversed(_sequence()))

    result = validate_anonymous_sequence(events)

    assert result.status == SequenceStatus.VALID


def test_anonymous_sequence_accepts_identical_retry():
    events = _sequence()
    events.append(deepcopy(events[-2]))

    result = validate_anonymous_sequence(events)

    assert result.status == SequenceStatus.VALID


def test_anonymous_sequence_gap_is_incomplete():
    events = _sequence()
    del events[-2]

    result = validate_anonymous_sequence(events)

    assert result.status == SequenceStatus.INCOMPLETE
    assert any(
        issue.code == ReasonCode.EVENT_SEQUENCE_GAP
        for issue in result.issues
    )


def test_anonymous_sequence_without_end_is_incomplete():
    events = _sequence()[:-1]

    result = validate_anonymous_sequence(events)

    assert result.status == SequenceStatus.INCOMPLETE
    assert any(
        issue.code == ReasonCode.MISSING_RUN_END
        for issue in result.issues
    )


def test_anonymous_sequence_number_conflict_is_invalid():
    events = _sequence()
    conflict = deepcopy(events[-2])
    conflict["event_id"] = "00000000-0000-4000-8000-000000000099"
    events.append(conflict)

    result = validate_anonymous_sequence(events)

    assert result.status == SequenceStatus.INVALID
    assert any(
        issue.code == ReasonCode.EVENT_SEQUENCE_CONFLICT
        for issue in result.issues
    )


def test_anonymous_elapsed_time_decrease_is_invalid():
    events = _sequence()
    events[-1]["run_elapsed_seconds"] = 30

    result = validate_anonymous_sequence(events)

    assert result.status == SequenceStatus.INVALID
    assert any(
        issue.code == ReasonCode.COUNTER_DECREASED
        and issue.path == ("run_elapsed_seconds",)
        for issue in result.issues
    )


def test_anonymous_run_id_must_match():
    events = _sequence()
    events[-2]["run_id"] = "30000000-0000-4000-8000-000000000099"

    result = validate_anonymous_sequence(events)

    assert result.status == SequenceStatus.INVALID
    assert any(
        issue.code == ReasonCode.CORRELATION_MISMATCH
        and issue.path == ("run_id",)
        for issue in result.issues
    )


def test_anonymous_event_after_run_end_is_invalid():
    events = _sequence()
    late_checkpoint = deepcopy(events[-2])
    late_checkpoint["event_id"] = (
        "00000000-0000-4000-8000-000000000098"
    )
    late_checkpoint["event_sequence"] = 6
    late_checkpoint["checkpoint_number"] = 2
    late_checkpoint["run_elapsed_seconds"] = 180
    events.append(late_checkpoint)

    result = validate_anonymous_sequence(events)

    assert result.status == SequenceStatus.INVALID
    assert any(
        issue.code == ReasonCode.EVENT_ORDER_INVALID
        and issue.path == ("event_sequence",)
        for issue in result.issues
    )


def test_anonymous_selection_must_follow_shown_choice():
    events = _sequence()
    events[0]["event_sequence"] = 2
    events[1]["event_sequence"] = 1

    result = validate_anonymous_sequence(events)

    assert result.status == SequenceStatus.INVALID
    assert any(
        issue.code == ReasonCode.EVENT_ORDER_INVALID
        and issue.path == ("event_sequence",)
        for issue in result.issues
    )
