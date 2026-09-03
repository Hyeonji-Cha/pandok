# Silver Parquet를 날짜 파티션의 고정 S3 key에 저장한다.
# 같은 날짜를 재처리해도 파일이 늘어나지 않고 최신 복원 결과로 교체되게 하기 위해 필요하다.

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any, Protocol

from .parquet import write_silver_parquet_bytes
from .run_reconstruction import ReconstructedRun


class S3Client(Protocol):
    """Silver writer가 사용하는 S3 작업 범위를 정의한다."""

    def put_object(
        self,
        *,
        Bucket: str,
        Key: str,
        Body: bytes,
        ContentType: str,
        ServerSideEncryption: str,
    ) -> Mapping[str, Any]: ...


def build_silver_object_key(received_date: str) -> str:
    """Bronze 입력 날짜와 대응되는 Silver Parquet key를 만든다."""

    try:
        parsed_date = date.fromisoformat(received_date)
    except ValueError as error:
        raise ValueError("received_date must use YYYY-MM-DD") from error
    if parsed_date.isoformat() != received_date:
        raise ValueError("received_date must use YYYY-MM-DD")

    # 고정 파일명은 같은 날짜 backfill이 중복 파일을 만들지 않게 한다.
    return f"silver/received_date={received_date}/events.parquet"


def put_silver_parquet(
    runs: Iterable[ReconstructedRun],
    bucket_name: str,
    received_date: str,
    s3_client: S3Client,
) -> str:
    """복원된 Run을 Parquet로 변환해 Silver S3에 저장한다."""

    object_key = build_silver_object_key(received_date)
    s3_client.put_object(
        Bucket=bucket_name,
        Key=object_key,
        Body=write_silver_parquet_bytes(runs),
        ContentType="application/vnd.apache.parquet",
        ServerSideEncryption="AES256",
    )
    return object_key
