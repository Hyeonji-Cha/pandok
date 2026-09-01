# 제어 시나리오가 JSON 수집 경계를 거쳐 Bronze 레코드가 되는 전체 흐름을 테스트한다.
# AWS 연결 전에 producer와 ingestion 사이의 형식·출처 규칙이 맞는지 확인한다.

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from pandok_contracts import validate_sequence
from pandok_ingestion.handler import ingest_json
from pandok_producer import generate_controlled_sequence


# 생성된 원본 이벤트 전체가 JSON 파싱과 계약 검증을 거쳐 Bronze에 도달하는지 확인한다.
def test_controlled_scenario_flows_to_bronze(
    valid_sequence: list[dict[str, Any]],
) -> None:
    generated_events = generate_controlled_sequence(
        valid_sequence,
        started_at=datetime(2026, 9, 2, 15, 0, tzinfo=UTC),
    )
    first_received_at = datetime(2026, 9, 2, 16, 0, tzinfo=UTC)

    bronze_records = [
        ingest_json(
            json.dumps(event),
            "scenario_generator",
            received_at=first_received_at + timedelta(seconds=index),
        )
        for index, event in enumerate(generated_events)
    ]

    stored_events = [record["event"] for record in bronze_records]

    assert stored_events == generated_events
    assert validate_sequence(stored_events) == []
    assert all(
        record["bronze_record_version"] == 1
        for record in bronze_records
    )
    assert all(
        record["metadata"]["ingestion_channel"] == "scenario_generator"
        for record in bronze_records
    )
