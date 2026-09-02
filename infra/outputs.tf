# Lambda 환경변수에 연결할 Kinesis 스트림 이름을 출력한다.
# 스트리밍이 꺼져 있을 때는 존재하지 않는 리소스를 참조하지 않고 null을 반환한다.

output "kinesis_stream_name" {
  description = "활성화된 PANDOK telemetry Kinesis 스트림 이름"
  value       = try(aws_kinesis_stream.telemetry[0].name, null)
}

output "firehose_delivery_stream_name" {
  description = "활성화된 PANDOK Bronze Firehose 전송 스트림 이름"
  value       = try(aws_kinesis_firehose_delivery_stream.bronze[0].name, null)
}

output "ingestion_lambda_function_name" {
  description = "활성화된 PANDOK ingestion Lambda 함수 이름"
  value       = try(aws_lambda_function.ingestion[0].function_name, null)
}
