# API Gateway HTTP API 요청을 기존 v2 검증·Kinesis 전송 흐름에 연결한다.
# Lambda가 요청 본문이나 개인정보를 로그·응답에 노출하지 않고 수집을 처리하기 위해 필요하다.

import base64
import hmac
import json
import os
from binascii import Error as Base64DecodeError
from typing import Any

from .handler import InvalidJsonError, ingest_json_to_kinesis
from .kinesis_producer import KinesisClient
from .pipeline import EventContractError


_kinesis_client: KinesisClient | None = None
_INGESTION_SECRET_HEADER = "x-pandok-ingestion-key"
_MAX_REQUEST_BODY_BYTES = 64 * 1024


def lambda_handler(
    event: dict[str, Any],
    _context: Any,
) -> dict[str, Any]:
    """Handle one API Gateway HTTP API telemetry request."""
    if not _is_authorized(event):
        return _json_response(
            401,
            {"accepted": False, "reason": "unauthorized"},
        )

    # endpoint는 유지하되 스트림이 없을 때 성공 응답으로 데이터 유실을 숨기지 않는다.
    if not _streaming_is_enabled():
        return _json_response(
            503,
            {"accepted": False, "reason": "streaming_disabled"},
        )

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
        decoded_body = base64.b64decode(body, validate=True)
    else:
        decoded_body = body

    body_size = len(
        decoded_body.encode("utf-8")
        if isinstance(decoded_body, str)
        else decoded_body
    )
    if body_size > _MAX_REQUEST_BODY_BYTES:
        raise ValueError("API Gateway request body is too large")

    return decoded_body


def _is_authorized(event: dict[str, Any]) -> bool:
    """Compare the Türkiye Gateway secret without logging it."""
    headers = event.get("headers")
    if not isinstance(headers, dict):
        return False

    provided_secret = next(
        (
            value
            for name, value in headers.items()
            if str(name).lower() == _INGESTION_SECRET_HEADER
            and isinstance(value, str)
        ),
        None,
    )
    if provided_secret is None:
        return False

    expected_secret = os.environ["INGESTION_SHARED_SECRET"]
    return hmac.compare_digest(provided_secret, expected_secret)


def _get_kinesis_client() -> KinesisClient:
    """Reuse one Kinesis client across warm Lambda invocations."""
    global _kinesis_client

    if _kinesis_client is None:
        # Lambda Python 런타임에 포함된 boto3를 실제 실행 시점에만 불러온다.
        import boto3

        _kinesis_client = boto3.client("kinesis")

    return _kinesis_client


def _streaming_is_enabled() -> bool:
    """Terraform이 전달한 스트리밍 활성화 상태를 엄격하게 확인한다."""

    return os.environ.get("STREAMING_ENABLED", "false").lower() == "true"


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
