# S3 Bronze를 읽어 Silver 처리의 전체 순서를 실행하는 진입점이다.
# 이 파일이 Run 복원이나 Parquet 생성을 직접 구현하는 것은 아니다.
# run_reconstruction에 이벤트 복원을, s3_writer에 Parquet 저장을 맡기고
# "Bronze 읽기 -> Run 복원 -> Silver S3 저장" 단계를 연결한다.
# 날짜별 원본 전체를 같은 규칙으로 재처리할 수 있게 하여 네트워크 도착 순서와
# retry 중복이 분석 결과에 영향을 주지 않는 Silver 데이터를 만들기 위해 필요하다.

from __future__ import annotations

import argparse
import gzip
import json
from collections.abc import Iterable
from typing import Any

import boto3

from pandok_silver import put_silver_and_quarantine, reconstruct_runs


def read_bronze_records(
    bucket_name: str,
    prefix: str,
) -> Iterable[dict[str, Any]]:
    """S3의 Firehose GZIP 객체에서 Bronze JSON 레코드를 읽는다."""

    s3_client = boto3.client("s3")
    paginator = s3_client.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
        for object_info in page.get("Contents", []):
            response = s3_client.get_object(
                Bucket=bucket_name,
                Key=object_info["Key"],
            )
            decompressed = gzip.decompress(response["Body"].read())

            for line in decompressed.decode("utf-8").splitlines():
                if line.strip():
                    yield json.loads(line)


def main() -> None:
    """날짜별 S3 Bronze를 복원해 Silver Parquet로 저장한다."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--bronze-bucket", required=True)
    parser.add_argument("--silver-bucket", required=True)
    parser.add_argument("--received-date", required=True)
    arguments = parser.parse_args()

    bronze_prefix = (
        f"bronze/received_date={arguments.received_date}/"
    )
    bronze_records = list(
        read_bronze_records(arguments.bronze_bucket, bronze_prefix)
    )
    if not bronze_records:
        raise SystemExit(
            f"No Bronze records found under {bronze_prefix}"
        )

    reconstructed_runs = reconstruct_runs(bronze_records)
    s3_client = boto3.client("s3")
    write_result = put_silver_and_quarantine(
        reconstructed_runs,
        arguments.silver_bucket,
        arguments.received_date,
        s3_client,
    )

    print(f"BRONZE_RECORDS={len(bronze_records)}")
    print(f"SILVER_RUNS={len(reconstructed_runs)}")
    print(f"SILVER_ACCEPTED_RUNS={write_result.silver_run_count}")
    print(
        "QUARANTINED_RUNS="
        f"{write_result.quarantine_run_count}"
    )
    print(
        "SILVER_OUTPUT="
        f"s3://{arguments.silver_bucket}/{write_result.silver_key}"
    )
    print(
        "QUARANTINE_OUTPUT="
        f"s3://{arguments.silver_bucket}/{write_result.quarantine_key}"
    )

    for run in reconstructed_runs:
        print(
            f"run_id={run.run_id} "
            f"status={run.status.value} "
            f"events={run.unique_event_count} "
            f"retries={run.exact_retry_count} "
            f"conflicts={run.conflicting_duplicate_count}"
        )


if __name__ == "__main__":
    main()
