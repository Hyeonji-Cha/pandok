# API Gateway 요청이 Lambda를 거쳐 기존 Kinesis 전송 흐름에 연결되는지 테스트한다.
# 배포 전에 HTTP 요청 형식과 Lambda 환경변수 연결 오류를 한 번에 잡기 위해 필요하다.

import json
from typing import Any
from unittest.mock import Mock

import pandok_ingestion.lambda_entrypoint as lambda_entrypoint


def test_lambda_handler_accepts_valid_event(
    anonymous_sequence: list[dict[str, Any]],
    monkeypatch: Any,
) -> None:
    valid_event = anonymous_sequence[0]
    kinesis_client = Mock()
    kinesis_client.put_record.return_value = {
        "ShardId": "shardId-000000000000",
        "SequenceNumber": "12345",
    }
    monkeypatch.setenv("KINESIS_STREAM_NAME", "pandok-dev-telemetry")
    monkeypatch.setattr(
        lambda_entrypoint,
        "_get_kinesis_client",
        lambda: kinesis_client,
    )

    response = lambda_entrypoint.lambda_handler(
        {
            "body": json.dumps(valid_event),
            "isBase64Encoded": False,
        },
        None,
    )

    assert response["statusCode"] == 202
    assert json.loads(response["body"]) == {"accepted": True}
    assert kinesis_client.put_record.call_args.kwargs[
        "PartitionKey"
    ] == valid_event["run_id"]
