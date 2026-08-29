from __future__ import annotations

from copy import deepcopy

from pandok_contracts.errors import ReasonCode
from pandok_contracts.validator import validate_event

import pytest


def test_top_level_steam_id_is_rejected(valid_sequence):
    event = deepcopy(valid_sequence[1])
    event["steam_id"] = "76561198000000000"
    issues = validate_event(event)
    assert issues[0].code == ReasonCode.PROHIBITED_FIELD
    assert issues[0].path == ("steam_id",)


def test_nested_email_is_rejected(valid_sequence):
    event = deepcopy(valid_sequence[2])
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
    event = deepcopy(valid_sequence[2])
    event["options"][0][field] = "prohibited"
    issues = validate_event(event)
    assert issues[0].code == ReasonCode.PROHIBITED_FIELD
    assert issues[0].path == ("options", 0, field)
