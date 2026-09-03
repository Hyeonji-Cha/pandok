# 여러 수신 날짜에 나뉜 Bronze 이벤트를 최초 수신일 기준의 Silver 배치로 묶는다.
# 날짜 경계 이후 도착한 이벤트도 같은 Run에 연결하고 과도한 지연을 격리하기 위해 필요하다.

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Any

from pandok_contracts import ReasonCode, SequenceStatus, ValidationIssue

from .run_reconstruction import ReconstructedRun, reconstruct_runs


DEFAULT_ALLOWED_LATENESS = timedelta(hours=24)


@dataclass(frozen=True, slots=True)
class SilverBatchResult:
    """한 수신 날짜에 귀속된 Run과 전체 복원 Run 개수를 나타낸다."""

    received_date: date
    runs: tuple[ReconstructedRun, ...]
    reconstructed_run_count: int


def _parse_received_date(value: str) -> date:
    """배치 날짜가 정확한 YYYY-MM-DD 형식인지 검사한다."""

    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("received_date must use YYYY-MM-DD") from error
    if parsed.isoformat() != value:
        raise ValueError("received_date must use YYYY-MM-DD")
    return parsed


def reconstruct_received_date_batch(
    bronze_records: Iterable[Mapping[str, Any]],
    received_date: str,
    *,
    allowed_lateness: timedelta = DEFAULT_ALLOWED_LATENESS,
) -> SilverBatchResult:
    """전체 Bronze 범위에서 지정된 최초 수신일의 Run을 복원한다."""

    if allowed_lateness <= timedelta(0):
        raise ValueError("allowed_lateness must be positive")

    target_date = _parse_received_date(received_date)
    reconstructed = reconstruct_runs(bronze_records)
    target_runs: list[ReconstructedRun] = []

    for run in reconstructed:
        first_received_at = min(
            event.first_received_at for event in run.events
        )
        if first_received_at.date() != target_date:
            continue

        cutoff = first_received_at + allowed_lateness
        late_issues = tuple(
            ValidationIssue(
                ReasonCode.EVENT_ARRIVAL_TOO_LATE,
                "Event arrived after the Silver batch lateness window",
                ("metadata", "received_at"),
                str(event.event["event_id"]),
            )
            for event in run.events
            if event.first_received_at > cutoff
        )
        if late_issues:
            run = replace(
                run,
                status=SequenceStatus.INVALID,
                issues=(*run.issues, *late_issues),
            )
        target_runs.append(run)

    return SilverBatchResult(
        received_date=target_date,
        runs=tuple(target_runs),
        reconstructed_run_count=len(reconstructed),
    )
