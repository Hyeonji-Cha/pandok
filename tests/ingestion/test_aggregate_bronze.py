# 실제 계약 형식의 synthetic export가 예상한 Bronze 경로로 변환되는지 확인한다.
# 경로가 잘못되면 synthetic·production 데이터가 섞이거나 Athena 조회 범위가 커질 수 있어 필요하다.

import json
from pathlib import Path

from pandok_ingestion.aggregate_bronze import (
    build_aggregate_bronze_key,
)


SAMPLE_PATH = (
    Path(__file__).parents[2]
    / "kingcharles_turkiye_gateway"
    / "examples"
    / "aggregate-export-v1.synthetic.json"
)


def test_build_aggregate_bronze_key() -> None:
    validated_export = json.loads(
        SAMPLE_PATH.read_text(encoding="utf-8")
    )

    key = build_aggregate_bronze_key(validated_export)

    assert key == (
        "bronze/king_charles/"
        "data_class=SYNTHETIC_TEST/"
        "schema_version=aggregate-export-v1/"
        "source_region=TR/"
        "bucket_date=2099-01-01/"
        "revision=000001.json"
    )