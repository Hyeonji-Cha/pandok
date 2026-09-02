# Bronze 레코드가 올바른 스트림과 Run 기준으로 Kinesis에 전달되는지 테스트한다.
# 잘못된 Partition Key나 JSON 직렬화로 이벤트 순서가 깨지는 것을 배포 전에 막기 위해 필요하다.

import json
from unittest.mock import Mock

from pandok_ingestion.kinesis_producer import put_bronze_record


def test_put_bronze_record_sends_json_using_run_id() -> None:
    bronze_record = {
        "bronze_record_version": 1,
        "event": {
            "run_id": "run-123",
            "event_id": "event-1",
            "event_sequence": 1,
        },
        "metadata": {
            "ingestion_channel": "turkiye_gateway",
        },
    }
    kinesis_client = Mock()
    kinesis_client.put_record.return_value = {
        "ShardId": "shardId-000000000000",
        "SequenceNumber": "12345",
    }

    response = put_bronze_record(
        bronze_record,
        stream_name="pandok-dev-telemetry",
        kinesis_client=kinesis_client,
    )

    # Kinesis 호출에 전달된 실제 인자를 꺼내 핵심 값만 확인한다.
    call_arguments = kinesis_client.put_record.call_args.kwargs

    assert call_arguments["StreamName"] == "pandok-dev-telemetry"
    assert call_arguments["PartitionKey"] == "run-123"
    assert call_arguments["Data"].endswith(b"\n")
    assert json.loads(call_arguments["Data"].decode("utf-8")) == (
        bronze_record
    )
    assert response["SequenceNumber"] == "12345"
