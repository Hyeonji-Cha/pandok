# Athena의 검증된 Gold 집계를 읽어 Bedrock 영어 보고서 생성까지 한 번 실행한다.
# 수동 명령 하나로 최종 단계를 검증하되 조회 행·대기 시간·재시도를 제한해 비용 폭증을 막기 위해 필요하다.

from __future__ import annotations

import argparse
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

import boto3
from botocore.config import Config

from .bedrock import (
    AWS_REGION,
    BedrockRuntimeClient,
    ReportGenerationResult,
    generate_gold_report,
)
from .payload import build_gold_report_input


ATHENA_DATABASE = "pandok_dev"
ATHENA_WORKGROUP = "pandok-dev"
ATHENA_QUERY_TIMEOUT_SECONDS = 300

_SECTION_QUERIES = {
    "run_quality": """
        SELECT run_status, run_count, input_event_count, unique_event_count,
               exact_retry_count, conflicting_duplicate_count
        FROM gold_run_quality
        LIMIT 5
    """,
    "run_outcomes": """
        SELECT end_reason, ended_run_count, ended_run_percentage,
               average_run_seconds
        FROM gold_run_outcome
        LIMIT 7
    """,
    "checkpoint_metrics": """
        SELECT checkpoint_number, checkpoint_event_count,
               average_player_level, average_current_xp,
               average_xp_to_next_level, average_hp_percent,
               average_total_kills, average_current_gold
        FROM gold_checkpoint_metrics
        LIMIT 51
    """,
    "upgrade_funnel": """
        SELECT choice_source, item_id, rarity, exposure_count,
               selection_count, selection_percentage
        FROM gold_upgrade_funnel
        LIMIT 101
    """,
    "run_progression": """
        SELECT game_version, checkpoint_number, started_run_count,
               reached_run_count, reach_percentage, step_dropoff_percentage
        FROM gold_run_progression
        ORDER BY step_dropoff_percentage DESC, game_version, checkpoint_number
        LIMIT 20
    """,
    "upgrade_post_selection": """
        SELECT game_version, choice_source, item_id, rarity, selection_minute,
               selection_count, selected_run_count, outcome_observed_run_count,
               average_seconds_after_selection,
               death_within_60_seconds_count,
               death_within_60_seconds_percentage, analysis_status
        FROM gold_upgrade_post_selection
        WHERE outcome_observed_run_count > 0
        ORDER BY
          CASE analysis_status WHEN 'DESCRIPTIVE_ONLY' THEN 0 ELSE 1 END,
          selected_run_count DESC,
          game_version,
          item_id
        LIMIT 20
    """,
}


class AthenaResultsPaginator(Protocol):
    def paginate(self, **kwargs: Any) -> Any: ...


class AthenaClient(Protocol):
    """보고서 runner가 사용하는 Athena 작업 범위를 정의한다."""

    def start_query_execution(self, **kwargs: Any) -> Mapping[str, Any]: ...

    def get_query_execution(self, **kwargs: Any) -> Mapping[str, Any]: ...

    def stop_query_execution(self, **kwargs: Any) -> Mapping[str, Any]: ...

    def get_paginator(self, operation_name: str) -> AthenaResultsPaginator: ...


def create_athena_client() -> AthenaClient:
    """Sydney 고정·자동 재시도 없음으로 Athena client를 만든다."""

    return boto3.client(
        "athena",
        region_name=AWS_REGION,
        config=Config(
            connect_timeout=5,
            read_timeout=60,
            retries={"mode": "standard", "total_max_attempts": 1},
        ),
    )


def _run_athena_query(
    client: AthenaClient,
    sql: str,
    *,
    database: str,
    workgroup: str,
) -> str:
    """비용 제한 WorkGroup에서 쿼리를 시작하고 최대 5분만 완료를 기다린다."""

    response = client.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": database},
        WorkGroup=workgroup,
    )
    query_id = str(response["QueryExecutionId"])

    for _ in range(ATHENA_QUERY_TIMEOUT_SECONDS):
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


def _convert_athena_value(value: str | None, column_type: str) -> Any:
    """Athena 문자열 결과를 Gold 계약이 요구하는 숫자와 문자열 타입으로 복원한다."""

    if value is None:
        return None
    normalized_type = column_type.lower()
    if normalized_type in {"tinyint", "smallint", "integer", "bigint"}:
        return int(value)
    if normalized_type.startswith("decimal"):
        return Decimal(value)
    if normalized_type in {"real", "float", "double"}:
        return float(value)
    return value


def _read_athena_rows(
    client: AthenaClient,
    query_id: str,
) -> list[dict[str, Any]]:
    """페이지로 나뉜 Athena 결과를 컬럼명이 포함된 Python 행으로 변환한다."""

    pages = client.get_paginator("get_query_results").paginate(
        QueryExecutionId=query_id
    )
    rows: list[dict[str, Any]] = []
    header_skipped = False

    for page in pages:
        metadata = page["ResultSet"]["ResultSetMetadata"]["ColumnInfo"]
        columns = [(column["Name"], column["Type"]) for column in metadata]
        for raw_row in page["ResultSet"].get("Rows", []):
            if not header_skipped:
                header_skipped = True
                continue
            cells = raw_row.get("Data", [])
            values = [
                cells[index].get("VarCharValue") if index < len(cells) else None
                for index in range(len(columns))
            ]
            rows.append(
                {
                    name: _convert_athena_value(value, column_type)
                    for (name, column_type), value in zip(columns, values, strict=True)
                }
            )
    return rows


def generate_report_from_athena(
    report_date: str,
    *,
    database: str = ATHENA_DATABASE,
    workgroup: str = ATHENA_WORKGROUP,
    athena_client: AthenaClient | None = None,
    bedrock_client: BedrockRuntimeClient | None = None,
) -> ReportGenerationResult:
    """Gold 여섯 섹션을 제한 조회하고 Nova Micro 영어 보고서를 한 번 생성한다."""

    client = athena_client or create_athena_client()
    sections: dict[str, list[dict[str, Any]]] = {}
    for section, sql in _SECTION_QUERIES.items():
        query_id = _run_athena_query(
            client,
            sql,
            database=database,
            workgroup=workgroup,
        )
        sections[section] = _read_athena_rows(client, query_id)

    report_input = build_gold_report_input(
        report_date,
        run_quality=sections["run_quality"],
        run_outcomes=sections["run_outcomes"],
        checkpoint_metrics=sections["checkpoint_metrics"],
        upgrade_funnel=sections["upgrade_funnel"],
        run_progression=sections["run_progression"],
        upgrade_post_selection=sections["upgrade_post_selection"],
    )
    return generate_gold_report(report_input, bedrock_client=bedrock_client)


def main() -> None:
    """명령행에서 오늘 또는 지정 날짜의 Gold 영어 보고서를 출력한다."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report-date",
        default=datetime.now(UTC).date().isoformat(),
    )
    parser.add_argument("--database", default=ATHENA_DATABASE)
    parser.add_argument("--workgroup", default=ATHENA_WORKGROUP)
    arguments = parser.parse_args()

    result = generate_report_from_athena(
        arguments.report_date,
        database=arguments.database,
        workgroup=arguments.workgroup,
    )
    print(result.markdown)
    print()
    print(f"MODEL_ID={result.model_id}")
    print(f"INPUT_TOKENS={result.input_tokens}")
    print(f"OUTPUT_TOKENS={result.output_tokens}")
    print(f"TOTAL_TOKENS={result.total_tokens}")
    print(f"STOP_REASON={result.stop_reason}")


if __name__ == "__main__":
    main()
