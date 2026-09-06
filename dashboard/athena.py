# Athena 쿼리를 제한된 Workgroup에서 실행하고 표 형태로 변환한다.
# 자동 재시도나 자동 새로고침 없이 사용자가 요청한 조회만 수행한다.

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

import boto3


AWS_REGION = "ap-southeast-2"
ATHENA_DATABASE = "pandok_dev"
ATHENA_WORKGROUP = "pandok-dev"
QUERY_TIMEOUT_SECONDS = 60


class AthenaQueryError(RuntimeError):
    pass


def _cell_value(cell: Mapping[str, str]) -> str | None:
    return cell.get("VarCharValue")


def _rows_from_result(result: Mapping[str, Any]) -> list[dict[str, str | None]]:
    result_set = result.get("ResultSet", {})
    columns = [
        column["Name"]
        for column in result_set.get("ResultSetMetadata", {}).get("ColumnInfo", [])
    ]
    rows = result_set.get("Rows", [])
    if not columns or len(rows) <= 1:
        return []
    return [
        {
            column: _cell_value(cell)
            for column, cell in zip(columns, row.get("Data", []), strict=False)
        }
        for row in rows[1:]
    ]


def run_query(
    sql: str,
    *,
    athena_client: Any | None = None,
    timeout_seconds: int = QUERY_TIMEOUT_SECONDS,
) -> list[dict[str, str | None]]:
    client = athena_client or boto3.client("athena", region_name=AWS_REGION)
    response = client.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": ATHENA_DATABASE},
        WorkGroup=ATHENA_WORKGROUP,
    )
    query_id = response["QueryExecutionId"]
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        execution = client.get_query_execution(QueryExecutionId=query_id)
        status = execution["QueryExecution"]["Status"]
        state = status["State"]
        if state == "SUCCEEDED":
            return _rows_from_result(
                client.get_query_results(QueryExecutionId=query_id)
            )
        if state in {"FAILED", "CANCELLED"}:
            raise AthenaQueryError(status.get("StateChangeReason", state))
        time.sleep(0.5)

    client.stop_query_execution(QueryExecutionId=query_id)
    raise AthenaQueryError(f"Athena 쿼리가 {timeout_seconds}초 안에 끝나지 않았습니다.")


def run_queries(
    queries: Mapping[str, str],
    *,
    athena_client: Any | None = None,
) -> dict[str, list[dict[str, str | None]]]:
    client = athena_client or boto3.client("athena", region_name=AWS_REGION)
    return {
        name: run_query(sql, athena_client=client)
        for name, sql in queries.items()
    }
