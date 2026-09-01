from typing import Any, Mapping
from copy import deepcopy
from datetime import datetime, timezone

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

ALLOWED_SOURCE_TYPES_BY_CHANNEL = {
    "unity_client": frozenset(
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
