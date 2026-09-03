# S3 Bronze 객체를 내려받아 Run 단위 Silver 데이터로 복원한다.
# 실제 AWS 저장 결과가 중복·순서 검증을 거쳐 분석 가능한 Run으로 변환되는지 확인하기 위해 사용한다.

from __future__ import annotations

import argparse
import gzip
import json
from collections.abc import Iterable
from typing import Any

import boto3

from pandok_silver import put_silver_parquet, reconstruct_runs


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
    silver_key = put_silver_parquet(
        reconstructed_runs,
        arguments.silver_bucket,
        arguments.received_date,
        s3_client,
    )

    print(f"BRONZE_RECORDS={len(bronze_records)}")
    print(f"SILVER_RUNS={len(reconstructed_runs)}")
    print(
        f"SILVER_OUTPUT=s3://{arguments.silver_bucket}/{silver_key}"
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
