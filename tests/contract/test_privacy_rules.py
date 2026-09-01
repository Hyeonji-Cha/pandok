from __future__ import annotations

from copy import deepcopy

from pandok_contracts.errors import ReasonCode
from pandok_contracts.validator import validate_anonymous_event, validate_event

import pytest

from conftest import REPO_ROOT, read_json


ANONYMOUS_SEQUENCE_PATH = (
    REPO_ROOT
    / "tests"
    / "contract"
    / "fixtures"
    / "v2"
    / "valid"
    / "anonymous_p0_run_sequence.json"
)


# 정상 v2 이벤트를 복사해 개인정보 필드 변형만 독립적으로 검사한다.
def _anonymous_run_started():
    events = read_json(ANONYMOUS_SEQUENCE_PATH)
    return deepcopy(
        next(event for event in events if event["event_name"] == "run_started")
    )


def test_top_level_steam_id_is_rejected(valid_sequence):
    event = deepcopy(valid_sequence[1])
    event["steam_id"] = "76561198000000000"
    issues = validate_event(event)
    assert issues[0].code == ReasonCode.PROHIBITED_FIELD
    assert issues[0].path == ("steam_id",)


def test_nested_email_is_rejected(valid_sequence):
    event = deepcopy(
        next(
            item
            for item in valid_sequence
            if item["event_name"] == "upgrade_options_shown"
        )
    )
    event["options"][0]["email"] = "player@example.com"
    issues = validate_event(event)
    assert issues[0].code == ReasonCode.PROHIBITED_FIELD
    assert issues[0].path == ("options", 0, "email")


@pytest.mark.parametrize(
    "field",
    (
        "steam_id",
        "steam_nickname",
        "email",
        "device_identifier",
        "authentication_token",
        "chat_content",
        "precise_location",
        "username",
    ),
)
def test_every_documented_direct_identifier_is_rejected(valid_sequence, field):
    event = deepcopy(
        next(
            item
            for item in valid_sequence
            if item["event_name"] == "upgrade_options_shown"
        )
    )
    event["options"][0][field] = "prohibited"
    issues = validate_event(event)
    assert issues[0].code == ReasonCode.PROHIBITED_FIELD
    assert issues[0].path == ("options", 0, field)


@pytest.mark.parametrize(
    "field",
    (
        "steamAccountId",
        "PLAYER-ID",
        "user_identifier",
        "account.id",
        "deviceId",
        "machine_id",
        "installation-id",
        "hardwareUUID",
        "MAC_address",
        "clientIp",
        "emailAddress",
        "full_name",
        "phoneNumber",
        "discord_id",
        "latitude",
        "longitude",
        "auth",
        "Authorization",
        "sessionToken",
        "Cookie",
        "persistent_identifier",
        "fingerprint",
        "X-Forwarded-For",
        "FORWARDED",
        "xRealIp",
        "CF-Connecting-IP",
        "True_Client_IP",
    ),
)
# v2 금지 키가 표기 방식과 대소문자에 관계없이 같은 개인정보 필드로 처리되는지 확인한다.
def test_anonymous_v2_rejects_identifier_key_variations(field):
    event = _anonymous_run_started()
    event[field] = "prohibited"

    issues = validate_anonymous_event(event)

    assert issues[0].code == ReasonCode.PROHIBITED_FIELD
    assert issues[0].path == (field,)


# 중첩 객체와 배열 안에 숨긴 금지 필드도 AWS 경계 전에 찾아내는지 확인한다.
def test_anonymous_v2_rejects_nested_identifier_in_array():
    event = _anonymous_run_started()
    event["unexpected"] = {
        "items": [
            {"deviceId": "device-123"},
        ]
    }

    issues = validate_anonymous_event(event)

    assert issues[0].code == ReasonCode.PROHIBITED_FIELD
    assert issues[0].path == ("unexpected", "items", 0, "deviceId")


# 과거 계약의 필수 session_id가 v1 검증에서 새 규칙 때문에 차단되지 않는지 확인한다.
def test_v1_session_id_remains_valid(valid_sequence):
    assert validate_event(valid_sequence[1]) == []


# 이름에 player가 포함돼도 gameplay 상태인 player_level은 과잉 차단하지 않는지 확인한다.
def test_anonymous_v2_allows_gameplay_state_and_run_scoped_identifiers():
    events = read_json(ANONYMOUS_SEQUENCE_PATH)
    checkpoint = next(
        event for event in events if event["event_name"] == "run_checkpoint"
    )

    assert "player_level" in checkpoint
    assert "run_id" in checkpoint
    assert "event_sequence" in checkpoint
    assert validate_anonymous_event(checkpoint) == []


# 개인정보가 아닌 미승인 필드는 개인정보 오류와 구분해 Schema 오류로 거부하는지 확인한다.
def test_anonymous_v2_rejects_unknown_non_identifier_as_schema_error():
    event = _anonymous_run_started()
    event["unreviewed_metric"] = 1

    issues = validate_anonymous_event(event)

    assert issues[0].code == ReasonCode.SCHEMA_INVALID
