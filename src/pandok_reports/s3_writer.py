# Bedrock이 생성한 영어 Markdown 보고서를 기존 Silver S3 버킷에 저장한다.
# 날짜별 결과를 덮어써 저장량 증가를 막고 암호화·크기 제한으로 비용과 노출 범위를 통제하기 위해 필요하다.

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any, Protocol

from .bedrock import ReportGenerationResult


MAX_REPORT_OUTPUT_BYTES = 32 * 1024


class S3Client(Protocol):
    """AI 보고서 저장에 필요한 S3 작업 한 개만 정의한다."""

    def put_object(self, **kwargs: Any) -> Mapping[str, Any]: ...


def build_ai_report_key(report_date: str) -> str:
    """같은 날짜 재실행이 새 파일을 누적하지 않도록 고정 S3 key를 만든다."""

    try:
        parsed_date = date.fromisoformat(report_date)
    except ValueError as error:
        raise ValueError("report_date must use YYYY-MM-DD") from error
    if parsed_date.isoformat() != report_date:
        raise ValueError("report_date must use YYYY-MM-DD")
    return f"ai-reports/report_date={report_date}/report.md"


def put_ai_report(
    report: ReportGenerationResult,
    bucket_name: str,
    report_date: str,
    s3_client: S3Client,
) -> str:
    """크기를 검증한 Markdown과 토큰 사용량을 암호화해 S3에 저장한다."""

    body = report.markdown.strip().encode("utf-8")
    if not body:
        raise ValueError("AI report must not be empty")
    if len(body) > MAX_REPORT_OUTPUT_BYTES:
        raise ValueError(
            f"AI report exceeds {MAX_REPORT_OUTPUT_BYTES} byte limit"
        )

    object_key = build_ai_report_key(report_date)
    s3_client.put_object(
        Bucket=bucket_name,
        Key=object_key,
        Body=body,
        ContentType="text/markdown; charset=utf-8",
        ServerSideEncryption="AES256",
        Metadata={
            "model-id": report.model_id,
            "input-tokens": str(report.input_tokens),
            "output-tokens": str(report.output_tokens),
            "total-tokens": str(report.total_tokens),
            "stop-reason": report.stop_reason,
        },
    )
    return object_key
