# Bronze 원본 텔레메트리를 변경하지 않고 S3에 보관한다.
# 재처리 원본을 확보하되 dev에서는 테스트 리소스를 쉽게 정리하기 위해 사용한다.

resource "aws_s3_bucket" "bronze" {
  bucket_prefix = "${local.name_prefix}-bronze-"

  # dev에서는 테스트 객체까지 함께 제거하고, 운영 환경에서는 원본 오삭제를 막는다.
  force_destroy = var.environment == "dev"
}

# 실수로 버킷이나 객체에 공개 권한을 설정해도 외부 노출을 차단한다.
resource "aws_s3_bucket_public_access_block" "bronze" {
  bucket = aws_s3_bucket.bronze.id

  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}

# 업로드 주체와 관계없이 현재 AWS 계정이 객체를 소유하도록 하고 ACL 사용을 막는다.
resource "aws_s3_bucket_ownership_controls" "bronze" {
  bucket = aws_s3_bucket.bronze.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# Bronze 원본을 저장할 때 자동으로 암호화하며 별도 KMS 사용료는 발생시키지 않는다.
resource "aws_s3_bucket_server_side_encryption_configuration" "bronze" {
  bucket = aws_s3_bucket.bronze.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Bronze 원본을 설정된 보관 기간 후 삭제해 개인정보와 저장 비용이 계속 쌓이지 않게 한다.
resource "aws_s3_bucket_lifecycle_configuration" "bronze" {
  bucket = aws_s3_bucket.bronze.id

  rule {
    id     = "expire-bronze-data"
    status = "Enabled"

    filter {}

    expiration {
      days = var.bronze_retention_days
    }

    # 완료되지 못한 업로드 조각도 비용을 발생시키므로 7일 후 제거한다.
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# 네트워크 전송 중 Bronze 데이터가 노출되지 않도록 HTTPS 연결만 허용한다.
resource "aws_s3_bucket_policy" "bronze_https_only" {
  bucket = aws_s3_bucket.bronze.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.bronze.arn,
          "${aws_s3_bucket.bronze.arn}/*"
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