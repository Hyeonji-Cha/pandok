# 익명 텔레메트리 v2 Schema가 Run 분석 필드는 허용하고 영구 식별정보와 절대시각은 거부하는지 확인한다.
# v2가 프로젝트의 단일 공식 계약으로 개인정보 경계를 지키는지 검증한다.

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from pandok_contracts.validator import (
    _resolve_schema_path,
    _schema_path_candidates,
)

from conftest import REPO_ROOT, read_json


SCHEMA_PATH = REPO_ROOT / "contracts" / "telemetry-event-v2.schema.json"
FIXTURES_V2 = REPO_ROOT / "tests" / "contract" / "fixtures" / "v2"


@pytest.fixture(scope="module")
def v2_validator() -> Draft202012Validator:
    schema = read_json(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


@pytest.fixture(scope="module")
def anonymous_sequence() -> list[dict[str, object]]:
    return read_json(FIXTURES_V2 / "valid" / "anonymous_p0_run_sequence.json")


def _run_ended(
    anonymous_sequence: list[dict[str, object]],
) -> dict[str, object]:
    """기존 fixture를 변경하지 않고 종료 이벤트 복사본을 만든다."""

    return deepcopy(
        next(
            event
            for event in anonymous_sequence
            if event["event_name"] == "run_ended"
        )
    )


def test_v2_schema_itself_is_valid() -> None:
    Draft202012Validator.check_schema(read_json(SCHEMA_PATH))


def test_schema_path_resolves_local_source_layout() -> None:
    assert _resolve_schema_path() == SCHEMA_PATH.resolve()


def test_schema_path_checks_lambda_task_root() -> None:
    module_path = Path("C:/var/task/pandok_contracts/validator.py")

    candidates = _schema_path_candidates(module_path)

    assert candidates[0] == Path(
        "C:/var/task/contracts/telemetry-event-v2.schema.json"
    )


def test_all_five_anonymous_run_events_are_valid(
    v2_validator: Draft202012Validator,
    anonymous_sequence: list[dict[str, object]],
) -> None:
    assert {event["event_name"] for event in anonymous_sequence} == {
        "run_started",
        "upgrade_options_shown",
        "upgrade_selected",
        "run_checkpoint",
        "run_ended",
    }
    assert all(v2_validator.is_valid(event) for event in anonymous_sequence)


def test_event_sequence_represents_initial_weapon_order(
    anonymous_sequence: list[dict[str, object]],
) -> None:
    assert [event["event_sequence"] for event in anonymous_sequence] == [
        1,
        2,
        3,
        4,
        5,
    ]
    assert [event["event_name"] for event in anonymous_sequence[:3]] == [
        "upgrade_options_shown",
        "upgrade_selected",
        "run_started",
    ]
    assert all(
        event["run_elapsed_seconds"] == 0
        for event in anonymous_sequence[:3]
    )


@pytest.mark.parametrize(
    "death_cause",
    (
        "enemy_damage",
        "fall",
        "environmental_hazard",
        "unknown",
    ),
)
def test_player_death_accepts_approved_optional_death_cause(
    v2_validator: Draft202012Validator,
    anonymous_sequence: list[dict[str, object]],
    death_cause: str,
) -> None:
    event = _run_ended(anonymous_sequence)
    event["death_cause"] = death_cause

    assert v2_validator.is_valid(event)


def test_player_death_remains_valid_without_death_cause(
    v2_validator: Draft202012Validator,
    anonymous_sequence: list[dict[str, object]],
) -> None:
    event = _run_ended(anonymous_sequence)

    assert "death_cause" not in event
    assert v2_validator.is_valid(event)


@pytest.mark.parametrize(
    "end_reason",
    (
        "player_quit",
        "player_restart",
        "run_completed",
        "application_closed",
        "unknown",
    ),
)
def test_non_death_end_reason_rejects_death_cause(
    v2_validator: Draft202012Validator,
    anonymous_sequence: list[dict[str, object]],
    end_reason: str,
) -> None:
    event = _run_ended(anonymous_sequence)
    event["end_reason"] = end_reason
    event["death_cause"] = "unknown"

    assert not v2_validator.is_valid(event)


@pytest.mark.parametrize(
    "invalid_death_cause",
    (
        "critical_enemy_damage",
        "",
        None,
        {"type": "enemy_damage"},
        1,
    ),
)
def test_player_death_rejects_unapproved_death_cause(
    v2_validator: Draft202012Validator,
    anonymous_sequence: list[dict[str, object]],
    invalid_death_cause: object,
) -> None:
    event = _run_ended(anonymous_sequence)
    event["death_cause"] = invalid_death_cause

    assert not v2_validator.is_valid(event)


@pytest.mark.parametrize(
    "filename",
    (
        "event_with_persistent_identifiers.json",
        "event_with_client_time.json",
        "event_without_sequence.json",
    ),
)
def test_privacy_invalid_v2_fixtures_are_rejected(
    v2_validator: Draft202012Validator,
    filename: str,
) -> None:
    event = read_json(FIXTURES_V2 / "invalid" / filename)
    assert not v2_validator.is_valid(event)


def test_retry_identity_and_order_fields_can_remain_unchanged(
    v2_validator: Draft202012Validator,
    anonymous_sequence: list[dict[str, object]],
) -> None:
    original = anonymous_sequence[3]
    retry = deepcopy(original)

    assert retry == original
    assert retry["event_id"] == original["event_id"]
    assert retry["event_sequence"] == original["event_sequence"]
    assert v2_validator.is_valid(retry)


@pytest.mark.parametrize(
    "removed_field",
    ("anonymous_user_id", "session_id", "event_time"),
)
def test_removed_identity_and_time_fields_are_rejected(
    v2_validator: Draft202012Validator,
    anonymous_sequence: list[dict[str, object]],
    removed_field: str,
) -> None:
    event = deepcopy(anonymous_sequence[2])
    event[removed_field] = "prohibited"

    assert not v2_validator.is_valid(event)
