# Bronze에 저장된 retry 포함 이벤트를 Run 단위의 신뢰 가능한 Silver 입력으로 복원한다.
# 네트워크 도착 순서와 중복이 분석 결과를 바꾸지 않게 하고, 불완전·오류 Run을 구분하기 위해 필요하다.

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
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
class ReconstructedEvent:
    """중복 제거된 이벤트와 최초 AWS 수신 정보를 함께 보관한다."""

    event: dict[str, Any]
    first_received_at: datetime
    ingestion_channel: str


@dataclass(frozen=True, slots=True)
class ReconstructedRun:
    """Run 복원 결과와 품질 판정 근거를 함께 보관한다."""

    run_id: str
    source_type: str
    status: SequenceStatus
    events: tuple[ReconstructedEvent, ...]
    issues: tuple[ValidationIssue, ...]
    input_event_count: int
    unique_event_count: int
    exact_retry_count: int
    conflicting_duplicate_count: int


@dataclass(frozen=True, slots=True)
class _BronzeEvent:
    """복원 중에 사용하는 단일 Bronze 이벤트와 수신 metadata다."""

    event: dict[str, Any]
    received_at: datetime
    ingestion_channel: str


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
) -> _BronzeEvent:
    """Bronze wrapper에서 원본 이벤트와 수신 metadata를 꺼낸다."""

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

    metadata = bronze_record.get("metadata")
    if not isinstance(metadata, Mapping):
        raise SilverInputError(
            f"Bronze record {record_index} has no metadata object"
        )

    received_at_text = metadata.get("received_at")
    ingestion_channel = metadata.get("ingestion_channel")
    if not isinstance(received_at_text, str) or not isinstance(
        ingestion_channel,
        str,
    ):
        raise SilverInputError(
            f"Bronze record {record_index} has invalid metadata"
        )

    try:
        received_at = datetime.fromisoformat(
            received_at_text.replace("Z", "+00:00")
        )
    except ValueError as error:
        raise SilverInputError(
            f"Bronze record {record_index} has invalid received_at"
        ) from error
    if received_at.tzinfo is None or received_at.utcoffset() is None:
        raise SilverInputError(
            f"Bronze record {record_index} has timezone-naive received_at"
        )

    # 호출자가 보유한 Bronze 객체를 정렬·중복 제거 과정에서 변경하지 않는다.
    return _BronzeEvent(
        event=deepcopy(dict(event)),
        received_at=received_at.astimezone(timezone.utc),
        ingestion_channel=ingestion_channel,
    )


def _deduplicate_run_events(
    events: list[_BronzeEvent],
) -> tuple[list[ReconstructedEvent], int, int]:
    """정상 retry와 본문 충돌을 구분하며 Silver 이벤트를 한 건씩 남긴다."""

    events_by_id: dict[str, list[_BronzeEvent]] = defaultdict(list)
    for bronze_event in events:
        events_by_id[str(bronze_event.event["event_id"])].append(
            bronze_event
        )

    unique: list[ReconstructedEvent] = []
    exact_retry_count = 0
    conflicting_duplicate_count = 0

    for duplicates in events_by_id.values():
        # S3 파일을 읽은 순서가 달라도 가장 이른 AWS 수신 기록을 동일하게 선택한다.
        ordered = sorted(
            duplicates,
            key=lambda item: (
                item.received_at,
                _canonical_event(item.event),
            ),
        )
        selected = ordered[0]
        selected_canonical = _canonical_event(selected.event)
        unique.append(
            ReconstructedEvent(
                event=selected.event,
                first_received_at=selected.received_at,
                ingestion_channel=selected.ingestion_channel,
            )
        )

        for duplicate in ordered[1:]:
            if _canonical_event(duplicate.event) == selected_canonical:
                exact_retry_count += 1
            else:
                # 충돌 이벤트도 출력에서는 제거하지만 정상 retry와 별도로 기록한다.
                conflicting_duplicate_count += 1

    unique.sort(key=lambda item: int(item.event["event_sequence"]))
    return (
        unique,
        exact_retry_count,
        conflicting_duplicate_count,
    )


def reconstruct_runs(
    bronze_records: Iterable[Mapping[str, Any]],
) -> list[ReconstructedRun]:
    """Bronze 레코드를 run_id별로 복원하고 품질 상태를 판정한다."""

    grouped: dict[str, list[_BronzeEvent]] = defaultdict(list)

    for index, bronze_record in enumerate(bronze_records):
        if not isinstance(bronze_record, Mapping):
            raise SilverInputError(
                f"Bronze record {index} must be a JSON object"
            )
        bronze_event = _extract_event(bronze_record, index)
        grouped[str(bronze_event.event["run_id"])].append(
            bronze_event
        )

    # 같은 event_id가 서로 다른 Run에서 사용된 경우 양쪽 Run을 INVALID로 만든다.
    event_owners: dict[str, tuple[str, str]] = {}
    cross_run_issues: dict[str, list[ValidationIssue]] = defaultdict(list)
    for run_id, events in grouped.items():
        for bronze_event in events:
            event = bronze_event.event
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
        input_records = grouped[run_id]
        input_events = [record.event for record in input_records]
        validation = validate_anonymous_sequence(input_events)
        (
            unique_events,
            exact_retry_count,
            conflicting_duplicate_count,
        ) = _deduplicate_run_events(input_records)
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
                source_type=str(unique_events[0].event["source_type"]),
                status=status,
                events=tuple(unique_events),
                issues=tuple(issues),
                input_event_count=len(input_records),
                unique_event_count=len(unique_events),
                exact_retry_count=exact_retry_count,
                conflicting_duplicate_count=conflicting_duplicate_count,
            )
        )

    return reconstructed
