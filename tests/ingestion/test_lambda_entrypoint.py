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
    monkeypatch.setenv("STREAMING_ENABLED", "true")
    monkeypatch.setenv("INGESTION_SHARED_SECRET", "test-secret-at-least-32-characters")
    monkeypatch.setattr(
        lambda_entrypoint,
        "_get_kinesis_client",
        lambda: kinesis_client,
    )

    response = lambda_entrypoint.lambda_handler(
        {
            "body": json.dumps(valid_event),
            "headers": {
                "x-pandok-ingestion-key": (
                    "test-secret-at-least-32-characters"
                ),
            },
            "isBase64Encoded": False,
        },
        None,
    )

    assert response["statusCode"] == 202
    assert json.loads(response["body"]) == {"accepted": True}
    assert kinesis_client.put_record.call_args.kwargs[
        "PartitionKey"
    ] == valid_event["run_id"]


# 공유 비밀값이 다르면 Lambda가 이벤트를 처리하거나 Kinesis를 호출하지 않는지 확인한다.
def test_lambda_handler_rejects_invalid_secret(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("INGESTION_SHARED_SECRET", "test-secret-at-least-32-characters")

    response = lambda_entrypoint.lambda_handler(
        {
            "body": "{}",
            "headers": {"x-pandok-ingestion-key": "wrong-secret"},
            "isBase64Encoded": False,
        },
        None,
    )

    assert response["statusCode"] == 401
    assert json.loads(response["body"]) == {
        "accepted": False,
        "reason": "unauthorized",
    }


def test_lambda_handler_reports_disabled_streaming(
    anonymous_sequence: list[dict[str, Any]],
    monkeypatch: Any,
) -> None:
    kinesis_client = Mock()
    monkeypatch.setenv(
        "INGESTION_SHARED_SECRET",
        "test-secret-at-least-32-characters",
    )
    monkeypatch.setenv("STREAMING_ENABLED", "false")
    monkeypatch.setattr(
        lambda_entrypoint,
        "_get_kinesis_client",
        lambda: kinesis_client,
    )

    response = lambda_entrypoint.lambda_handler(
        {
            "body": json.dumps(anonymous_sequence[0]),
            "headers": {
                "x-pandok-ingestion-key": (
                    "test-secret-at-least-32-characters"
                ),
            },
            "isBase64Encoded": False,
        },
        None,
    )

    assert response["statusCode"] == 503
    assert json.loads(response["body"]) == {
        "accepted": False,
        "reason": "streaming_disabled",
    }
    kinesis_client.put_record.assert_not_called()
