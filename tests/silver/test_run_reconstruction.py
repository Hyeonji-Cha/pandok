# Bronze 이벤트를 Run별로 묶고 retry를 제거한 뒤 품질 상태를 유지하는지 검증한다.
# Silver 변환에서 도착 순서·중복 때문에 분석용 Run이 달라지는 회귀를 막기 위해 필요하다.

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from pandok_contracts import ReasonCode, SequenceStatus
from pandok_ingestion.bronze import build_bronze_record
from pandok_silver import reconstruct_runs


def _bronze_records(
    events: list[dict],
) -> list[dict]:
    received_at = datetime(2026, 9, 3, tzinfo=timezone.utc)
    return [
        build_bronze_record(
            event,
            "turkiye_gateway",
            received_at=received_at,
        )
        for event in events
    ]


def test_reconstructs_runs_in_sequence_and_removes_retry(
    anonymous_sequence,
):
    second_run = deepcopy(anonymous_sequence)
    second_run_id = "30000000-0000-4000-8000-000000000002"
    for index, event in enumerate(second_run, start=1):
        event["run_id"] = second_run_id
        event["event_id"] = (
            f"10000000-0000-4000-8000-{index:012d}"
        )

    retry = deepcopy(anonymous_sequence[-2])
    records = _bronze_records(
        list(reversed(anonymous_sequence)) + [retry] + second_run
    )

    runs = reconstruct_runs(records)

    assert len(runs) == 2
    first = runs[0]
    assert first.status == SequenceStatus.VALID
    assert [event["event_sequence"] for event in first.events] == [
        1,
        2,
        3,
        4,
        5,
    ]
    assert first.input_event_count == 6
    assert first.unique_event_count == 5
    assert first.exact_retry_count == 1
    assert first.conflicting_duplicate_count == 0
    assert first.input_event_count == (
        first.unique_event_count
        + first.exact_retry_count
        + first.conflicting_duplicate_count
    )


def test_preserves_incomplete_run_status(anonymous_sequence):
    records = _bronze_records(anonymous_sequence[:-1])

    run = reconstruct_runs(records)[0]

    assert run.status == SequenceStatus.INCOMPLETE
    assert any(
        issue.code == ReasonCode.MISSING_RUN_END
        for issue in run.issues
    )


def test_marks_conflicting_retry_as_invalid(anonymous_sequence):
    conflict = deepcopy(anonymous_sequence[-2])
    conflict["game_version"] = "1.2.1"
    records = _bronze_records(anonymous_sequence + [conflict])

    run = reconstruct_runs(records)[0]

    assert run.status == SequenceStatus.INVALID
    assert run.unique_event_count == len(anonymous_sequence)
    assert run.exact_retry_count == 0
    assert run.conflicting_duplicate_count == 1
    assert run.input_event_count == (
        run.unique_event_count
        + run.exact_retry_count
        + run.conflicting_duplicate_count
    )
    assert any(
        issue.code == ReasonCode.DUPLICATE_CONFLICT
        for issue in run.issues
    )


def test_marks_event_id_reused_across_runs_as_invalid(
    anonymous_sequence,
):
    second_run = deepcopy(anonymous_sequence)
    second_run_id = "30000000-0000-4000-8000-000000000002"
    for index, event in enumerate(second_run, start=1):
        event["run_id"] = second_run_id
        event["event_id"] = (
            f"10000000-0000-4000-8000-{index:012d}"
        )
    second_run[0]["event_id"] = anonymous_sequence[0]["event_id"]

    records = _bronze_records(anonymous_sequence + second_run)

    runs = reconstruct_runs(records)

    assert [run.status for run in runs] == [
        SequenceStatus.INVALID,
        SequenceStatus.INVALID,
    ]
    assert all(
        any(
            issue.code == ReasonCode.DUPLICATE_CONFLICT
            for issue in run.issues
        )
        for run in runs
    )
