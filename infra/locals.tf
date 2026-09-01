# AWS 리소스 이름과 공통 태그를 한곳에서 정의한다.
# 환경별 이름 충돌을 막고 PANDOK 비용을 Cost Explorer에서 구분하기 위해 사용한다.

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Purpose     = "steam-telemetry"

    # PANDOK 관련 비용을 태그 기준으로 검색하고 집계하기 위한 값이다.
    CostScope = "pandok"
  }
}