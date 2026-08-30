"""Single-event and Run-sequence validation for telemetry contract v1."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .errors import ReasonCode, ValidationIssue


SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "contracts" / "telemetry-event-v1.schema.json"
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

_CORRELATION_FIELDS = (
    "anonymous_user_id",
    "session_id",
    "run_id",
    "game_version",
    "schema_version",
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


@lru_cache(maxsize=1)
def _schema() -> dict[str, Any]:
    with SCHEMA_PATH.open(encoding="utf-8") as handle:
        schema = json.load(handle)
    Draft202012Validator.check_schema(schema)
    return schema


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


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.casefold())


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


def _canonical(event: Mapping[str, Any]) -> str:
    return json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _event_time(event: Mapping[str, Any]) -> datetime:
    return datetime.fromisoformat(str(event["event_time"]).replace("Z", "+00:00"))


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
