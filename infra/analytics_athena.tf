# Athena 쿼리 결과 위치와 데이터 스캔 상한을 공통 설정으로 관리한다.
# 잘못된 전체 테이블 조회로 비용이 커지는 것을 막고 Silver 조회 환경을 재현하기 위해 필요하다.

resource "aws_athena_workgroup" "pandok" {
  name  = local.name_prefix
  state = "ENABLED"

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = false
    requester_pays_enabled             = false


    # Terraform AWS Provider가 허용하는 최소값인 10MiB로
    # 쿼리당 스캔량을 제한해 실수로 인한 대규모 조회를 막는다.
    bytes_scanned_cutoff_per_query = 10 * 1024 * 1024

    result_configuration {
      output_location = "s3://${aws_s3_bucket.silver.id}/athena-results/"

      # 별도 KMS 비용 없이 Athena 결과 파일을 S3에서 암호화한다.
      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }
}