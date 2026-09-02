# API Gateway에서 전달된 JSON 요청을 파싱해 Bronze 처리 단계로 넘긴다.
# JSON 문법 오류와 이벤트 Schema 오류를 구분해 정확한 거부 원인을 남기기 위해 사용한다.

import json
from datetime import datetime
from typing import Any, Mapping

from pandok_contracts import ReasonCode, ValidationIssue

from .kinesis_producer import KinesisClient, put_bronze_record
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
    body: str | bytes, #Türkiye Gateway에서 받은 JSON
    ingestion_channel: str, # 데이터 유입 경로. 운영 데이터는 turkiye_gateway
    *,
    received_at: datetime | None = None, # AWS에서 이벤트를 받은 시각
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

# 위의 처리를 실행한 뒤 Kinesis로 전송
def ingest_json_to_kinesis(
    body: str | bytes,
    ingestion_channel: str,
    *,
    stream_name: str, # 전송할 Kinesis Data Streams 이름
    kinesis_client: KinesisClient, # AWS Kinesis를 호출하는 객체
    received_at: datetime | None = None,
) -> Mapping[str, Any]:
    """Validate one JSON event and send its Bronze record to Kinesis."""

    # JSON 파싱·v2 계약 검증·Bronze 포장이 모두 끝난 레코드만 전송한다.
    bronze_record = ingest_json(
        body,
        ingestion_channel,
        received_at=received_at,
    )

    # 같은 Run의 이벤트가 같은 Kinesis shard로 전달되도록 Producer에 맡긴다.
    return put_bronze_record(
        bronze_record,
        stream_name,
        kinesis_client,
    )
