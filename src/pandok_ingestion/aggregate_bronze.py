# 검증된 집계 Export를 중복 없이 저장할 S3 Bronze 경로로 변환한다.
# 데이터 종류와 날짜를 경로에서 분리해 오염을 막고 Athena 조회 비용을 줄이기 위해 필요하다.

from typing import Any, Mapping


# 동일한 export 식별 정보는 항상 동일한 S3 경로를 반환한다.
def build_aggregate_bronze_key(
    validated_export: Mapping[str, Any],
) -> str:
    revision = validated_export["revision"]

    return (
        "bronze/king_charles/"
        f"data_class={validated_export['data_class']}/"
        f"schema_version={validated_export['schema_version']}/"
        f"source_region={validated_export['source_region']}/"
        f"bucket_date={validated_export['bucket_date']}/"
        f"revision={revision:06d}.json"
    )