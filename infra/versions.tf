# Terraform CLI와 AWS Provider의 호환 가능한 버전 범위를 정의한다.
# 실행 환경마다 다른 버전이 설치되어 예기치 않은 동작 차이가 생기는 것을 막는다.

terraform {
  required_version = ">= 1.15.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.57"
    }
  }
}