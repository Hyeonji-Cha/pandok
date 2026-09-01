# 환경마다 달라질 수 있는 프로젝트명·리전·보관 기간을 입력값으로 정의한다.
# 코드 수정 없이 설정만 변경하고 잘못된 리전이나 보관 기간을 사전에 차단하기 위해 사용한다.

variable "project_name" {
  description = "Project name used in AWS resource names and tags."
  type        = string
  default     = "pandok"
  nullable    = false

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "project_name must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "environment" {
  description = "AWS 리소스를 구분하는 배포 환경 이름"
  type        = string

  # 실수로 운영 환경을 만들지 않도록 개인 개발 환경을 기본값으로 사용한다.
  default  = "dev"
  nullable = false
  # 환경 이름 오타로 별도 AWS 리소스가 생성되는 것을 막는다.
  validation {
    condition = contains(
      ["dev", "staging", "prod"],
      var.environment,
    )
    error_message = "배포 환경은 dev, staging, prod 중 하나여야 합니다."
  }
}

variable "aws_region" {
  description = "PANDOK 인프라를 배포할 AWS 리전"
  type        = string

  # 게임 운영자가 승인한 Sydney 리전에 모든 데이터를 저장한다.
  default  = "ap-southeast-2"
  nullable = false
  # 승인되지 않은 리전에 데이터와 유료 리소스가 생성되는 것을 막는다.
  validation {
    condition     = var.aws_region == "ap-southeast-2"
    error_message = "현재 PANDOK은 Sydney 리전(ap-southeast-2)만 허용합니다."
  }
}

variable "bronze_retention_days" {
  description = "Bronze 테스트 텔레메트리를 AWS에 보관하는 기간"
  type        = number

  # 친구 대상 비공개 테스트 데이터를 최대 30일 후 자동 삭제하기 위한 기준이다.
  default  = 30
  nullable = false

  validation {
    condition = (
      var.bronze_retention_days >= 1 &&
      var.bronze_retention_days <= 365
    )
    error_message = "데이터 보관 기간은 1일 이상 365일 이하여야 합니다."
  }
}
