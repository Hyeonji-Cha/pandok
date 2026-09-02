# v2 이벤트에 계정·기기·네트워크 식별정보가 포함되지 않는지 테스트한다.
# 중첩된 개인정보도 AWS Bronze에 도달하기 전에 차단하기 위해 필요하다.

from __future__ import annotations

from copy import deepcopy

import pytest

from pandok_contracts.errors import ReasonCode
from pandok_contracts.validator import validate_anonymous_event

from conftest import REPO_ROOT, read_json


SEQUENCE_PATH = (
    REPO_ROOT
    / "tests"
    / "contract"
    / "fixtures"
    / "v2"
    / "valid"
    / "anonymous_p0_run_sequence.json"
)


def _run_started():
    events = read_json(SEQUENCE_PATH)
    return deepcopy(
        next(
            event
            for event in events
            if event["event_name"] == "run_started"
        )
    )


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
def test_anonymous_v2_rejects_identifier_key_variations(field):
    event = _run_started()
    event[field] = "prohibited"

    issues = validate_anonymous_event(event)

    assert issues[0].code == ReasonCode.PROHIBITED_FIELD
    assert issues[0].path == (field,)


def test_anonymous_v2_rejects_nested_identifier_in_array():
    event = _run_started()
    event["unexpected"] = {
        "items": [
            {"deviceId": "device-123"},
        ]
    }

    issues = validate_anonymous_event(event)

    assert issues[0].code == ReasonCode.PROHIBITED_FIELD
    assert issues[0].path == (
        "unexpected",
        "items",
        0,
        "deviceId",
    )


def test_anonymous_v2_allows_gameplay_state_and_run_scoped_identifiers():
    events = read_json(SEQUENCE_PATH)
    checkpoint = next(
        event
        for event in events
        if event["event_name"] == "run_checkpoint"
    )

    assert "player_level" in checkpoint
    assert "run_id" in checkpoint
    assert "event_sequence" in checkpoint
    assert validate_anonymous_event(checkpoint) == []


def test_anonymous_v2_rejects_unknown_non_identifier_as_schema_error():
    event = _run_started()
    event["unreviewed_metric"] = 1

    issues = validate_anonymous_event(event)

    assert issues[0].code == ReasonCode.SCHEMA_INVALID
