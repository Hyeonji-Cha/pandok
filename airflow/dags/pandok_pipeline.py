# Bronze부터 Gold 검증까지 PANDOK 데이터 파이프라인의 실행 순서를 관리한다.
# 실패한 단계 뒤의 처리를 중단하고 실행 이력을 한 화면에서 확인하기 위해 필요하다.

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3
from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook
from airflow.sdk import dag, get_current_context, task

from pandok_gold import reconcile_metric_rows
from pandok_reports import generate_report_from_athena, put_ai_report
from pandok_silver import put_silver_and_quarantine, reconstruct_received_date_batch
from pandok_silver.s3_runner import read_bronze_records


AWS_REGION = "ap-southeast-2"
ATHENA_DATABASE = "pandok_dev"
SNOWFLAKE_CONNECTION_ID = "snowflake_default"
SQL_ROOT = Path("/opt/pandok/sql")
RECONCILIATION_COLUMNS = (
    "row_count",
    "metric_1_count",
    "metric_2_count",
    "metric_3_count",
    "metric_4_count",
    "metric_5_count",
)


def _required_environment(name: str) -> str:
    """필수 실행값이 빠진 상태로 유료 서비스 호출을 시작하지 않게 한다."""

    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"필수 환경 변수가 없습니다: {name}")
    return value


def _read_sql(relative_path: str) -> str:
    """Git에서 관리하는 SQL을 읽어 수동 실행과 DAG 실행의 로직을 같게 유지한다."""

    return (SQL_ROOT / relative_path).read_text(encoding="utf-8")


def _run_athena_query(sql: str) -> str:
    """비용 제한이 설정된 PANDOK WorkGroup에서 Athena 쿼리를 실행하고 완료를 기다린다."""

    client = boto3.client(
        "athena",
        region_name=os.getenv("AWS_REGION", AWS_REGION),
    )
    response = client.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": ATHENA_DATABASE},
        WorkGroup=_required_environment("PANDOK_ATHENA_WORKGROUP"),
    )
    query_id = response["QueryExecutionId"]

    for _ in range(300):
        execution = client.get_query_execution(QueryExecutionId=query_id)
        status = execution["QueryExecution"]["Status"]
        state = status["State"]
        if state == "SUCCEEDED":
            return query_id
        if state in {"FAILED", "CANCELLED"}:
            reason = status.get("StateChangeReason", "unknown error")
            raise RuntimeError(f"Athena query {state}: {reason}")
        time.sleep(1)

    client.stop_query_execution(QueryExecutionId=query_id)
    raise TimeoutError("Athena query did not finish within 300 seconds")


def _athena_rows(sql: str) -> list[dict[str, Any]]:
    """Athena 결과의 헤더와 값을 Gold 비교 함수가 읽을 수 있는 행으로 바꾼다."""

    query_id = _run_athena_query(sql)
    client = boto3.client(
        "athena",
        region_name=os.getenv("AWS_REGION", AWS_REGION),
    )
    paginator = client.get_paginator("get_query_results")
    pages = paginator.paginate(QueryExecutionId=query_id)
    columns: list[str] | None = None
    rows: list[dict[str, Any]] = []

    for page in pages:
        for raw_row in page["ResultSet"].get("Rows", []):
            values = [cell.get("VarCharValue") for cell in raw_row.get("Data", [])]
            if columns is None:
                columns = [str(value) for value in values]
                continue
            rows.append(dict(zip(columns, values, strict=False)))
    return rows


def _snowflake_rows(sql: str) -> list[dict[str, Any]]:
    """Snowflake 조회 결과를 컬럼명이 포함된 행 목록으로 바꾼다."""

    hook = SnowflakeHook(snowflake_conn_id=SNOWFLAKE_CONNECTION_ID)
    with hook.get_conn() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


