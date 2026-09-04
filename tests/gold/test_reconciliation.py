# Snowflake와 Athena 결과의 표현 차이는 허용하고 실제 Gold 값 차이는 탐지하는지 검증한다.
# 잘못된 Gold 지표가 후속 리포트에 전달되는 회귀를 막기 위해 필요하다.

from decimal import Decimal

import pytest

from pandok_gold import (
    GoldReconciliationInputError,
    reconcile_metric_rows,
)


METRIC_COLUMNS = (
    "run_count",
    "input_event_count",
    "unique_event_count",
    "exact_retry_count",
    "conflicting_duplicate_count",
)


def test_matches_rows_with_engine_specific_representations():
    result = reconcile_metric_rows(
        [
            {
                "RUN_STATUS": "incomplete",
                "RUN_COUNT": Decimal("1"),
                "INPUT_EVENT_COUNT": Decimal("1"),
                "UNIQUE_EVENT_COUNT": Decimal("1"),
                "EXACT_RETRY_COUNT": Decimal("0"),
                "CONFLICTING_DUPLICATE_COUNT": Decimal("0"),
            }
        ],
        [
            {
                "run_status": "incomplete",
                "run_count": "1",
                "input_event_count": "1",
                "unique_event_count": "1",
                "exact_retry_count": "0",
                "conflicting_duplicate_count": "0",
            }
        ],
        key_columns=("run_status",),
        metric_columns=METRIC_COLUMNS,
    )

    assert result.matched
    assert result.differences == ()


def test_reports_a_metric_value_mismatch():
    result = reconcile_metric_rows(
        [{"run_status": "valid", "run_count": 2}],
        [{"run_status": "valid", "run_count": "1"}],
        key_columns=("run_status",),
        metric_columns=("run_count",),
    )

    assert not result.matched
    assert result.differences[0].column == "run_count"
    assert result.differences[0].reason == "value_mismatch"


def test_rejects_duplicate_metric_keys():
    with pytest.raises(
        GoldReconciliationInputError,
        match="중복된 비교 키",
    ):
        reconcile_metric_rows(
            [
                {"run_status": "valid", "run_count": 1},
                {"run_status": "valid", "run_count": 1},
            ],
            [],
            key_columns=("run_status",),
            metric_columns=("run_count",),
        )
