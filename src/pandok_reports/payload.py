# 검증된 Gold 집계 결과만 Bedrock 입력 payload로 변환한다.
# 원본 이벤트나 Run 식별자가 AI 계층으로 넘어가는 것을 막고 입력 크기를 제한해 비용을 통제하기 위해 필요하다.

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
from typing import Any


MAX_REPORT_INPUT_BYTES = 24 * 1024
MAX_TEXT_LENGTH = 128

_SECTION_COLUMNS = {
    "run_quality": (
        "run_status",
        "run_count",
        "input_event_count",
        "unique_event_count",
        "exact_retry_count",
        "conflicting_duplicate_count",
    ),
    "run_outcomes": (
        "end_reason",
        "ended_run_count",
        "ended_run_percentage",
        "average_run_seconds",
    ),
    "checkpoint_metrics": (
        "checkpoint_number",
        "checkpoint_event_count",
        "average_player_level",
        "average_current_xp",
        "average_xp_to_next_level",
        "average_hp_percent",
        "average_total_kills",
        "average_current_gold",
    ),
    "upgrade_funnel": (
        "choice_source",
        "item_id",
        "rarity",
        "exposure_count",
        "selection_count",
        "selection_percentage",
    ),
}

_SECTION_ROW_LIMITS = {
    "run_quality": 4,
    "run_outcomes": 6,
    "checkpoint_metrics": 50,
    "upgrade_funnel": 100,
}


class GoldReportInputError(ValueError):
    """Gold 보고서 입력에 허용되지 않은 컬럼·값·크기가 있음을 나타낸다."""


def _json_value(value: Any, *, section: str, column: str) -> str | int | float:
    """Snowflake 숫자 타입을 JSON 값으로 바꾸고 비정상 값과 긴 문자열을 차단한다."""

    if isinstance(value, bool) or value is None:
        raise GoldReportInputError(f"{section}.{column} 값이 올바르지 않습니다.")
    if isinstance(value, Decimal):
        value = int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, str):
        if not value or len(value) > MAX_TEXT_LENGTH:
            raise GoldReportInputError(f"{section}.{column} 문자열 길이가 올바르지 않습니다.")
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise GoldReportInputError(f"{section}.{column} 타입이 올바르지 않습니다.")


def _normalize_section(
    section: str,
    source_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, str | int | float]]:
    """섹션별 허용 컬럼만 정확히 받도록 검사해 식별자나 원본 데이터 혼입을 막는다."""

    expected_columns = _SECTION_COLUMNS[section]
    normalized_rows: list[dict[str, str | int | float]] = []

    for source_row in source_rows:
        row = {str(column).lower(): value for column, value in source_row.items()}
        actual_columns = set(row)
        if actual_columns != set(expected_columns):
            unexpected = sorted(actual_columns - set(expected_columns))
            missing = sorted(set(expected_columns) - actual_columns)
            raise GoldReportInputError(
                f"{section} 컬럼이 계약과 다릅니다. "
                f"unexpected={unexpected}, missing={missing}"
            )
        normalized_rows.append(
            {
                column: _json_value(row[column], section=section, column=column)
                for column in expected_columns
            }
        )

    row_limit = _SECTION_ROW_LIMITS[section]
    if len(normalized_rows) > row_limit:
        raise GoldReportInputError(
            f"{section} 행 수가 비용 제한 {row_limit}개를 초과했습니다."
        )

    # 같은 입력은 같은 prompt가 되도록 행 순서를 고정한다.
    normalized_rows.sort(
        key=lambda row: json.dumps(row, sort_keys=True, ensure_ascii=False)
    )
    return normalized_rows


def build_gold_report_input(
    report_date: str,
    *,
    run_quality: Iterable[Mapping[str, Any]],
    run_outcomes: Iterable[Mapping[str, Any]],
    checkpoint_metrics: Iterable[Mapping[str, Any]],
    upgrade_funnel: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """허용된 네 종류의 Gold 집계만 크기 제한이 있는 Bedrock 입력으로 만든다."""

    try:
        parsed_date = date.fromisoformat(report_date)
    except ValueError as error:
        raise GoldReportInputError("report_date는 YYYY-MM-DD 형식이어야 합니다.") from error
    if parsed_date.isoformat() != report_date:
        raise GoldReportInputError("report_date는 YYYY-MM-DD 형식이어야 합니다.")

    payload = {
        "schema_version": "gold-report-input-v1",
        "report_date": report_date,
        "metrics": {
            "run_quality": _normalize_section("run_quality", run_quality),
            "run_outcomes": _normalize_section("run_outcomes", run_outcomes),
            "checkpoint_metrics": _normalize_section(
                "checkpoint_metrics",
                checkpoint_metrics,
            ),
            "upgrade_funnel": _normalize_section("upgrade_funnel", upgrade_funnel),
        },
    }

    encoded_payload = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(encoded_payload) > MAX_REPORT_INPUT_BYTES:
        raise GoldReportInputError(
            f"Bedrock 입력이 비용 제한 {MAX_REPORT_INPUT_BYTES} bytes를 초과했습니다."
        )
    return payload


def validate_gold_report_input(payload: Mapping[str, Any]) -> dict[str, Any]:
    """외부에서 받은 payload도 builder와 같은 허용 컬럼·크기 제한으로 다시 검증한다."""

    if set(payload) != {"schema_version", "report_date", "metrics"}:
        raise GoldReportInputError("Gold 보고서 입력의 최상위 필드가 계약과 다릅니다.")
    if payload.get("schema_version") != "gold-report-input-v1":
        raise GoldReportInputError("지원하지 않는 Gold 보고서 Schema입니다.")

    metrics = payload.get("metrics")
    if not isinstance(metrics, Mapping) or set(metrics) != set(_SECTION_COLUMNS):
        raise GoldReportInputError("Gold 보고서 metric 섹션이 계약과 다릅니다.")

    return build_gold_report_input(
        str(payload.get("report_date", "")),
        run_quality=metrics["run_quality"],
        run_outcomes=metrics["run_outcomes"],
        checkpoint_metrics=metrics["checkpoint_metrics"],
        upgrade_funnel=metrics["upgrade_funnel"],
    )
