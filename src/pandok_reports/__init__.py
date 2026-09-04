"""검증된 Gold 집계만 AI 보고서 입력으로 변환한다."""

from .payload import (
    GoldReportInputError,
    MAX_REPORT_INPUT_BYTES,
    build_gold_report_input,
    validate_gold_report_input,
)
from .bedrock import (
    BEDROCK_MODEL_ID,
    MAX_OUTPUT_TOKENS,
    ReportGenerationError,
    ReportGenerationResult,
    create_bedrock_runtime_client,
    generate_gold_report,
)
from .runner import generate_report_from_athena
from .s3_writer import (
    MAX_REPORT_OUTPUT_BYTES,
    build_ai_report_key,
    put_ai_report,
)

__all__ = [
    "BEDROCK_MODEL_ID",
    "GoldReportInputError",
    "MAX_REPORT_INPUT_BYTES",
    "MAX_OUTPUT_TOKENS",
    "MAX_REPORT_OUTPUT_BYTES",
    "ReportGenerationError",
    "ReportGenerationResult",
    "build_gold_report_input",
    "build_ai_report_key",
    "create_bedrock_runtime_client",
    "generate_gold_report",
    "generate_report_from_athena",
    "put_ai_report",
    "validate_gold_report_input",
]
