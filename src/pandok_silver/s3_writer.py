# 복원이 끝난 Run을 Parquet로 변환하여 S3 Silver 영역에 기록하는 출력 모듈이다.
# 이 파일은 Bronze를 읽거나 이벤트를 Run 단위로 복원하지 않는다.
# parquet 모듈에 파일 생성을 맡기고, 날짜별 S3 key 결정과 업로드만 담당한다.
# 같은 날짜를 재처리할 때 파일이 계속 늘어나 중복 집계되지 않도록 고정 key를
# 사용하여 그 날짜의 전체 복원 결과를 최신 파일로 교체하기 위해 필요하다.

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from pandok_contracts import SequenceStatus

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


@dataclass(frozen=True, slots=True)
class PartitionWriteResult:
    """날짜별 Silver·Quarantine 저장 결과와 Run 개수를 나타낸다."""

    silver_key: str
    quarantine_key: str
    silver_run_count: int
    quarantine_run_count: int


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


def build_quarantine_object_key(received_date: str) -> str:
    """잘못된 Run을 Silver와 분리하는 Quarantine key를 만든다."""

    build_silver_object_key(received_date)
    return f"quarantine/received_date={received_date}/events.parquet"


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


def put_silver_and_quarantine(
    runs: Iterable[ReconstructedRun],
    bucket_name: str,
    received_date: str,
    s3_client: S3Client,
) -> PartitionWriteResult:
    """신뢰 가능한 Run과 INVALID Run을 서로 다른 S3 경로에 저장한다."""

    all_runs = list(runs)
    silver_runs = [
        run for run in all_runs if run.status != SequenceStatus.INVALID
    ]
    quarantine_runs = [
        run for run in all_runs if run.status == SequenceStatus.INVALID
    ]

    silver_key = put_silver_parquet(
        silver_runs,
        bucket_name,
        received_date,
        s3_client,
    )
    quarantine_key = build_quarantine_object_key(received_date)
    s3_client.put_object(
        Bucket=bucket_name,
        Key=quarantine_key,
        Body=write_silver_parquet_bytes(quarantine_runs),
        ContentType="application/vnd.apache.parquet",
        ServerSideEncryption="AES256",
    )

    return PartitionWriteResult(
        silver_key=silver_key,
        quarantine_key=quarantine_key,
        silver_run_count=len(silver_runs),
        quarantine_run_count=len(quarantine_runs),
    )
