# Silver writer가 날짜 파티션과 보안 설정을 지켜 S3에 Parquet를 저장하는지 검증한다.
# backfill 재실행이 중복 key를 만들거나 잘못된 형식으로 업로드되는 회귀를 막기 위해 필요하다.

from __future__ import annotations

from datetime import datetime, timezone

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from pandok_ingestion.bronze import build_bronze_record
from pandok_silver import (
    put_silver_and_quarantine,
    put_silver_parquet,
    reconstruct_runs,
)


class RecordingS3Client:
    """AWS 호출 없이 put_object 인자를 기록한다."""

    def __init__(self) -> None:
        self.request = None
        self.requests = []

    def put_object(self, **kwargs):
        self.request = kwargs
        self.requests.append(kwargs)
        return {"ETag": '"test"'}


def test_puts_silver_parquet_at_deterministic_date_key(
    anonymous_sequence,
):
    received_at = datetime(2026, 9, 3, tzinfo=timezone.utc)
    records = [
        build_bronze_record(
            event,
            "turkiye_gateway",
            received_at=received_at,
        )
        for event in anonymous_sequence
    ]
    client = RecordingS3Client()

    key = put_silver_parquet(
        reconstruct_runs(records),
        "pandok-test-silver",
        "2026-09-03",
        client,
    )

    assert key == "silver/received_date=2026-09-03/events.parquet"
    assert client.request["Bucket"] == "pandok-test-silver"
    assert client.request["Key"] == key
    assert client.request["ContentType"] == "application/vnd.apache.parquet"
    assert client.request["ServerSideEncryption"] == "AES256"
    table = pq.read_table(pa.BufferReader(client.request["Body"]))
    assert table.num_rows == len(anonymous_sequence)


def test_rejects_invalid_silver_partition_date(anonymous_sequence):
    client = RecordingS3Client()

    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        put_silver_parquet(
            [],
            "pandok-test-silver",
            "2026-9-3",
            client,
        )

    assert client.request is None


def test_separates_invalid_runs_into_quarantine(anonymous_sequence):
    received_at = datetime(2026, 9, 3, tzinfo=timezone.utc)
    conflict = dict(anonymous_sequence[-1])
    conflict["game_version"] = "conflicting-version"
    records = [
        build_bronze_record(
            event,
            "turkiye_gateway",
            received_at=received_at,
        )
        for event in [*anonymous_sequence, conflict]
    ]
    client = RecordingS3Client()

    result = put_silver_and_quarantine(
        reconstruct_runs(records),
        "pandok-test-silver",
        "2026-09-03",
        client,
    )

    assert result.silver_run_count == 0
    assert result.quarantine_run_count == 1
    assert [request["Key"] for request in client.requests] == [
        "silver/received_date=2026-09-03/events.parquet",
        "quarantine/received_date=2026-09-03/events.parquet",
    ]
    assert pq.read_table(
        pa.BufferReader(client.requests[0]["Body"])
    ).num_rows == 0
    quarantine_rows = pq.read_table(
        pa.BufferReader(client.requests[1]["Body"])
    ).to_pylist()
    assert len(quarantine_rows) == len(anonymous_sequence)
    assert all(
        row["run_status"] == "invalid" for row in quarantine_rows
    )
