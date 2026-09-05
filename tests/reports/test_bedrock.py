# Bedrock 요청이 영어 보고서·저비용 모델·토큰 상한을 지키는지 mock으로 검증한다.
# 실제 모델을 호출하지 않고 비용 및 개인정보 보호 설정의 회귀를 막기 위해 필요하다.

from copy import deepcopy

import pytest

from pandok_reports import (
    BEDROCK_MODEL_ID,
    MAX_OUTPUT_TOKENS,
    GoldReportInputError,
    ReportGenerationError,
    build_gold_report_input,
    generate_gold_report,
)


class FakeBedrockClient:
    def __init__(self, response):
        self.response = response
        self.request = None

    def converse(self, **kwargs):
        self.request = kwargs
        return self.response


def _report_input():
    return build_gold_report_input(
        "2026-09-04",
        run_quality=[],
        run_outcomes=[],
        checkpoint_metrics=[],
        upgrade_funnel=[],
        run_progression=[],
        upgrade_post_selection=[],
    )


def test_generates_english_markdown_with_bounded_nova_request():
    client = FakeBedrockClient(
        {
            "output": {
                "message": {
                    "content": [{"text": "# Executive Summary\nNo runs were supplied."}]
                }
            },
            "usage": {"inputTokens": 180, "outputTokens": 24, "totalTokens": 204},
            "stopReason": "end_turn",
        }
    )

    result = generate_gold_report(_report_input(), bedrock_client=client)

    assert result.markdown.startswith("# Executive Summary")
    assert result.output_tokens == 24
    assert client.request["modelId"] == BEDROCK_MODEL_ID
    assert client.request["inferenceConfig"]["maxTokens"] == MAX_OUTPUT_TOKENS
    assert "concise English Markdown" in client.request["system"][0]["text"]
    assert "INSUFFICIENT_SAMPLE" in client.request["system"][0]["text"]


def test_revalidates_payload_before_bedrock_call():
    payload = deepcopy(_report_input())
    payload["metrics"]["run_quality"] = [{"run_id": "prohibited"}]
    client = FakeBedrockClient({})

    with pytest.raises(GoldReportInputError, match="unexpected=.*run_id"):
        generate_gold_report(payload, bedrock_client=client)

    assert client.request is None


def test_rejects_response_without_report_text():
    client = FakeBedrockClient(
        {"output": {"message": {"content": []}}, "usage": {}}
    )

    with pytest.raises(ReportGenerationError, match="보고서 텍스트"):
        generate_gold_report(_report_input(), bedrock_client=client)
