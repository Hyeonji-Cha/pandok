# 복원된 Silver Run을 분석 도구가 읽기 좋은 Parquet 행과 파일로 변환한다.
# 공통 필드는 컬럼으로 조회하고 이벤트별 가변 필드는 JSON으로 보존해 정보 손실을 막기 위해 필요하다.

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from .run_reconstruction import ReconstructedRun


COMMON_EVENT_FIELDS = frozenset(
    {
        "event_id",
        "event_name",
        "source_type",
        "run_id",
        "event_sequence",
        "run_elapsed_seconds",
        "game_version",
        "schema_version",
    }
)


SILVER_EVENT_SCHEMA = pa.schema(
    [
        pa.field("run_id", pa.string(), nullable=False),
        pa.field("event_id", pa.string(), nullable=False),
        pa.field("event_name", pa.string(), nullable=False),
        pa.field("event_sequence", pa.int64(), nullable=False),
        pa.field("run_elapsed_seconds", pa.float64(), nullable=False),
        pa.field("source_type", pa.string(), nullable=False),
        pa.field("game_version", pa.string(), nullable=False),
        pa.field("schema_version", pa.string(), nullable=False),
        pa.field("run_status", pa.string(), nullable=False),
        pa.field("first_received_at", pa.timestamp("ms", tz="UTC"), nullable=False),
        pa.field("ingestion_channel", pa.string(), nullable=False),
        pa.field("event_payload_json", pa.string(), nullable=False),
        pa.field("quality_issues_json", pa.string(), nullable=False),
        pa.field("input_event_count", pa.int64(), nullable=False),
        pa.field("unique_event_count", pa.int64(), nullable=False),
        pa.field("exact_retry_count", pa.int64(), nullable=False),
        pa.field("conflicting_duplicate_count", pa.int64(), nullable=False),
    ]
)


def _json_text(value: Any) -> str:
    """중첩 데이터도 실행할 때마다 동일한 JSON 문자열로 만든다."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def runs_to_silver_rows(
    runs: Iterable[ReconstructedRun],
) -> list[dict[str, Any]]:
    """Run 결과를 이벤트 한 건당 Silver 행 하나로 평탄화한다."""

    rows: list[dict[str, Any]] = []
    for run in runs:
        issues_json = _json_text(
            [issue.as_dict() for issue in run.issues]
        )
        for reconstructed_event in run.events:
            event = reconstructed_event.event
            event_payload = {
                key: value
                for key, value in event.items()
                if key not in COMMON_EVENT_FIELDS
            }
            rows.append(
                {
                    "run_id": run.run_id,
                    "event_id": str(event["event_id"]),
                    "event_name": str(event["event_name"]),
                    "event_sequence": int(event["event_sequence"]),
                    "run_elapsed_seconds": float(
                        event["run_elapsed_seconds"]
                    ),
                    "source_type": run.source_type,
                    "game_version": str(event["game_version"]),
                    "schema_version": str(event["schema_version"]),
                    "run_status": run.status.value,
                    "first_received_at": (
                        reconstructed_event.first_received_at
                    ),
                    "ingestion_channel": (
                        reconstructed_event.ingestion_channel
                    ),
                    "event_payload_json": _json_text(event_payload),
                    "quality_issues_json": issues_json,
                    "input_event_count": run.input_event_count,
                    "unique_event_count": run.unique_event_count,
                    "exact_retry_count": run.exact_retry_count,
                    "conflicting_duplicate_count": (
                        run.conflicting_duplicate_count
                    ),
                }
            )
    return rows


def write_silver_parquet(
    runs: Iterable[ReconstructedRun],
    destination: str | Path,
) -> Path:
    """Silver 이벤트를 Snappy 압축 Parquet 파일로 저장한다."""

    output_path = Path(destination)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(
        runs_to_silver_rows(runs),
        schema=SILVER_EVENT_SCHEMA,
    )
    pq.write_table(table, output_path, compression="snappy")
    return output_path


def write_silver_parquet_bytes(
    runs: Iterable[ReconstructedRun],
) -> bytes:
    """로컬 임시 파일 없이 S3에 전송할 Parquet bytes를 만든다."""

    table = pa.Table.from_pylist(
        runs_to_silver_rows(runs),
        schema=SILVER_EVENT_SCHEMA,
    )
    output = pa.BufferOutputStream()
    pq.write_table(table, output, compression="snappy")
    return output.getvalue().to_pybytes()
