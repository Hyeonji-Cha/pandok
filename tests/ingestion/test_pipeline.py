from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from unittest.mock import Mock

import pytest

import pandok_ingestion.pipeline as pipeline
from pandok_contracts import ReasonCode


# 계약 위반 시 Bronze 생성 함수가 호출되지 않았는지 확인하기 위한 감시 객체다.
@pytest.fixture
def bronze_builder_spy(monkeypatch: pytest.MonkeyPatch) -> Mock:
    builder = Mock()
    monkeypatch.setattr(pipeline, "build_bronze_record", builder)
    return builder


# 계약을 통과한 실제 fixture가 Bronze 레코드로 생성되는지 확인한다.
def test_prepare_bronze_record_accepts_valid_event(
    anonymous_sequence: list[dict[str, Any]],
) -> None:
    valid_event = next(
        event
        for event in anonymous_sequence
        if event["event_name"] == "run_started"
    )

    record = pipeline.prepare_bronze_record(
        valid_event,
        "scenario_generator",
        received_at=datetime(
            2026,
            9,
            1,
            12,
            30,
            tzinfo=timezone.utc,
        ),
    )

    assert record["event"] == valid_event
    assert record["metadata"] == {
        "received_at": "2026-09-01T12:30:00.000Z",
        "ingestion_channel": "scenario_generator",
    }


# 필수 필드가 누락된 이벤트를 Schema 오류로 거부하는지 확인한다.
def test_prepare_bronze_record_rejects_missing_required_field(
    anonymous_sequence: list[dict[str, Any]],
    bronze_builder_spy: Mock,
) -> None:
    invalid_event = deepcopy(anonymous_sequence[0])
    del invalid_event["event_id"]

    with pytest.raises(pipeline.EventContractError) as captured:
        pipeline.prepare_bronze_record(invalid_event, "scenario_generator")

    assert ReasonCode.SCHEMA_INVALID in {
        issue.code for issue in captured.value.issues
    }
    bronze_builder_spy.assert_not_called()


# 금지된 개인정보 필드가 포함된 이벤트를 거부하는지 확인한다.
def test_prepare_bronze_record_rejects_prohibited_field(
    anonymous_sequence: list[dict[str, Any]],
    bronze_builder_spy: Mock,
) -> None:
    invalid_event = deepcopy(anonymous_sequence[0])
    invalid_event["ip_address"] = "192.0.2.1"

    with pytest.raises(pipeline.EventContractError) as captured:
        pipeline.prepare_bronze_record(invalid_event, "scenario_generator")

    assert ReasonCode.PROHIBITED_FIELD in {
        issue.code for issue in captured.value.issues
    }
    bronze_builder_spy.assert_not_called()


# JSON 객체가 아닌 입력을 Schema 오류로 거부하는지 확인한다.
def test_prepare_bronze_record_rejects_non_object(
    bronze_builder_spy: Mock,
) -> None:
    with pytest.raises(pipeline.EventContractError) as captured:
        pipeline.prepare_bronze_record([], "scenario_generator")

    assert ReasonCode.SCHEMA_INVALID in {
        issue.code for issue in captured.value.issues
    }
    bronze_builder_spy.assert_not_called()
