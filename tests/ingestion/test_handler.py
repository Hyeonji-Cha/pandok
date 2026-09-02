# API Gateway·Lambda 연결 전에 JSON 요청 처리 기준이 지켜지는지 테스트한다.
# JSON 문법 오류와 이벤트 Schema 오류를 서로 구분하기 위해 사용한다.

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock

import pytest

from pandok_contracts import ReasonCode
from pandok_ingestion.handler import (
    InvalidJsonError,
    ingest_json,
    ingest_json_to_kinesis,
)


# 정상 JSON이 계약 검증을 거쳐 Bronze 레코드로 변환되는지 확인한다.
def test_ingest_json_accepts_valid_json(
    anonymous_sequence: list[dict[str, Any]],
) -> None:
    valid_event = anonymous_sequence[0]

    record = ingest_json(
        json.dumps(valid_event),
        "turkiye_gateway",
        received_at=datetime(2026, 9, 1, 12, 30, tzinfo=UTC),
    )

    assert record["event"] == valid_event
    assert record["metadata"]["received_at"] == (
        "2026-09-01T12:30:00.000Z"
    )


# 정상 v2 JSON이 Bronze 포장을 거쳐 Kinesis 전송까지 연결되는지 확인한다.
def test_ingest_json_to_kinesis_sends_valid_event(
    anonymous_sequence: list[dict[str, Any]],
) -> None:
    valid_event = anonymous_sequence[0]
    kinesis_client = Mock()
    kinesis_client.put_record.return_value = {
        "ShardId": "shardId-000000000000",
        "SequenceNumber": "12345",
    }

    response = ingest_json_to_kinesis(
        json.dumps(valid_event),
        "turkiye_gateway",
        stream_name="pandok-dev-telemetry",
        kinesis_client=kinesis_client,
        received_at=datetime(2026, 9, 1, 12, 30, tzinfo=UTC),
    )

    call_arguments = kinesis_client.put_record.call_args.kwargs

    assert call_arguments["StreamName"] == "pandok-dev-telemetry"
    assert call_arguments["PartitionKey"] == valid_event["run_id"]
    assert response["SequenceNumber"] == "12345"


# JSON 문법이 깨진 요청을 Schema 검증 전에 INVALID_JSON으로 거부하는지 확인한다.
def test_ingest_json_rejects_invalid_json() -> None:
    with pytest.raises(InvalidJsonError) as captured:
        ingest_json(
            '{"event_name": "run_started"',
            "turkiye_gateway",
        )

    assert captured.value.issues[0].code == ReasonCode.INVALID_JSON
