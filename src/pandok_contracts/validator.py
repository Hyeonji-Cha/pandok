# AWS로 전달되는 익명 v2 이벤트와 Run 순서를 검증한다.
# 개인정보가 포함되거나 순서가 깨진 이벤트가 Bronze·Silver로 넘어가는 것을 막기 위해 필요하다.

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
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
    Path(__file__).resolve().parents[2]
    / "contracts"
    / "telemetry-event-v2.schema.json"
)

# 계정·기기·네트워크·인증정보와 영구 식별자로 해석될 수 있는 키를 차단한다.
_PROHIBITED_KEYS = frozenset(
    {
        "accountdata",
        "accountid",
        "accountidentifier",
        "auth",
        "authenticationtoken",
        "authorization",
        "authtoken",
        "cfconnectingip",
        "chat",
        "chatcontent",
        "clientip",
        "cookie",
        "deviceid",
        "deviceidentifier",
        "discordid",
        "email",
        "emailaddress",
        "filepath",
        "fingerprint",
        "forwarded",
        "fullname",
        "gps",
        "hardwareid",
        "hardwareuuid",
        "headers",
        "installationid",
        "installationidentifier",
        "ip",
        "ipaddress",
        "latitude",
        "location",
        "longitude",
        "mac",
        "macaddress",
        "machineid",
        "machineidentifier",
        "name",
        "nickname",
        "operatingsystemusername",
        "originalheaders",
        "persistentid",
        "persistentidentifier",
        "phone",
        "phonenumber",
        "playerid",
        "playeridentifier",
        "preciselocation",
        "referer",
        "requestheaders",
        "session",
        "sessionid",
        "sessiontoken",
        "sourceip",
        "steamaccountid",
        "steamid",
        "steamnickname",
        "token",
        "trueclientip",
        "useragent",
        "userid",
        "useridentifier",
        "username",
        "xforwardedfor",
        "xrealip",
    }
)

_CORRELATION_FIELDS = (
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
    "run_started": "runStarted",
    "upgrade_options_shown": "upgradeOptionsShown",
    "upgrade_selected": "upgradeSelected",
    "run_checkpoint": "runCheckpoint",
    "run_ended": "runEnded",
}

_INCOMPLETE_SEQUENCE_CODES = {
    ReasonCode.MISSING_RUN_START,
    ReasonCode.MISSING_RUN_END,
    ReasonCode.EVENT_SEQUENCE_GAP,
    ReasonCode.CHOICE_NOT_FOUND,
}


# JSON Schema는 최초 한 번만 읽어 이후 검증 비용을 줄인다.
@lru_cache(maxsize=1)
def _schema() -> dict[str, Any]:
    with SCHEMA_PATH.open(encoding="utf-8") as handle:
        schema = json.load(handle)
    Draft202012Validator.check_schema(schema)
    return schema


# 이벤트 종류별 Schema 검증기도 캐시해 반복 수집 시 파일 처리를 줄인다.
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


# 키 비교 전에 대소문자와 밑줄·하이픈 같은 구분 문자를 제거한다.
def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.casefold())


# 중첩 객체와 배열까지 순회하며 금지된 개인정보 필드를 찾는다.
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
            issues.extend(
                _privacy_issues(child, (*path, index), event_id)
            )
    return issues


# 단일 v2 이벤트의 개인정보와 JSON Schema, 선택지 규칙을 검증한다.
def validate_anonymous_event(event: Any) -> list[ValidationIssue]:
    """Return all anonymous v2 contract issues for one event."""

    if not isinstance(event, Mapping):
        return [
            ValidationIssue(
                ReasonCode.SCHEMA_INVALID,
                "An event must be a JSON object",
            )
        ]

    event_id = (
        event.get("event_id")
        if isinstance(event.get("event_id"), str)
        else None
    )
    privacy = _privacy_issues(event, event_id=event_id)
    if privacy:
        return privacy

    event_name = event.get("event_name")
    errors = sorted(
        _validator(
            event_name if isinstance(event_name, str) else None
        ).iter_errors(event),
        key=lambda error: tuple(
            str(part) for part in error.absolute_path
        ),
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


# 이벤트 내용을 일정한 문자열로 바꿔 retry와 충돌을 비교한다.
def _canonical(event: Mapping[str, Any]) -> str:
    return json.dumps(
        event,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


# 이벤트와 필드 경로가 포함된 표준 검증 오류를 만든다.
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


# 동일 event_id의 같은 retry는 합치고 내용이 다르면 충돌로 기록한다.
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


# 오류 종류에 따라 Run을 정상·부분 수집·잘못된 데이터로 구분한다.
def _sequence_result(
    issues: Sequence[ValidationIssue],
) -> SequenceValidationResult:
    if not issues:
        status = SequenceStatus.VALID
    elif all(
        issue.code in _INCOMPLETE_SEQUENCE_CODES
        for issue in issues
    ):
        status = SequenceStatus.INCOMPLETE
    else:
        status = SequenceStatus.INVALID
    return SequenceValidationResult(status, tuple(issues))


# 도착 시각이 아니라 event_sequence를 기준으로 v2 Run 전체를 복원·검증한다.
def validate_anonymous_sequence(events: Any) -> SequenceValidationResult:
    """Assess one anonymous v2 Run as valid, incomplete, or invalid."""

    if not isinstance(events, list):
        return _sequence_result(
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
        return _sequence_result(event_issues)

    typed_events: list[Mapping[str, Any]] = list(events)
    deduplicated, issues = _deduplicate(typed_events)

    events_by_sequence: dict[int, Mapping[str, Any]] = {}
    for event in deduplicated:
        sequence_number = int(event["event_sequence"])
        if sequence_number in events_by_sequence:
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

    ordered = [
        events_by_sequence[number]
        for number in sorted(events_by_sequence)
    ]

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

    starts = [
        event
        for event in ordered
        if event["event_name"] == "run_started"
    ]
    endings = [
        event
        for event in ordered
        if event["event_name"] == "run_ended"
    ]

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
            for field in _CORRELATION_FIELDS:
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
            initial_weapon_choice = (
                event["event_name"]
                in {"upgrade_options_shown", "upgrade_selected"}
                and event.get("choice_source") == "level_up_weapon"
                and event.get("run_elapsed_seconds") == 0
            )
            if not initial_weapon_choice:
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
                {1, 2, 3}
                if event["choice_source"] == "statue"
                else {1, 2}
            )
            if (
                set(slots) != expected_slots
                or len(slots) != len(expected_slots)
            ):
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
                if int(shown["event_sequence"]) >= int(
                    event["event_sequence"]
                ):
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
                    or event["choice_sequence"]
                    != shown["choice_sequence"]
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
                if (
                    field in previous_values
                    and value < previous_values[field]
                ):
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

    return _sequence_result(issues)
