# Gold 집계만 Bedrock 입력으로 허용하고 식별자·과도한 입력을 차단하는지 검증한다.
# AI 호출 전에 개인정보와 토큰 비용 회귀를 발견하기 위해 필요한 핵심 테스트만 둔다.

import json
from decimal import Decimal
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from pandok_reports import GoldReportInputError, build_gold_report_input


def _valid_sections():
    return {
        "run_quality": [
            {
                "RUN_STATUS": "complete",
                "RUN_COUNT": Decimal("1"),
                "INPUT_EVENT_COUNT": Decimal("69"),
                "UNIQUE_EVENT_COUNT": Decimal("69"),
                "EXACT_RETRY_COUNT": Decimal("0"),
                "CONFLICTING_DUPLICATE_COUNT": Decimal("0"),
            }
        ],
        "run_outcomes": [
            {
                "END_REASON": "player_death",
                "ENDED_RUN_COUNT": Decimal("1"),
                "ENDED_RUN_PERCENTAGE": Decimal("100.00"),
                "AVERAGE_RUN_SECONDS": Decimal("655.18"),
            }
        ],
        "checkpoint_metrics": [],
        "upgrade_funnel": [],
    }


def test_builds_bounded_payload_from_aggregate_gold_rows():
    payload = build_gold_report_input("2026-09-04", **_valid_sections())

    assert payload["schema_version"] == "gold-report-input-v1"
    assert payload["metrics"]["run_outcomes"][0]["average_run_seconds"] == 655.18

    schema_path = (
        Path(__file__).parents[2]
        / "contracts"
        / "gold-report-input-v1.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)


def test_rejects_run_identifier_even_when_other_columns_are_valid():
    sections = _valid_sections()
    sections["run_quality"][0]["run_id"] = "prohibited"

    with pytest.raises(GoldReportInputError, match="unexpected=.*run_id"):
        build_gold_report_input("2026-09-04", **sections)


def test_rejects_section_that_exceeds_cost_row_limit():
    sections = _valid_sections()
    sections["run_outcomes"] *= 7

    with pytest.raises(GoldReportInputError, match="비용 제한 6개"):
        build_gold_report_input("2026-09-04", **sections)


def test_rejects_invalid_report_date():
    with pytest.raises(GoldReportInputError, match="YYYY-MM-DD"):
        build_gold_report_input("2026/09/04", **_valid_sections())
