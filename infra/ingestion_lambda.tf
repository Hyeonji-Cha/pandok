# API Gateway의 v2 이벤트를 검증하고 Bronze 레코드를 Kinesis에 넣는 Lambda를 만든다.
# 서버를 상시 운영하지 않고 요청이 있을 때만 실행해 개인 프로젝트의 수집 비용을 줄인다.

locals {
  ingestion_lambda_zip_path = "${path.module}/../build/pandok-ingestion-lambda.zip"
}

data "aws_iam_policy_document" "ingestion_lambda_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ingestion_lambda" {
  name               = "${local.name_prefix}-ingestion-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.ingestion_lambda_assume_role.json
}

# Lambda 런타임 로그는 요청 본문을 기록하지 않고 운영 오류 확인용으로 7일만 보관한다.
resource "aws_cloudwatch_log_group" "ingestion_lambda" {
  name              = "/aws/lambda/${local.name_prefix}-ingestion"
  retention_in_days = 7
}

data "aws_iam_policy_document" "ingestion_lambda" {
  # 이 Lambda는 PANDOK telemetry 스트림 하나에 레코드를 넣는 작업만 허용한다.
  dynamic "statement" {
    for_each = var.enable_streaming ? [1] : []

    content {
      effect    = "Allow"
      actions   = ["kinesis:PutRecord"]
      resources = [aws_kinesis_stream.telemetry[0].arn]
    }
  }

  # 애플리케이션이 직접 본문을 기록하지 않는 CloudWatch 로그 스트림만 허용한다.
  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["${aws_cloudwatch_log_group.ingestion_lambda.arn}:*"]
  }
}

resource "aws_iam_role_policy" "ingestion_lambda" {
  name   = "${local.name_prefix}-ingestion-lambda-policy"
  role   = aws_iam_role.ingestion_lambda.id
  policy = data.aws_iam_policy_document.ingestion_lambda.json
}

resource "aws_lambda_function" "ingestion" {
  function_name = "${local.name_prefix}-ingestion"
  description   = "Validate PANDOK telemetry v2 events and publish Bronze records to Kinesis."
  role          = aws_iam_role.ingestion_lambda.arn

  filename         = local.ingestion_lambda_zip_path
  source_code_hash = filebase64sha256(local.ingestion_lambda_zip_path)
  handler          = "pandok_ingestion.lambda_entrypoint.lambda_handler"
  runtime          = "python3.12"
  architectures    = ["x86_64"]

  memory_size                    = var.ingestion_lambda_memory_mb
  timeout                        = var.ingestion_lambda_timeout_seconds
  reserved_concurrent_executions = var.ingestion_lambda_reserved_concurrency

  environment {
    variables = {
      INGESTION_SHARED_SECRET = var.ingestion_shared_secret
      KINESIS_STREAM_NAME     = try(aws_kinesis_stream.telemetry[0].name, "")
      STREAMING_ENABLED       = tostring(var.enable_streaming)
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.ingestion_lambda,
    aws_iam_role_policy.ingestion_lambda,
  ]

  tags = {
    Component = "ingestion"
  }
}
