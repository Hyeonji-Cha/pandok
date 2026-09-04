"""검증된 Gold 집계만 AI 보고서 입력으로 변환한다."""

from .payload import (
    GoldReportInputError,
    MAX_REPORT_INPUT_BYTES,
    build_gold_report_input,
)

__all__ = [
    "GoldReportInputError",
    "MAX_REPORT_INPUT_BYTES",
    "build_gold_report_input",
]
