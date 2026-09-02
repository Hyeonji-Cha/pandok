# 검증된 v2 이벤트를 AWS Bronze 저장 형식으로 감싼다.
# Türkiye Gateway를 거친 출처만 운영 데이터로 허용하기 위해 수집 채널도 함께 검사한다.

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping


def build_bronze_record(
    validated_event: Mapping[str, Any],
    ingestion_channel: str,
    *,
    received_at: datetime | None = None,
) -> dict[str, Any]:
    """Wrap a validated telemetry event in a Bronze storage record."""
    validate_source_channel_pair(validated_event, ingestion_channel)

    if received_at is None:
        received_at = datetime.now(timezone.utc)

    if received_at.tzinfo is None or received_at.utcoffset() is None:
        raise ValueError("received_at must be timezone-aware")

    received_at_utc = received_at.astimezone(timezone.utc)
    received_at_text = received_at_utc.isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")

    return {
        "bronze_record_version": 1,
        "event": deepcopy(dict(validated_event)),
        "metadata": {
            "received_at": received_at_text,
            "ingestion_channel": ingestion_channel,
        },
    }


# Bronze 레코드를 Athena가 효율적으로 조회할 수 있는 S3 파티션 경로로 변환한다.
# 날짜와 source_type으로 조회 범위를 줄여 불필요한 S3 스캔 비용을 막기 위해 필요하다.
def build_bronze_partition_prefix(
    bronze_record: Mapping[str, Any],
) -> str:
    event = bronze_record["event"]
    metadata = bronze_record["metadata"]
    # 클라이언트 시간이 아니라 AWS에서 기록한 수신 날짜를 파티션 기준으로 사용한다.
    received_at = datetime.fromisoformat(
        str(metadata["received_at"]).replace("Z", "+00:00")
    )
    received_date = received_at.date().isoformat()
    # run_id와 event_id는 값이 너무 많아 파티션 수를 증가시키므로 경로에서 제외한다.
    return (
        "bronze/"
        f"schema_version={event['schema_version']}/"
        f"source_type={event['source_type']}/"
        f"received_date={received_date}/"
    )

ALLOWED_SOURCE_TYPES_BY_CHANNEL = {
    "turkiye_gateway": frozenset(
        {
            "CONSENTED_PROD_PLAY",
            "CONTROLLED_SCENARIO",
        }
    ),
    "scenario_generator": frozenset({"CONTROLLED_SCENARIO"}),
    "load_test_runner": frozenset({"LOAD_TEST"}),
}

ALLOWED_INGESTION_CHANNELS = frozenset(
    ALLOWED_SOURCE_TYPES_BY_CHANNEL
)


def validate_ingestion_channel(ingestion_channel: str) -> None:
    """Reject ingestion channels that are not explicitly allowed."""
    if ingestion_channel not in ALLOWED_INGESTION_CHANNELS:
        raise ValueError(
            f"Unsupported ingestion_channel: {ingestion_channel}"
        )


def validate_source_channel_pair(
    event: Mapping[str, Any],
    ingestion_channel: str,
) -> None:
    """Reject source types that are not allowed for the ingestion channel."""
    validate_ingestion_channel(ingestion_channel)

    source_type = event.get("source_type")
    allowed_source_types = ALLOWED_SOURCE_TYPES_BY_CHANNEL[
        ingestion_channel
    ]

    if source_type not in allowed_source_types:
        raise ValueError(
            f"source_type {source_type!r} is not allowed for "
            f"ingestion_channel {ingestion_channel!r}"
        )
