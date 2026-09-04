# Snowflake가 PANDOK Iceberg 저장소와 Glue Catalog에 접근할 IAM Role을 만든다.
# S3 데이터와 Glue metadata를 동일한 Iceberg 테이블로 연결하기 위해 필요하다.

data "aws_caller_identity" "current" {}

locals {
  # Snowflake 정보가 아직 없을 때는 현재 AWS 사용자만 임시 신뢰한다.
  snowflake_trusted_principal_arn = coalesce(
    var.snowflake_iam_user_arn,
    data.aws_caller_identity.current.arn,
  )
}

data "aws_iam_policy_document" "snowflake_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = [local.snowflake_trusted_principal_arn]
    }

    dynamic "condition" {
      for_each = length(var.snowflake_external_ids) > 0 ? [1] : []

      content {
        test     = "ForAnyValue:StringEquals"
        variable = "sts:ExternalId"
        values   = var.snowflake_external_ids
      }
    }
  }
}

resource "aws_iam_role" "snowflake_iceberg" {
  name               = "${local.name_prefix}-snowflake-iceberg-role"
  assume_role_policy = data.aws_iam_policy_document.snowflake_assume_role.json
}

data "aws_iam_policy_document" "snowflake_iceberg" {
  # Snowflake가 Iceberg가 사용하는 S3 prefix만 조회하게 한다.
  statement {
    effect = "Allow"
    actions = [
      "s3:GetBucketLocation",
      "s3:ListBucket",
    ]
    resources = [aws_s3_bucket.silver.arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values = [
        "iceberg",
        "iceberg/*",
      ]
    }
  }

  # Silver 조회와 Gold 생성을 위해 Iceberg 객체만 읽고 쓰게 한다.
  statement {
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = [
      "${aws_s3_bucket.silver.arn}/iceberg/*",
    ]
  }

  # PANDOK Glue database 안의 Iceberg table metadata만 관리하게 한다.
  statement {
    effect = "Allow"
    actions = [
      "glue:GetCatalog",
      "glue:GetDatabase",
      "glue:GetDatabases",
      "glue:GetTable",
      "glue:GetTables",
      "glue:CreateTable",
      "glue:UpdateTable",
      "glue:DeleteTable",
    ]
    resources = [
      "arn:aws:glue:${var.aws_region}:${data.aws_caller_identity.current.account_id}:catalog",
      "arn:aws:glue:${var.aws_region}:${data.aws_caller_identity.current.account_id}:database/${aws_glue_catalog_database.pandok.name}",
      "arn:aws:glue:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/${aws_glue_catalog_database.pandok.name}/*",
    ]
  }
}

resource "aws_iam_role_policy" "snowflake_iceberg" {
  name   = "${local.name_prefix}-snowflake-iceberg-policy"
  role   = aws_iam_role.snowflake_iceberg.id
  policy = data.aws_iam_policy_document.snowflake_iceberg.json
}

output "snowflake_iceberg_role_arn" {
  description = "Snowflake External Volume과 Glue REST Catalog에 사용할 IAM Role ARN"
  value       = aws_iam_role.snowflake_iceberg.arn
}