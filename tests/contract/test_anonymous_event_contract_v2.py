# 익명 텔레메트리 v2 Schema가 Run 분석 필드는 허용하고 영구 식별정보와 절대시각은 거부하는지 확인한다.
# v2가 프로젝트의 단일 공식 계약으로 개인정보 경계를 지키는지 검증한다.

from __future__ import annotations

from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator, FormatChecker

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


def test_v2_schema_itself_is_valid() -> None:
    Draft202012Validator.check_schema(read_json(SCHEMA_PATH))


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
