from datetime import datetime, timezone

import pytest

from pandok_ingestion.bronze import build_bronze_record


# 원본 이벤트를 변경하지 않고 Bronze 레코드로 감싸는지 확인한다.
def test_build_bronze_record_preserves_original_event() -> None:
    validated_event = {
        "source_type": "CONTROLLED_SCENARIO",
        "payload": {
            "current_gold": 100,
        },
    }

    record = build_bronze_record(
        validated_event,
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

    assert record == {
        "bronze_record_version": 1,
        "event": {
            "source_type": "CONTROLLED_SCENARIO",
            "payload": {
                "current_gold": 100,
            },
        },
        "metadata": {
            "received_at": "2026-09-01T12:30:00.000Z",
            "ingestion_channel": "scenario_generator",
        },
    }

    validated_event["payload"]["current_gold"] = 0
    assert record["event"]["payload"]["current_gold"] == 100


# 등록되지 않은 수집 경로를 거부하는지 확인한다.
def test_build_bronze_record_rejects_unknown_channel() -> None:
    with pytest.raises(ValueError, match="Unsupported ingestion_channel"):
        build_bronze_record(
            {"source_type": "CONTROLLED_SCENARIO"},
            "unknown_channel",
        )


# 수집 경로에서 허용하지 않는 source_type을 거부하는지 확인한다.
def test_build_bronze_record_rejects_mismatched_source_type() -> None:
    with pytest.raises(ValueError, match="source_type .* is not allowed"):
        build_bronze_record(
            {"source_type": "LOAD_TEST"},
            "scenario_generator",
        )


# source_type이 없는 이벤트를 거부하는지 확인한다.
def test_build_bronze_record_rejects_missing_source_type() -> None:
    with pytest.raises(ValueError, match="source_type None is not allowed"):
        build_bronze_record({}, "scenario_generator")


# 시간대 정보가 없는 수신 시각을 거부하는지 확인한다.
def test_build_bronze_record_rejects_naive_received_at() -> None:
    with pytest.raises(ValueError, match="received_at must be timezone-aware"):
        build_bronze_record(
            {"source_type": "CONTROLLED_SCENARIO"},
            "scenario_generator",
            received_at=datetime(2026, 9, 1, 12, 30),
        )
