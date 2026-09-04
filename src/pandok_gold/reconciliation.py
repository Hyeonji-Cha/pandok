# Snowflake와 Athena가 계산한 Gold 지표가 같은지 비교한다.
# 엔진마다 다른 컬럼 대소문자와 숫자 타입 때문에 정상 결과를 오류로 판단하지 않기 위해 필요하다.

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


class GoldReconciliationInputError(ValueError):
    """비교할 행에 필수 컬럼이나 고유 키가 없음을 나타낸다."""


@dataclass(frozen=True)
class MetricDifference:
    """두 엔진 사이에서 발견된 지표 차이 한 건을 보존한다."""

    key: tuple[str, ...]
    column: str
    snowflake_value: Any
    athena_value: Any
    reason: str


@dataclass(frozen=True)
class ReconciliationResult:
    """전체 비교 결과와 발견된 차이를 함께 반환한다."""

    differences: tuple[MetricDifference, ...]

    @property
    def matched(self) -> bool:
        """차이가 하나도 없을 때만 두 엔진 결과가 같다고 판정한다."""

        return not self.differences


def _lowercase_columns(row: Mapping[str, Any]) -> dict[str, Any]:
    """Snowflake의 대문자 컬럼과 Athena의 소문자 컬럼을 같은 이름으로 맞춘다."""

    return {str(column).lower(): value for column, value in row.items()}


def _decimal(value: Any, column: str) -> Decimal:
    """정수·실수·문자열로 반환되는 엔진별 숫자를 Decimal로 통일한다."""

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise GoldReconciliationInputError(
            f"{column} 값은 숫자여야 합니다: {value!r}"
        ) from exc


def _index_rows(
    rows: Iterable[Mapping[str, Any]],
    key_columns: tuple[str, ...],
) -> dict[tuple[str, ...], dict[str, Any]]:
    """행 순서와 무관하게 비교하도록 각 행을 지표의 고유 키로 색인한다."""

    indexed: dict[tuple[str, ...], dict[str, Any]] = {}
    for original_row in rows:
        row = _lowercase_columns(original_row)
        missing = [column for column in key_columns if column not in row]
        if missing:
            raise GoldReconciliationInputError(
                f"비교 키 컬럼이 없습니다: {', '.join(missing)}"
            )

        key = tuple(str(row[column]) for column in key_columns)
        if key in indexed:
            raise GoldReconciliationInputError(
                f"중복된 비교 키입니다: {key!r}"
            )
        indexed[key] = row
    return indexed


def reconcile_metric_rows(
    snowflake_rows: Iterable[Mapping[str, Any]],
    athena_rows: Iterable[Mapping[str, Any]],
    *,
    key_columns: Sequence[str],
    metric_columns: Sequence[str],
    tolerance: Decimal = Decimal("0.01"),
) -> ReconciliationResult:
    """두 엔진의 Gold 행을 키로 연결하고 숫자 지표를 허용 오차 안에서 비교한다."""

    normalized_keys = tuple(column.lower() for column in key_columns)
    normalized_metrics = tuple(column.lower() for column in metric_columns)
    if not normalized_keys:
        raise GoldReconciliationInputError("비교 키 컬럼이 필요합니다.")
    if tolerance < 0:
        raise GoldReconciliationInputError("허용 오차는 0 이상이어야 합니다.")

    snowflake_index = _index_rows(snowflake_rows, normalized_keys)
    athena_index = _index_rows(athena_rows, normalized_keys)
    differences: list[MetricDifference] = []

    for key in sorted(snowflake_index.keys() | athena_index.keys()):
        snowflake_row = snowflake_index.get(key)
        athena_row = athena_index.get(key)
        if snowflake_row is None or athena_row is None:
            differences.append(
                MetricDifference(
                    key=key,
                    column="*",
                    snowflake_value=snowflake_row,
                    athena_value=athena_row,
                    reason=(
                        "missing_in_snowflake"
                        if snowflake_row is None
                        else "missing_in_athena"
                    ),
                )
            )
            continue

        for column in normalized_metrics:
            if column not in snowflake_row or column not in athena_row:
                raise GoldReconciliationInputError(
                    f"지표 컬럼이 없습니다: {column}"
                )

            snowflake_value = snowflake_row[column]
            athena_value = athena_row[column]
            if (
                snowflake_value is None
                or athena_value is None
                or abs(
                    _decimal(snowflake_value, column)
                    - _decimal(athena_value, column)
                )
                > tolerance
            ):
                if snowflake_value == athena_value:
                    continue
                differences.append(
                    MetricDifference(
                        key=key,
                        column=column,
                        snowflake_value=snowflake_value,
                        athena_value=athena_value,
                        reason="value_mismatch",
                    )
                )

    return ReconciliationResult(differences=tuple(differences))
