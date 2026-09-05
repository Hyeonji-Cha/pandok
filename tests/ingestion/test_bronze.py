# Bronze 포장과 수집 채널 정책이 AWS 저장 전에 지켜지는지 테스트한다.
# Türkiye Gateway 우회와 잘못된 source_type을 차단하기 위해 필요하다.

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


# 허용된 사망 원인이 Bronze 원본 이벤트에서 손실되지 않는지 확인한다.
def test_build_bronze_record_preserves_death_cause() -> None:
    record = build_bronze_record(
        {
            "source_type": "CONTROLLED_SCENARIO",
            "event_name": "run_ended",
            "end_reason": "player_death",
            "death_cause": "fall",
        },
        "scenario_generator",
    )

    assert record["event"]["death_cause"] == "fall"


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


# 운영 데이터는 Türkiye Gateway만 AWS Bronze에 전달할 수 있는지 확인한다.
def test_production_ingestion_requires_turkiye_gateway() -> None:
    record = build_bronze_record(
        {"source_type": "CONSENTED_PROD_PLAY"},
        "turkiye_gateway",
    )

    assert record["metadata"]["ingestion_channel"] == (
        "turkiye_gateway"
    )

    with pytest.raises(
        ValueError,
        match="Unsupported ingestion_channel",
    ):
        build_bronze_record(
            {"source_type": "CONSENTED_PROD_PLAY"},
            "unity_client",
        )
