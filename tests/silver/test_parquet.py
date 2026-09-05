# Silver Run이 손실 없는 고정 스키마의 Parquet 파일로 저장되는지 검증한다.
# 중첩 필드와 품질 metadata가 컬럼 변환 과정에서 사라지는 회귀를 막기 위해 필요하다.

from __future__ import annotations

import json
from datetime import datetime, timezone

import pyarrow.parquet as pq

from pandok_ingestion.bronze import build_bronze_record
from pandok_silver import reconstruct_runs, write_silver_parquet


def test_writes_reconstructed_events_to_parquet(
    anonymous_sequence,
    tmp_path,
):
    received_at = datetime(2026, 9, 3, tzinfo=timezone.utc)
    bronze_records = [
        build_bronze_record(
            event,
            "turkiye_gateway",
            received_at=received_at,
        )
        for event in anonymous_sequence
    ]
    runs = reconstruct_runs(bronze_records)
    output_path = tmp_path / "silver.parquet"

    write_silver_parquet(runs, output_path)

    table = pq.read_table(output_path)
    rows = table.to_pylist()
    assert table.num_rows == len(anonymous_sequence)
    assert rows[0]["run_status"] == "valid"
    assert rows[0]["first_received_at"] == received_at
    assert rows[0]["ingestion_channel"] == "turkiye_gateway"
    assert rows[0]["exact_retry_count"] == 0
    assert json.loads(rows[0]["event_payload_json"]) == {
        key: value
        for key, value in anonymous_sequence[0].items()
        if key
        not in {
            "event_id",
            "event_name",
            "source_type",
            "run_id",
            "event_sequence",
            "run_elapsed_seconds",
            "game_version",
            "schema_version",
        }
    }


def test_preserves_optional_death_cause_in_event_payload(
    anonymous_sequence,
    tmp_path,
):
    events = [dict(event) for event in anonymous_sequence]
    ended_event = next(
        event for event in events if event["event_name"] == "run_ended"
    )
    ended_event["death_cause"] = "enemy_damage"
    bronze_records = [
        build_bronze_record(
            event,
            "turkiye_gateway",
            received_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
        )
        for event in events
    ]
    output_path = tmp_path / "silver-death-cause.parquet"

    write_silver_parquet(reconstruct_runs(bronze_records), output_path)

    rows = pq.read_table(output_path).to_pylist()
    silver_end = next(row for row in rows if row["event_name"] == "run_ended")
    assert json.loads(silver_end["event_payload_json"])["death_cause"] == (
        "enemy_damage"
    )
