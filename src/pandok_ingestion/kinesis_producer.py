# 검증과 포장이 끝난 v2 Bronze 레코드를 Kinesis Data Streams로 전송한다.
# 같은 Run의 이벤트 순서를 유지하며 Firehose를 통해 S3에 저장하기 위해 필요하다.

import json
from typing import Any, Mapping, Protocol


class KinesisClient(Protocol):
    """Define the Kinesis client operation used by the producer."""

    def put_record(
        self,
        *,
        StreamName: str,
        Data: bytes,
        PartitionKey: str,
    ) -> Mapping[str, Any]: ...


def put_bronze_record(
    bronze_record: Mapping[str, Any],
    stream_name: str,
    kinesis_client: KinesisClient,
) -> Mapping[str, Any]:
    """Send one validated Bronze record to Kinesis."""

    # 같은 run_id를 Partition Key로 사용해 한 Run의 이벤트를 같은 shard로 보낸다.
    run_id = str(bronze_record["event"]["run_id"])

    # Firehose가 여러 이벤트를 S3에 저장할 때 레코드를 구분하도록 줄바꿈을 추가한다.
    record_data = (
        json.dumps(
            bronze_record,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")

    # 이벤트 하나를 Kinesis 레코드 하나로 전송한다.
    return kinesis_client.put_record(
        StreamName=stream_name,
        Data=record_data,
        PartitionKey=run_id,
    )