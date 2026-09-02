# API Gateway HTTP API 요청을 기존 v2 검증·Kinesis 전송 흐름에 연결한다.
# Lambda가 요청 본문이나 개인정보를 로그·응답에 노출하지 않고 수집을 처리하기 위해 필요하다.

import base64
import json
import os
from binascii import Error as Base64DecodeError
from typing import Any

from .handler import InvalidJsonError, ingest_json_to_kinesis
from .kinesis_producer import KinesisClient
from .pipeline import EventContractError


_kinesis_client: KinesisClient | None = None


def lambda_handler(
    event: dict[str, Any],
    _context: Any,
) -> dict[str, Any]:
    """Handle one API Gateway HTTP API telemetry request."""
    try:
        request_body = _decode_request_body(event)

        ingest_json_to_kinesis(
            request_body,
            "turkiye_gateway",
            stream_name=os.environ["KINESIS_STREAM_NAME"],
            kinesis_client=_get_kinesis_client(),
        )
    except (
        Base64DecodeError,
        EventContractError,
        InvalidJsonError,
        TypeError,
        ValueError,
    ):
        # 입력값과 상세 오류를 응답에 넣지 않아 텔레메트리 내용 노출을 막는다.
        return _json_response(
            400,
            {"accepted": False, "reason": "invalid_telemetry"},
        )

    # 비동기 스트림에 접수됐다는 의미로 HTTP 202를 반환한다.
    return _json_response(202, {"accepted": True})


def _decode_request_body(event: dict[str, Any]) -> str | bytes:
    """Extract an optional Base64-encoded API Gateway request body."""
    body = event.get("body")
    if not isinstance(body, (str, bytes)):
        raise ValueError("API Gateway request body is required")

    if event.get("isBase64Encoded") is True:
        return base64.b64decode(body, validate=True)

    return body


def _get_kinesis_client() -> KinesisClient:
    """Reuse one Kinesis client across warm Lambda invocations."""
    global _kinesis_client

    if _kinesis_client is None:
        # Lambda Python 런타임에 포함된 boto3를 실제 실행 시점에만 불러온다.
        import boto3

        _kinesis_client = boto3.client("kinesis")

    return _kinesis_client


def _json_response(
    status_code: int,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Build an API Gateway-compatible JSON response."""
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body, separators=(",", ":")),
        "isBase64Encoded": False,
    }
