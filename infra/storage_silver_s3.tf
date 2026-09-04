# 정제·중복 제거된 Silver Parquet 데이터를 Bronze와 분리해 저장한다.
# 원본과 분석용 데이터의 보존 정책·접근 권한을 독립적으로 관리하기 위해 필요하다.

resource "aws_s3_bucket" "silver" {
  bucket_prefix = "${local.name_prefix}-silver-"

  # dev 환경에서는 Terraform 제거 시 테스트 Parquet도 함께 정리할 수 있게 한다.
  force_destroy = var.environment == "dev"
}

# 실수로 Silver 데이터가 외부에 공개되는 것을 차단한다.
resource "aws_s3_bucket_public_access_block" "silver" {
  bucket = aws_s3_bucket.silver.id

  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}

# ACL을 사용하지 않고 현재 AWS 계정이 모든 Silver 객체를 소유하게 한다.
resource "aws_s3_bucket_ownership_controls" "silver" {
  bucket = aws_s3_bucket.silver.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# 별도 KMS 비용 없이 저장되는 Silver Parquet를 자동 암호화한다.
resource "aws_s3_bucket_server_side_encryption_configuration" "silver" {
  bucket = aws_s3_bucket.silver.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# 테스트 Silver 데이터가 승인된 기간을 넘겨 계속 쌓이지 않게 한다.
resource "aws_s3_bucket_lifecycle_configuration" "silver" {
  bucket = aws_s3_bucket.silver.id

  # Plain Parquet staging은 설정된 보관 기간 후 자동 삭제한다.
  rule {
    id     = "expire-silver-staging"
    status = "Enabled"

    filter {
      prefix = "silver/"
    }

    expiration {
      days = var.silver_retention_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  # INVALID Run도 승인된 보관 기간을 넘기지 않게 한다.
  rule {
    id     = "expire-quarantine-data"
    status = "Enabled"

    filter {
      prefix = "quarantine/"
    }

    expiration {
      days = var.silver_retention_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  # Athena 쿼리 결과가 계속 누적되어 저장 비용을 만들지 않게 한다.
  rule {
    id     = "expire-athena-results"
    status = "Enabled"

    filter {
      prefix = "athena-results/"
    }

    expiration {
      days = var.silver_retention_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  # AI 보고서도 승인된 기간 뒤 삭제해 오래된 분석과 저장 비용이 누적되지 않게 한다.
  rule {
    id     = "expire-ai-reports"
    status = "Enabled"

    filter {
      prefix = "ai-reports/"
    }

    expiration {
      days = var.silver_retention_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# 암호화되지 않은 HTTP 연결로 Silver 데이터에 접근하는 것을 거부한다.
resource "aws_s3_bucket_policy" "silver_https_only" {
  bucket = aws_s3_bucket.silver.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.silver.arn,
          "${aws_s3_bucket.silver.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}
