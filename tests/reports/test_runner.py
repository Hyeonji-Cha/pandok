# Athena Gold 조회부터 Bedrock 보고서 반환까지 연결되는지 가짜 AWS 응답으로 검증한다.
# 네 번의 제한 조회와 단 한 번의 모델 호출 원칙을 실제 비용 없이 확인하기 위해 필요하다.

from pandok_reports import generate_report_from_athena


class FakePaginator:
    def __init__(self, pages_by_query_id):
        self.pages_by_query_id = pages_by_query_id

    def paginate(self, *, QueryExecutionId):
        return self.pages_by_query_id[QueryExecutionId]


class FakeAthenaClient:
    def __init__(self):
        self.started_queries = []
        self.pages_by_query_id = {}

    def start_query_execution(self, **kwargs):
        query_id = f"query-{len(self.started_queries) + 1}"
        self.started_queries.append(kwargs)
        self.pages_by_query_id[query_id] = [_empty_result_page()]
        return {"QueryExecutionId": query_id}

    def get_query_execution(self, **_kwargs):
        return {"QueryExecution": {"Status": {"State": "SUCCEEDED"}}}

    def stop_query_execution(self, **_kwargs):
        return {}

    def get_paginator(self, operation_name):
        assert operation_name == "get_query_results"
        return FakePaginator(self.pages_by_query_id)


class FakeBedrockClient:
    def __init__(self):
        self.requests = []

    def converse(self, **kwargs):
        self.requests.append(kwargs)
        return {
            "output": {
                "message": {"content": [{"text": "# Executive Summary\nNo data."}]}
            },
            "usage": {"inputTokens": 150, "outputTokens": 12, "totalTokens": 162},
            "stopReason": "end_turn",
        }


def _empty_result_page():
    return {
        "ResultSet": {
            "ResultSetMetadata": {"ColumnInfo": []},
            "Rows": [],
        }
    }


def test_queries_four_bounded_gold_sections_and_invokes_bedrock_once():
    athena = FakeAthenaClient()
    bedrock = FakeBedrockClient()

    result = generate_report_from_athena(
        "2026-09-04",
        athena_client=athena,
        bedrock_client=bedrock,
    )

    assert result.total_tokens == 162
    assert len(athena.started_queries) == 4
    assert all("LIMIT" in query["QueryString"] for query in athena.started_queries)
    assert all(query["WorkGroup"] == "pandok-dev" for query in athena.started_queries)
    assert len(bedrock.requests) == 1
