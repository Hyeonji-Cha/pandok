# 날짜 경계를 넘겨 도착한 이벤트가 같은 Run으로 복원되고 과도한 지연은 격리되는지 검증한다.
# 일별 파일만 따로 처리해 하나의 Run이 둘로 갈라지는 회귀를 막기 위해 필요하다.

from __future__ import annotations

from datetime import datetime, timezone

from pandok_contracts import ReasonCode, SequenceStatus
from pandok_ingestion.bronze import build_bronze_record
from pandok_silver import reconstruct_received_date_batch


def _records_with_received_times(events, received_times):
    return [
        build_bronze_record(
            event,
            "turkiye_gateway",
            received_at=received_at,
        )
        for event, received_at in zip(
            events,
            received_times,
            strict=True,
        )
    ]


def test_reconstructs_run_across_received_date_boundary(
    anonymous_sequence,
):
    records = _records_with_received_times(
        anonymous_sequence,
        [
            datetime(2026, 9, 3, 23, 55, tzinfo=timezone.utc),
            datetime(2026, 9, 3, 23, 56, tzinfo=timezone.utc),
            datetime(2026, 9, 4, 0, 1, tzinfo=timezone.utc),
            datetime(2026, 9, 4, 0, 2, tzinfo=timezone.utc),
            datetime(2026, 9, 4, 0, 3, tzinfo=timezone.utc),
        ],
    )

    batch = reconstruct_received_date_batch(records, "2026-09-03")

    assert len(batch.runs) == 1
    assert batch.runs[0].status == SequenceStatus.VALID
    assert batch.runs[0].unique_event_count == len(anonymous_sequence)


def test_marks_event_after_lateness_window_invalid(
    anonymous_sequence,
):
    records = _records_with_received_times(
        anonymous_sequence,
        [
            datetime(2026, 9, 3, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 9, 3, 0, 1, tzinfo=timezone.utc),
            datetime(2026, 9, 3, 0, 2, tzinfo=timezone.utc),
            datetime(2026, 9, 3, 0, 3, tzinfo=timezone.utc),
            datetime(2026, 9, 4, 0, 1, tzinfo=timezone.utc),
        ],
    )

    run = reconstruct_received_date_batch(
        records,
        "2026-09-03",
    ).runs[0]

    assert run.status == SequenceStatus.INVALID
    assert any(
        issue.code == ReasonCode.EVENT_ARRIVAL_TOO_LATE
        for issue in run.issues
    )


def test_excludes_run_owned_by_another_received_date(
    anonymous_sequence,
):
    records = _records_with_received_times(
        anonymous_sequence,
        [
            datetime(2026, 9, 4, 0, index, tzinfo=timezone.utc)
            for index in range(len(anonymous_sequence))
        ],
    )

    batch = reconstruct_received_date_batch(records, "2026-09-03")

    assert batch.reconstructed_run_count == 1
    assert batch.runs == ()
