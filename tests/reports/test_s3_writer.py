# 영어 AI 보고서가 날짜별 고정 key와 암호화 설정으로 S3에 저장되는지 검증한다.
# 재실행 파일 누적과 예상보다 큰 출력 저장을 실제 S3 비용 없이 방지하기 위해 필요하다.

import pytest

from pandok_reports import (
    MAX_REPORT_OUTPUT_BYTES,
    ReportGenerationResult,
    build_ai_report_key,
    put_ai_report,
)


class FakeS3Client:
    def __init__(self):
        self.requests = []

    def put_object(self, **kwargs):
        self.requests.append(kwargs)
        return {"ETag": '"fake"'}


def _report(markdown="# PANDOK Report"):
    return ReportGenerationResult(
        markdown=markdown,
        model_id="amazon.nova-micro-v1:0",
        input_tokens=2668,
        output_tokens=591,
        total_tokens=3259,
        stop_reason="end_turn",
    )


def test_puts_encrypted_report_at_idempotent_date_key():
    client = FakeS3Client()

    key = put_ai_report(
        _report(),
        "pandok-silver",
        "2026-09-04",
        client,
    )

    assert key == "ai-reports/report_date=2026-09-04/report.md"
    assert client.requests == [
        {
            "Bucket": "pandok-silver",
            "Key": key,
            "Body": b"# PANDOK Report",
            "ContentType": "text/markdown; charset=utf-8",
            "ServerSideEncryption": "AES256",
            "Metadata": {
                "model-id": "amazon.nova-micro-v1:0",
                "input-tokens": "2668",
                "output-tokens": "591",
                "total-tokens": "3259",
                "stop-reason": "end_turn",
            },
        }
    ]


def test_rejects_report_larger_than_storage_limit_before_s3_call():
    client = FakeS3Client()

    with pytest.raises(ValueError, match="exceeds"):
        put_ai_report(
            _report("x" * (MAX_REPORT_OUTPUT_BYTES + 1)),
            "pandok-silver",
            "2026-09-04",
            client,
        )

    assert client.requests == []


def test_rejects_invalid_report_date():
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        build_ai_report_key("2026/09/04")
