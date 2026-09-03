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

output "ingestion_api_endpoint" {
  description = "Türkiye Gateway가 호출할 PANDOK telemetry v2 HTTPS endpoint"
  value = try(
    "${aws_apigatewayv2_api.ingestion[0].api_endpoint}/telemetry/v2",
    null,
  )
}

output "silver_bucket_name" {
  description = "Silver Parquet 데이터를 저장하는 S3 버킷 이름"
  value       = aws_s3_bucket.silver.id
}

output "glue_database_name" {
  description = "Silver와 Gold 테이블을 등록할 Glue 데이터베이스 이름"
  value       = aws_glue_catalog_database.pandok.name
}

output "silver_glue_table_name" {
  description = "Silver Parquet를 조회하는 Glue 테이블 이름"
  value       = aws_glue_catalog_table.silver_events.name
}