@dag(
    dag_id="pandok_bronze_to_gold",
    description="PANDOK Bronze를 Silver와 Gold로 갱신하고 엔진 간 결과를 검증한다.",
    schedule=None,
    start_date=datetime(2026, 9, 1, tzinfo=UTC),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 0},
    params={"received_date": ""},
    tags=["pandok", "telemetry"],
)
def pandok_bronze_to_gold() -> None:
    """날짜 하나를 수동 실행해 전체 파이프라인의 성공·실패를 추적한다."""

    @task
    def rebuild_silver() -> dict[str, Any]:
        """전체 Bronze를 읽고 지정 날짜의 Run을 다시 복원해 Silver에 덮어쓴다."""

        context = get_current_context()
        requested_date = str(context["params"].get("received_date", "")).strip()
        received_date = requested_date or datetime.now(UTC).date().isoformat()
        bronze_bucket = _required_environment("PANDOK_BRONZE_BUCKET")
        silver_bucket = _required_environment("PANDOK_SILVER_BUCKET")

        bronze_records = list(read_bronze_records(bronze_bucket, "bronze/"))
        if not bronze_records:
            raise ValueError("Bronze 객체가 없어 Silver를 복원할 수 없습니다.")

        batch = reconstruct_received_date_batch(bronze_records, received_date)
        result = put_silver_and_quarantine(
            batch.runs,
            silver_bucket,
            received_date,
            boto3.client("s3", region_name=os.getenv("AWS_REGION", AWS_REGION)),
        )
        return {
            "received_date": received_date,
            "bronze_record_count": len(bronze_records),
            "silver_run_count": result.silver_run_count,
            "quarantine_run_count": result.quarantine_run_count,
        }

    @task
    def refresh_silver_iceberg(silver_result: dict[str, Any]) -> dict[str, Any]:
        """같은 날짜의 Iceberg 행을 지운 뒤 최신 Silver Parquet 결과를 다시 넣는다."""

        received_date = silver_result["received_date"]
        for sql_name in (
            "delete_silver_iceberg_date.sql",
            "insert_silver_iceberg_date.sql",
        ):
            sql = _read_sql(sql_name).replace("__RECEIVED_DATE__", received_date)
            _run_athena_query(sql)
        return silver_result

    @task
    def refresh_snowflake_silver(silver_result: dict[str, Any]) -> dict[str, Any]:
        """Glue에서 바뀐 Silver Iceberg snapshot을 Snowflake에 즉시 반영한다."""

        hook = SnowflakeHook(snowflake_conn_id=SNOWFLAKE_CONNECTION_ID)
        hook.run("ALTER ICEBERG TABLE PANDOK.SILVER.SILVER_EVENTS REFRESH")
        return silver_result

    @task
    def create_gold_views(silver_result: dict[str, Any]) -> dict[str, Any]:
        """갱신된 Silver를 사용해 분석용 Gold View와 품질 검사 View를 다시 정의한다."""

        hook = SnowflakeHook(snowflake_conn_id=SNOWFLAKE_CONNECTION_ID)
        hook.run(
            _read_sql("snowflake/create_gold_views.sql"),
            split_statements=True,
        )
        return silver_result

    @task
    def check_gold_quality(silver_result: dict[str, Any]) -> dict[str, Any]:
        """Gold 품질 규칙 하나라도 실패하면 외부 Iceberg 적재 전에 실행을 중단한다."""

        failed_checks = _snowflake_rows(
            "SELECT check_name, failed_row_count "
            "FROM PANDOK.GOLD.QUALITY_CHECKS "
            "WHERE check_status <> 'PASS'"
        )
        if failed_checks:
            raise ValueError(f"Gold quality check failed: {failed_checks}")
        return silver_result

    @task
    def load_gold_iceberg(silver_result: dict[str, Any]) -> dict[str, Any]:
        """검증된 Gold 결과를 S3·Glue 기반 Iceberg 테이블에 전체 갱신한다."""

        hook = SnowflakeHook(snowflake_conn_id=SNOWFLAKE_CONNECTION_ID)
        hook.run(
            _read_sql("snowflake/load_gold_iceberg.sql"),
            # 외부 관리 Iceberg는 여러 변경문을 하나의 트랜잭션으로 처리할 수 없다.
            autocommit=True,
            split_statements=True,
        )
        return silver_result

    @task
    def query_snowflake_gold(silver_result: dict[str, Any]) -> list[dict[str, Any]]:
        """Snowflake에서 품질·진행·업그레이드 Gold의 핵심 건수를 조회한다."""

        del silver_result
        sql = _read_sql("reconcile_gold_metrics.sql").replace(
            "__TABLE_PREFIX__",
            "PANDOK_LAKEHOUSE.pandok_dev.",
        )
        return _snowflake_rows(sql)

    @task
    def query_athena_gold(silver_result: dict[str, Any]) -> list[dict[str, Any]]:
        """Athena에서 같은 Gold Iceberg의 핵심 건수를 조회한다."""

        del silver_result
        sql = _read_sql("reconcile_gold_metrics.sql").replace(
            "__TABLE_PREFIX__",
            "pandok_dev.",
        )
        return _athena_rows(sql)

    @task
    def reconcile_gold(
        snowflake_rows: list[dict[str, Any]],
        athena_rows: list[dict[str, Any]],
    ) -> None:
        """Snowflake와 Athena의 동일 Gold 결과가 다르면 DAG를 실패 처리한다."""

        result = reconcile_metric_rows(
            snowflake_rows,
            athena_rows,
            key_columns=("dataset_key",),
            metric_columns=RECONCILIATION_COLUMNS,
        )
        if not result.matched:
            raise ValueError(f"Gold reconciliation failed: {result.differences}")

    @task
    def generate_ai_report(
        silver_result: dict[str, Any],
        _reconciliation_complete: None,
    ) -> dict[str, Any]:
        """Gold 대조 성공 후 영어 보고서를 한 번 생성해 기존 Silver 버킷에 저장한다."""

        report_date = silver_result["received_date"]
        report = generate_report_from_athena(
            report_date,
            workgroup=_required_environment("PANDOK_ATHENA_WORKGROUP"),
        )
        bucket_name = _required_environment("PANDOK_SILVER_BUCKET")
        object_key = put_ai_report(
            report,
            bucket_name,
            report_date,
            boto3.client("s3", region_name=os.getenv("AWS_REGION", AWS_REGION)),
        )
        # 보고서 본문은 Airflow XCom과 로그에 복사하지 않고 위치·비용 정보만 남긴다.
        return {
            "report_uri": f"s3://{bucket_name}/{object_key}",
            "model_id": report.model_id,
            "input_tokens": report.input_tokens,
            "output_tokens": report.output_tokens,
            "total_tokens": report.total_tokens,
        }

    silver = rebuild_silver()
    iceberg = refresh_silver_iceberg(silver)
    refreshed = refresh_snowflake_silver(iceberg)
    views = create_gold_views(refreshed)
    checked = check_gold_quality(views)
    gold = load_gold_iceberg(checked)
    reconciliation = reconcile_gold(
        query_snowflake_gold(gold),
        query_athena_gold(gold),
    )
    generate_ai_report(gold, reconciliation)


pandok_bronze_to_gold()
