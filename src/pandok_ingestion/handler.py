# API Gateway에서 전달된 JSON 요청을 파싱해 Bronze 처리 단계로 넘긴다.
# JSON 문법 오류와 이벤트 Schema 오류를 구분해 정확한 거부 원인을 남기기 위해 사용한다.

import json
from datetime import datetime
from typing import Any

from pandok_contracts import ReasonCode, ValidationIssue

from .pipeline import prepare_bronze_record


class InvalidJsonError(ValueError):
    """Represent a request body that is not valid JSON."""

    def __init__(self, message: str) -> None:
        self.issues = (
            ValidationIssue(
                ReasonCode.INVALID_JSON,
                message,
            ),
        )
        super().__init__(message)


def ingest_json(
    body: str | bytes,
    ingestion_channel: str,
    *,
    received_at: datetime | None = None,
) -> dict[str, Any]:
    """Parse a JSON body and prepare its Bronze record."""
    try:
        event = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise InvalidJsonError(
            "Request body must be valid UTF-8 JSON"
        ) from error

    return prepare_bronze_record(
        event,
        ingestion_channel,
        received_at=received_at,
    )