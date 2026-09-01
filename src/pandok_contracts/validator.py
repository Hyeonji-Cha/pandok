"""Single-event and Run-sequence validation for telemetry contracts v1 and v2."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .errors import (
    ReasonCode,
    SequenceStatus,
    SequenceValidationResult,
    ValidationIssue,
)


SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "contracts" / "telemetry-event-v1.schema.json"
)
ANONYMOUS_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "contracts" / "telemetry-event-v2.schema.json"
)

_PROHIBITED_KEYS = {
    "steamid",
    "steamnickname",
    "email",
    "emailaddress",
    "deviceid",
    "deviceidentifier",
    "authtoken",
    "authenticationtoken",
    "chat",
    "chatcontent",
    "preciselocation",
    "username",
    "userid",
    "ip",
    "ipaddress",
}

# 같은 Run의 모든 이벤트에서 동일해야 하는 식별·출처 필드
_CORRELATION_FIELDS = (
    "anonymous_user_id",
    "session_id",
    "run_id",
    "game_version",
    "schema_version",
    "source_type",
)

# 익명 v2 Run에서는 플레이어나 애플리케이션 Session을 연결하지 않는다.
_ANONYMOUS_CORRELATION_FIELDS = (
    "run_id",
    "game_version",
    "schema_version",
    "source_type",
)

_MONOTONIC_FIELDS = (
    "run_elapsed_seconds",
    "total_kills",
    "total_xp_collected",
    "total_gold_collected",
    "hearts_collected",
    "total_healing_received",
    "magnets_collected",
    "miniboss_waves_cleared",
)

_EVENT_DEFS = {
    "session_started": "sessionStarted",
    "run_started": "runStarted",
    "upgrade_options_shown": "upgradeOptionsShown",
    "upgrade_selected": "upgradeSelected",
    "run_checkpoint": "runCheckpoint",
    "run_ended": "runEnded",
}

_ANONYMOUS_EVENT_DEFS = {
    "run_started": "runStarted",
    "upgrade_options_shown": "upgradeOptionsShown",
    "upgrade_selected": "upgradeSelected",
    "run_checkpoint": "runCheckpoint",
    "run_ended": "runEnded",
}


# JSON Schema를 한 번만 읽고 재사용한다.
@lru_cache(maxsize=1)
def _schema() -> dict[str, Any]:
    with SCHEMA_PATH.open(encoding="utf-8") as handle:
        schema = json.load(handle)
    Draft202012Validator.check_schema(schema)
    return schema


# 이벤트 종류에 맞는 JSON Schema 검증기를 생성하고 캐시한다.
@lru_cache(maxsize=len(_EVENT_DEFS) + 1)
def _validator(event_name: str | None = None) -> Draft202012Validator:
    schema = _schema()
    definition = _EVENT_DEFS.get(event_name or "")
    if definition is None:
        validation_schema = schema
    else:
        validation_schema = {
            "$schema": schema["$schema"],
            "$defs": schema["$defs"],
            "$ref": f"#/$defs/{definition}",
        }
    return Draft202012Validator(
        validation_schema,
        format_checker=FormatChecker(),
    )


# 익명 v2 JSON Schema도 한 번만 읽어 이후 검증에서 재사용한다.
@lru_cache(maxsize=1)
def _anonymous_schema() -> dict[str, Any]:
    with ANONYMOUS_SCHEMA_PATH.open(encoding="utf-8") as handle:
        schema = json.load(handle)
    Draft202012Validator.check_schema(schema)
    return schema


# v2 이벤트 종류에 맞는 독립 검증기를 만들어 v1 동작과 분리한다.
@lru_cache(maxsize=len(_ANONYMOUS_EVENT_DEFS) + 1)
def _anonymous_validator(event_name: str | None = None) -> Draft202012Validator:
    schema = _anonymous_schema()
    definition = _ANONYMOUS_EVENT_DEFS.get(event_name or "")
    if definition is None:
        validation_schema = schema
    else:
        validation_schema = {
            "$schema": schema["$schema"],
            "$defs": schema["$defs"],
            "$ref": f"#/$defs/{definition}",
        }
    return Draft202012Validator(
        validation_schema,
        format_checker=FormatChecker(),
    )


# 개인정보 필드 비교를 위해 키의 대소문자와 구분 문자를 제거한다.
def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.casefold())


# 중첩된 객체와 배열까지 탐색해 금지된 개인정보 필드를 찾는다.
def _privacy_issues(
    value: Any,
    path: tuple[str | int, ...] = (),
    event_id: str | None = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = (*path, str(key))
            if _normalize_key(str(key)) in _PROHIBITED_KEYS:
                issues.append(
                    ValidationIssue(
                        ReasonCode.PROHIBITED_FIELD,
                        f"Prohibited direct-identifier field: {key}",
                        child_path,
                        event_id,
                    )
                )
            issues.extend(_privacy_issues(child, child_path, event_id))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(_privacy_issues(child, (*path, index), event_id))
    return issues


# 단일 이벤트의 개인정보, Schema, 선택지 규칙을 검증한다.
def validate_event(event: Any) -> list[ValidationIssue]:
    """Return all contract issues for one event; an empty list means valid."""

    if not isinstance(event, Mapping):
        return [
            ValidationIssue(
                ReasonCode.SCHEMA_INVALID,
                "An event must be a JSON object",
            )
        ]

    event_id = event.get("event_id") if isinstance(event.get("event_id"), str) else None
    privacy = _privacy_issues(event, event_id=event_id)
    if privacy:
        return privacy

    event_name = event.get("event_name")
    errors = sorted(
        _validator(event_name if isinstance(event_name, str) else None).iter_errors(event),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    schema_issues = [
        ValidationIssue(
            ReasonCode.SCHEMA_INVALID,
            error.message,
            tuple(error.absolute_path),
            event_id,
        )
        for error in errors
    ]
    if schema_issues:
        return schema_issues

    if (
        event_name == "upgrade_options_shown"
        and event.get("choice_source") == "statue"
    ):
        options = event.get("options")
        if isinstance(options, list):
            item_ids = [
                option.get("item_id")
                for option in options
                if isinstance(option, Mapping)
            ]
            if len(item_ids) != len(set(item_ids)):
                return [
                    ValidationIssue(
                        ReasonCode.CHOICE_MISMATCH,
                        "Statue options must use distinct item_id values",
                        ("options",),
                        event_id,
                    )
                ]

    return []


# 익명 v2 이벤트에서 금지 필드와 Schema, 선택지 구조를 검증한다.
def validate_anonymous_event(event: Any) -> list[ValidationIssue]:
    """Return all anonymous v2 contract issues for one event."""

    if not isinstance(event, Mapping):
        return [
            ValidationIssue(
                ReasonCode.SCHEMA_INVALID,
                "An event must be a JSON object",
            )
        ]

    event_id = event.get("event_id") if isinstance(event.get("event_id"), str) else None
    privacy = _privacy_issues(event, event_id=event_id)
    if privacy:
        return privacy

    event_name = event.get("event_name")
    errors = sorted(
        _anonymous_validator(
            event_name if isinstance(event_name, str) else None
        ).iter_errors(event),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    schema_issues = [
        ValidationIssue(
            ReasonCode.SCHEMA_INVALID,
            error.message,
            tuple(error.absolute_path),
            event_id,
        )
        for error in errors
    ]
    if schema_issues:
        return schema_issues

    if (
        event_name == "upgrade_options_shown"
        and event.get("choice_source") == "statue"
    ):
        options = event.get("options")
        if isinstance(options, list):
            item_ids = [
                option.get("item_id")
                for option in options
                if isinstance(option, Mapping)
            ]
            if len(item_ids) != len(set(item_ids)):
                return [
                    ValidationIssue(
                        ReasonCode.CHOICE_MISMATCH,
                        "Statue options must use distinct item_id values",
                        ("options",),
                        event_id,
                    )
                ]

    return []


# 이벤트 내용을 일정한 문자열로 바꿔 재시도와 충돌을 비교한다.
def _canonical(event: Mapping[str, Any]) -> str:
    return json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# UTC 이벤트 시각 문자열을 정렬 가능한 datetime으로 변환한다.
def _event_time(event: Mapping[str, Any]) -> datetime:
    return datetime.fromisoformat(str(event["event_time"]).replace("Z", "+00:00"))


# 이벤트 정보와 필드 경로를 포함한 표준 검증 오류를 만든다.
def _issue(
    code: ReasonCode,
    message: str,
    event: Mapping[str, Any],
    *path: str | int,
) -> ValidationIssue:
    event_id = event.get("event_id")
    return ValidationIssue(
        code,
        message,
        tuple(path),
        event_id if isinstance(event_id, str) else None,
    )


# 동일 event_id의 재시도는 합치고 내용이 다르면 충돌로 기록한다.
def _deduplicate(
    events: Sequence[Mapping[str, Any]],
) -> tuple[list[Mapping[str, Any]], list[ValidationIssue]]:
    seen: dict[str, str] = {}
    unique: list[Mapping[str, Any]] = []
    issues: list[ValidationIssue] = []
    for event in events:
        event_id = str(event["event_id"])
        content = _canonical(event)
        if event_id not in seen:
            seen[event_id] = content
            unique.append(event)
        elif seen[event_id] != content:
            issues.append(
                _issue(
                    ReasonCode.DUPLICATE_CONFLICT,
                    "The same event_id was delivered with different content",
                    event,
                    "event_id",
                )
            )
    return unique, issues


# 이벤트 순서와 Run 전체의 상관관계·누적 상태를 검증한다.
def validate_sequence(events: Any) -> list[ValidationIssue]:
    """Validate a P0 sequence independent of network arrival order."""

    if not isinstance(events, list):
        return [
            ValidationIssue(
                ReasonCode.SCHEMA_INVALID,
                "A sequence must be a JSON array of events",
            )
        ]

    event_issues = [issue for event in events for issue in validate_event(event)]
    if event_issues:
        return event_issues

    typed_events: list[Mapping[str, Any]] = list(events)
    unique, issues = _deduplicate(typed_events)
    ordered = sorted(unique, key=_event_time)
    run_events = [event for event in ordered if isinstance(event.get("run_id"), str)]
    starts = [event for event in run_events if event["event_name"] == "run_started"]
    if not starts:
        issues.append(
            ValidationIssue(
                ReasonCode.MISSING_RUN_START,
                "The sequence contains no run_started event",
            )
        )
        return issues

    start = starts[0]
    for event in run_events:
        for field in _CORRELATION_FIELDS:
            if event.get(field) != start.get(field):
                issues.append(
                    _issue(
                        ReasonCode.CORRELATION_MISMATCH,
                        f"{field} does not match run_started",
                        event,
                        field,
                    )
                )

    start_time = _event_time(start)
    for event in run_events:
        if _event_time(event) >= start_time:
            continue
        is_initial_weapon_choice = (
            event["event_name"] in {"upgrade_options_shown", "upgrade_selected"}
            and event.get("choice_source") == "level_up_weapon"
            and event.get("run_elapsed_seconds") == 0
        )
        if not is_initial_weapon_choice:
            issues.append(
                _issue(
                    ReasonCode.EVENT_ORDER_INVALID,
                    "Only a zero-time initial level_up_weapon choice may precede run_started",
                    event,
                    "event_time",
                )
            )

    shown_choices: dict[str, Mapping[str, Any]] = {}
    for event in run_events:
        if event["event_name"] != "upgrade_options_shown":
            continue
        choice_id = str(event["choice_id"])
        prior = shown_choices.get(choice_id)
        if prior is not None and _canonical(prior) != _canonical(event):
            issues.append(
                _issue(
                    ReasonCode.CHOICE_MISMATCH,
                    "The same choice_id identifies different shown choices",
                    event,
                    "choice_id",
                )
            )
            continue
        shown_choices[choice_id] = event

    previous_values: dict[str, float] = {}
    previous_checkpoint = 0
    previous_choice_sequence = 0
    ended = False

    for event in run_events:
        name = str(event["event_name"])
        if ended:
            issues.append(
                _issue(
                    ReasonCode.EVENT_ORDER_INVALID,
                    "An event occurs after run_ended in gameplay time",
                    event,
                    "event_time",
                )
            )

        if name == "upgrade_options_shown":
            choice_sequence = int(event["choice_sequence"])
            if choice_sequence <= previous_choice_sequence:
                issues.append(
                    _issue(
                        ReasonCode.COUNTER_DECREASED,
                        "choice_sequence must strictly increase for shown choices",
                        event,
                        "choice_sequence",
                    )
                )
            previous_choice_sequence = choice_sequence
            slots = [option["slot"] for option in event["options"]]
            expected_slots = (
                {1, 2, 3} if event["choice_source"] == "statue" else {1, 2}
            )
            if set(slots) != expected_slots or len(slots) != len(expected_slots):
                issues.append(
                    _issue(
                        ReasonCode.CHOICE_MISMATCH,
                        "Upgrade options do not match the source-specific slot set",
                        event,
                        "options",
                    )
                )
        if name == "upgrade_selected":
            shown = shown_choices.get(str(event["choice_id"]))
            if shown is None:
                issues.append(
                    _issue(
                        ReasonCode.CHOICE_NOT_FOUND,
                        "No earlier upgrade_options_shown uses this choice_id",
                        event,
                        "choice_id",
                    )
                )
            else:
                if _event_time(shown) > _event_time(event):
                    issues.append(
                        _issue(
                            ReasonCode.EVENT_ORDER_INVALID,
                            "upgrade_selected occurs before its upgrade_options_shown",
                            event,
                            "event_time",
                        )
                    )
                expected = {
                    (
                        option["slot"],
                        option["item_id"],
                        option["rarity"],
                    )
                    for option in shown["options"]
                }
                actual = (
                    event["selected_slot"],
                    event["selected_item_id"],
                    event["selected_rarity"],
                )
                if (
                    actual not in expected
                    or event["choice_sequence"] != shown["choice_sequence"]
                    or event["choice_source"] != shown["choice_source"]
                ):
                    issues.append(
                        _issue(
                            ReasonCode.CHOICE_MISMATCH,
                            "Selected upgrade does not match the linked shown options",
                            event,
                            "choice_id",
                        )
                    )

        if name == "run_checkpoint":
            checkpoint = int(event["checkpoint_number"])
            if checkpoint <= previous_checkpoint:
                issues.append(
                    _issue(
                        ReasonCode.COUNTER_DECREASED,
                        "checkpoint_number must strictly increase",
                        event,
                        "checkpoint_number",
                    )
                )
            previous_checkpoint = checkpoint
            expected_elapsed = checkpoint * 60
            if float(event["run_elapsed_seconds"]) != expected_elapsed:
                issues.append(
                    _issue(
                        ReasonCode.EVENT_ORDER_INVALID,
                        "run_elapsed_seconds must equal checkpoint_number multiplied by 60",
                        event,
                        "run_elapsed_seconds",
                    )
                )

        comparable = dict(event)
        if name == "run_ended":
            comparable["run_elapsed_seconds"] = event["run_duration_seconds"]

        for field in _MONOTONIC_FIELDS:
            value = comparable.get(field)
            if isinstance(value, int | float):
                if field in previous_values and value < previous_values[field]:
                    issues.append(
                        _issue(
                            ReasonCode.COUNTER_DECREASED,
                            f"{field} decreased within the Run",
                            event,
                            field,
                        )
                    )
                previous_values[field] = float(value)

        if name == "run_ended":
            ended = True

    return issues


_INCOMPLETE_SEQUENCE_CODES = {
    ReasonCode.MISSING_RUN_START,
    ReasonCode.MISSING_RUN_END,
    ReasonCode.EVENT_SEQUENCE_GAP,
    ReasonCode.CHOICE_NOT_FOUND,
}


# 오류 종류를 바탕으로 Run을 정상·부분 수집·잘못된 데이터로 구분한다.
def _anonymous_sequence_result(
    issues: Sequence[ValidationIssue],
) -> SequenceValidationResult:
    if not issues:
        status = SequenceStatus.VALID
    elif all(issue.code in _INCOMPLETE_SEQUENCE_CODES for issue in issues):
        status = SequenceStatus.INCOMPLETE
    else:
        status = SequenceStatus.INVALID
    return SequenceValidationResult(status, tuple(issues))


# v2 이벤트를 도착 순서가 아닌 event_sequence로 재구성해 Run 상태를 판정한다.
def validate_anonymous_sequence(events: Any) -> SequenceValidationResult:
    """Assess one anonymous v2 Run as valid, incomplete, or invalid."""

    if not isinstance(events, list):
        return _anonymous_sequence_result(
            [
                ValidationIssue(
                    ReasonCode.SCHEMA_INVALID,
                    "A sequence must be a JSON array of events",
                )
            ]
        )

    event_issues = [
        issue
        for event in events
        for issue in validate_anonymous_event(event)
    ]
    if event_issues:
        return _anonymous_sequence_result(event_issues)

    typed_events: list[Mapping[str, Any]] = list(events)
    deduplicated, issues = _deduplicate(typed_events)

    # 동일 순서 번호에 서로 다른 논리 이벤트가 있으면 하나의 Run으로 확정할 수 없다.
    events_by_sequence: dict[int, Mapping[str, Any]] = {}
    for event in deduplicated:
        sequence_number = int(event["event_sequence"])
        prior = events_by_sequence.get(sequence_number)
        if prior is not None:
            issues.append(
                _issue(
                    ReasonCode.EVENT_SEQUENCE_CONFLICT,
                    "Different events use the same event_sequence",
                    event,
                    "event_sequence",
                )
            )
            continue
        events_by_sequence[sequence_number] = event

    ordered = [events_by_sequence[number] for number in sorted(events_by_sequence)]

    # Sequence 공백은 잘못된 Payload가 아니라 전송되지 않은 이벤트가 있을 가능성을 뜻한다.
    previous_sequence = 0
    for event in ordered:
        current_sequence = int(event["event_sequence"])
        if current_sequence > previous_sequence + 1:
            issues.append(
                _issue(
                    ReasonCode.EVENT_SEQUENCE_GAP,
                    (
                        "Missing event_sequence values between "
                        f"{previous_sequence} and {current_sequence}"
                    ),
                    event,
                    "event_sequence",
                )
            )
        previous_sequence = current_sequence

    starts = [event for event in ordered if event["event_name"] == "run_started"]
    endings = [event for event in ordered if event["event_name"] == "run_ended"]
    if not starts:
        issues.append(
            ValidationIssue(
                ReasonCode.MISSING_RUN_START,
                "The sequence contains no run_started event",
            )
        )
    elif len(starts) > 1:
        for duplicate_start in starts[1:]:
            issues.append(
                _issue(
                    ReasonCode.EVENT_ORDER_INVALID,
                    "The sequence contains more than one run_started event",
                    duplicate_start,
                    "event_name",
                )
            )

    if not endings:
        issues.append(
            ValidationIssue(
                ReasonCode.MISSING_RUN_END,
                "The sequence contains no run_ended event",
            )
        )
    elif len(endings) > 1:
        for duplicate_end in endings[1:]:
            issues.append(
                _issue(
                    ReasonCode.EVENT_ORDER_INVALID,
                    "The sequence contains more than one run_ended event",
                    duplicate_end,
                    "event_name",
                )
            )

    reference = starts[0] if starts else (ordered[0] if ordered else None)
    if reference is not None:
        for event in ordered:
            for field in _ANONYMOUS_CORRELATION_FIELDS:
                if event.get(field) != reference.get(field):
                    issues.append(
                        _issue(
                            ReasonCode.CORRELATION_MISMATCH,
                            f"{field} does not match the Run",
                            event,
                            field,
                        )
                    )

    if starts:
        start_sequence = int(starts[0]["event_sequence"])
        for event in ordered:
            if int(event["event_sequence"]) >= start_sequence:
                continue
            is_initial_weapon_choice = (
                event["event_name"]
                in {"upgrade_options_shown", "upgrade_selected"}
                and event.get("choice_source") == "level_up_weapon"
                and event.get("run_elapsed_seconds") == 0
            )
            if not is_initial_weapon_choice:
                issues.append(
                    _issue(
                        ReasonCode.EVENT_ORDER_INVALID,
                        "Only a zero-time initial weapon choice may precede run_started",
                        event,
                        "event_sequence",
                    )
                )

    shown_choices: dict[str, Mapping[str, Any]] = {}
    for event in ordered:
        if event["event_name"] != "upgrade_options_shown":
            continue
        choice_id = str(event["choice_id"])
        prior = shown_choices.get(choice_id)
        if prior is not None and _canonical(prior) != _canonical(event):
            issues.append(
                _issue(
                    ReasonCode.CHOICE_MISMATCH,
                    "The same choice_id identifies different shown choices",
                    event,
                    "choice_id",
                )
            )
            continue
        shown_choices[choice_id] = event

    previous_values: dict[str, float] = {}
    previous_checkpoint = 0
    previous_choice_sequence = 0
    ended = False

    for event in ordered:
        name = str(event["event_name"])
        if ended:
            issues.append(
                _issue(
                    ReasonCode.EVENT_ORDER_INVALID,
                    "An event occurs after run_ended in Run order",
                    event,
                    "event_sequence",
                )
            )

        if name == "upgrade_options_shown":
            choice_sequence = int(event["choice_sequence"])
            if choice_sequence <= previous_choice_sequence:
                issues.append(
                    _issue(
                        ReasonCode.COUNTER_DECREASED,
                        "choice_sequence must strictly increase for shown choices",
                        event,
                        "choice_sequence",
                    )
                )
            previous_choice_sequence = choice_sequence
            slots = [option["slot"] for option in event["options"]]
            expected_slots = (
                {1, 2, 3} if event["choice_source"] == "statue" else {1, 2}
            )
            if set(slots) != expected_slots or len(slots) != len(expected_slots):
                issues.append(
                    _issue(
                        ReasonCode.CHOICE_MISMATCH,
                        "Upgrade options do not match the source-specific slot set",
                        event,
                        "options",
                    )
                )

        if name == "upgrade_selected":
            shown = shown_choices.get(str(event["choice_id"]))
            if shown is None:
                issues.append(
                    _issue(
                        ReasonCode.CHOICE_NOT_FOUND,
                        "No upgrade_options_shown uses this choice_id",
                        event,
                        "choice_id",
                    )
                )
            else:
                if int(shown["event_sequence"]) >= int(event["event_sequence"]):
                    issues.append(
                        _issue(
                            ReasonCode.EVENT_ORDER_INVALID,
                            "upgrade_selected must follow upgrade_options_shown",
                            event,
                            "event_sequence",
                        )
                    )
                expected = {
                    (option["slot"], option["item_id"], option["rarity"])
                    for option in shown["options"]
                }
                actual = (
                    event["selected_slot"],
                    event["selected_item_id"],
                    event["selected_rarity"],
                )
                if (
                    actual not in expected
                    or event["choice_sequence"] != shown["choice_sequence"]
                    or event["choice_source"] != shown["choice_source"]
                ):
                    issues.append(
                        _issue(
                            ReasonCode.CHOICE_MISMATCH,
                            "Selected upgrade does not match the linked shown options",
                            event,
                            "choice_id",
                        )
                    )

        if name == "run_checkpoint":
            checkpoint = int(event["checkpoint_number"])
            if checkpoint <= previous_checkpoint:
                issues.append(
                    _issue(
                        ReasonCode.COUNTER_DECREASED,
                        "checkpoint_number must strictly increase",
                        event,
                        "checkpoint_number",
                    )
                )
            previous_checkpoint = checkpoint
            expected_elapsed = checkpoint * 60
            if float(event["run_elapsed_seconds"]) != expected_elapsed:
                issues.append(
                    _issue(
                        ReasonCode.EVENT_ORDER_INVALID,
                        "run_elapsed_seconds must equal checkpoint_number multiplied by 60",
                        event,
                        "run_elapsed_seconds",
                    )
                )

        for field in _MONOTONIC_FIELDS:
            value = event.get(field)
            if isinstance(value, int | float):
                if field in previous_values and value < previous_values[field]:
                    issues.append(
                        _issue(
                            ReasonCode.COUNTER_DECREASED,
                            f"{field} decreased within the Run",
                            event,
                            field,
                        )
                    )
                previous_values[field] = float(value)

        if name == "run_ended":
            ended = True

    return _anonymous_sequence_result(issues)
