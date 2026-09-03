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
      var.bronze_retention_days <= 30
    )
    error_message = "데이터 보관 기간은 1일 이상 30일 이하여야 합니다."
  }
}

variable "silver_retention_days" {
  description = "Silver Parquet 데이터를 AWS에 보관하는 기간"
  type        = number

  # Silver도 승인된 최대 보관 기간인 30일을 넘지 않게 한다.
  default  = 30
  nullable = false

  validation {
    condition = (
      var.silver_retention_days >= 1 &&
      var.silver_retention_days <= 30
    )
    error_message = "Silver 보관 기간은 1일 이상 30일 이하여야 합니다."
  }
}

variable "enable_streaming" {
  description = "Kinesis와 Firehose 실시간 스트리밍 리소스 생성 여부"
  type        = bool

  # 작업하지 않을 때 시간당 비용이 발생하는 스트림을 제거하도록 기본값을 끈다.
  default  = false
  nullable = false
}

variable "kinesis_shard_count" {
  description = "Kinesis Provisioned 모드에서 사용할 shard 수"
  type        = number

  # 개인 프로젝트의 낮은 처리량에는 shard 1개로 시작한다.
  default  = 1
  nullable = false

  # 설정 실수로 사용량보다 많은 shard가 생성되어 고정 비용이 커지는 것을 막는다.
  validation {
    condition = (
      floor(var.kinesis_shard_count) == var.kinesis_shard_count &&
      var.kinesis_shard_count >= 1 &&
      var.kinesis_shard_count <= 2
    )
    error_message = "Kinesis shard 수는 1~2 사이의 정수여야 합니다."
  }
}

variable "ingestion_lambda_memory_mb" {
  description = "Ingestion Lambda에 할당할 메모리 크기(MiB)"
  type        = number

  # JSON Schema 검증에 필요한 여유를 두되 개인 프로젝트 비용을 제한한다.
  default  = 256
  nullable = false

  validation {
    condition = contains(
      [128, 256, 512],
      var.ingestion_lambda_memory_mb,
    )
    error_message = "Lambda 메모리는 128, 256, 512MiB 중 하나여야 합니다."
  }
}

variable "ingestion_lambda_timeout_seconds" {
  description = "Ingestion Lambda 요청 1건의 최대 실행 시간(초)"
  type        = number

  # 이벤트 1건 검증과 Kinesis 전송만 수행하므로 장시간 실행을 차단한다.
  default  = 10
  nullable = false

  validation {
    condition = (
      floor(var.ingestion_lambda_timeout_seconds) ==
      var.ingestion_lambda_timeout_seconds &&
      var.ingestion_lambda_timeout_seconds >= 3 &&
      var.ingestion_lambda_timeout_seconds <= 15
    )
    error_message = "Lambda 제한 시간은 3~15초 사이의 정수여야 합니다."
  }
}

variable "ingestion_lambda_reserved_concurrency" {
  description = "Ingestion Lambda가 동시에 실행될 수 있는 최대 개수"
  type        = number

  # 여러 게임 이벤트가 동시에 들어와도 초기 테스트에서 과도한 요청 거부를 피한다.
  default  = 5
  nullable = false

  validation {
    condition = (
      floor(var.ingestion_lambda_reserved_concurrency) ==
      var.ingestion_lambda_reserved_concurrency &&
      var.ingestion_lambda_reserved_concurrency >= 1 &&
      var.ingestion_lambda_reserved_concurrency <= 10
    )
    error_message = "Lambda 예약 동시 실행 수는 1~10 사이의 정수여야 합니다."
  }
}

variable "ingestion_shared_secret" {
  description = "Türkiye Gateway가 ingestion API 호출 시 보내는 공유 비밀값"
  type        = string

  # 비밀값은 공개 예시나 Git이 아니라 개인 terraform.tfvars에서만 설정한다.
  default   = null
  nullable  = true
  sensitive = true

  validation {
    condition     = try(length(var.ingestion_shared_secret) >= 32, false)
    error_message = "항상 유지되는 ingestion API에는 32자 이상의 ingestion_shared_secret이 필요합니다."
  }
}

variable "ingestion_api_rate_limit" {
  description = "Ingestion HTTP API가 지속적으로 허용할 초당 요청 수"
  type        = number

  # 실제 게임 테스트에 여유를 주면서 비정상적인 지속 요청을 제한한다.
  default  = 20
  nullable = false

  validation {
    condition = (
      var.ingestion_api_rate_limit >= 1 &&
      var.ingestion_api_rate_limit <= 100
    )
    error_message = "API 초당 요청 제한은 1~100 사이여야 합니다."
  }
}

variable "ingestion_api_burst_limit" {
  description = "Ingestion HTTP API가 순간적으로 허용할 최대 요청 수"
  type        = number

  # 여러 Run 이벤트가 동시에 도착하는 짧은 순간에는 기본 처리량보다 여유를 둔다.
  default  = 40
  nullable = false

  validation {
    condition = (
      floor(var.ingestion_api_burst_limit) ==
      var.ingestion_api_burst_limit &&
      var.ingestion_api_burst_limit >= var.ingestion_api_rate_limit &&
      var.ingestion_api_burst_limit <= 200
    )
    error_message = "API burst 제한은 rate 제한 이상이며 200 이하의 정수여야 합니다."
  }
}
