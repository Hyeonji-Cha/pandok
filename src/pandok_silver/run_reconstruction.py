# Bronze에 저장된 retry 포함 이벤트를 Run 단위의 신뢰 가능한 Silver 입력으로 복원한다.
# 네트워크 도착 순서와 중복이 분석 결과를 바꾸지 않게 하고, 불완전·오류 Run을 구분하기 위해 필요하다.

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from pandok_contracts import (
    ReasonCode,
    SequenceStatus,
    ValidationIssue,
    validate_anonymous_sequence,
)


class SilverInputError(ValueError):
    """Bronze wrapper 자체가 Silver에서 읽을 수 없는 경우를 나타낸다."""


@dataclass(frozen=True, slots=True)
class ReconstructedRun:
    """Run 복원 결과와 품질 판정 근거를 함께 보관한다."""

    run_id: str
    source_type: str
    status: SequenceStatus
    events: tuple[dict[str, Any], ...]
    issues: tuple[ValidationIssue, ...]
    input_event_count: int
    unique_event_count: int
    duplicate_event_count: int


def _canonical_event(event: Mapping[str, Any]) -> str:
    """JSON 키 순서와 무관하게 retry 본문을 비교할 문자열을 만든다."""

    return json.dumps(
        event,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _extract_event(
    bronze_record: Mapping[str, Any],
    record_index: int,
) -> dict[str, Any]:
    """Bronze wrapper에서 계약 검증 대상인 원본 이벤트를 꺼낸다."""

    if bronze_record.get("bronze_record_version") != 1:
        raise SilverInputError(
            f"Bronze record {record_index} has an unsupported version"
        )

    event = bronze_record.get("event")
    if not isinstance(event, Mapping):
        raise SilverInputError(
            f"Bronze record {record_index} has no event object"
        )

    run_id = event.get("run_id")
    event_id = event.get("event_id")
    if not isinstance(run_id, str) or not isinstance(event_id, str):
        raise SilverInputError(
            f"Bronze record {record_index} has no Run or event ID"
        )

    # 호출자가 보유한 Bronze 객체를 정렬·중복 제거 과정에서 변경하지 않는다.
    return deepcopy(dict(event))


def _deduplicate_run_events(
    events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """같은 event_id와 같은 본문의 retry만 Silver 이벤트에서 제거한다."""

    seen: dict[str, str] = {}
    unique: list[dict[str, Any]] = []
    duplicate_count = 0

    for event in events:
        event_id = str(event["event_id"])
        canonical = _canonical_event(event)
        previous = seen.get(event_id)

        if previous is None:
            seen[event_id] = canonical
            unique.append(event)
        elif previous == canonical:
            duplicate_count += 1
        # 같은 ID의 다른 본문은 validator가 INVALID로 판정한다.
        # Silver 출력에는 먼저 도착한 한 건만 남기고 충돌 근거는 issues에 보존한다.

    unique.sort(key=lambda event: int(event["event_sequence"]))
    return unique, duplicate_count


def reconstruct_runs(
    bronze_records: Iterable[Mapping[str, Any]],
) -> list[ReconstructedRun]:
    """Bronze 레코드를 run_id별로 복원하고 품질 상태를 판정한다."""

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for index, bronze_record in enumerate(bronze_records):
        if not isinstance(bronze_record, Mapping):
            raise SilverInputError(
                f"Bronze record {index} must be a JSON object"
            )
        event = _extract_event(bronze_record, index)
        grouped[str(event["run_id"])].append(event)

    # 같은 event_id가 서로 다른 Run에서 사용된 경우 양쪽 Run을 INVALID로 만든다.
    event_owners: dict[str, tuple[str, str]] = {}
    cross_run_issues: dict[str, list[ValidationIssue]] = defaultdict(list)
    for run_id, events in grouped.items():
        for event in events:
            event_id = str(event["event_id"])
            canonical = _canonical_event(event)
            previous = event_owners.get(event_id)
            if previous is None:
                event_owners[event_id] = (run_id, canonical)
                continue

            previous_run_id, previous_canonical = previous
            if previous_run_id == run_id or previous_canonical == canonical:
                continue

            issue = ValidationIssue(
                ReasonCode.DUPLICATE_CONFLICT,
                "The same event_id is used by different Runs",
                ("event_id",),
                event_id,
            )
            cross_run_issues[previous_run_id].append(issue)
            cross_run_issues[run_id].append(issue)

    reconstructed: list[ReconstructedRun] = []
    for run_id in sorted(grouped):
        input_events = grouped[run_id]
        validation = validate_anonymous_sequence(input_events)
        unique_events, duplicate_count = _deduplicate_run_events(
            input_events
        )
        issues = (
            *validation.issues,
            *cross_run_issues.get(run_id, ()),
        )
        status = (
            SequenceStatus.INVALID
            if cross_run_issues.get(run_id)
            else validation.status
        )

        reconstructed.append(
            ReconstructedRun(
                run_id=run_id,
                source_type=str(unique_events[0]["source_type"]),
                status=status,
                events=tuple(unique_events),
                issues=tuple(issues),
                input_event_count=len(input_events),
                unique_event_count=len(unique_events),
                duplicate_event_count=duplicate_count,
            )
        )

    return reconstructed
