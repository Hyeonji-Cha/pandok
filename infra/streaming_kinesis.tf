# 검증된 v2 Bronze 레코드를 실시간으로 받아 Firehose에 전달할 Kinesis 스트림을 만든다.
# 작업 중에만 생성하고 최소 용량·보존 기간을 사용해 개인 프로젝트의 고정 비용을 제한한다.

resource "aws_kinesis_stream" "telemetry" {
  count = var.enable_streaming ? 1 : 0

  name             = "${local.name_prefix}-telemetry"
  shard_count      = var.kinesis_shard_count
  retention_period = 24

  # 낮은 트래픽에서 처리 용량과 고정 비용을 명확하게 제한하도록 Provisioned를 사용한다.
  stream_mode_details {
    stream_mode = "PROVISIONED"
  }

  # 별도 고객 관리 KMS 키 비용 없이 AWS 관리형 키로 스트림 데이터를 암호화한다.
  encryption_type = "KMS"
  kms_key_id      = "alias/aws/kinesis"

  tags = {
    DataLayer = "bronze-stream"
  }
}
