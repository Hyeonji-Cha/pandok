# Terraform이 어떤 AWS 리전과 인증 정보를 사용해 리소스를 관리할지 설정한다.
# 리전 실수와 리소스별 태그 누락을 막기 위해 공통 설정을 한곳에서 적용한다.

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}