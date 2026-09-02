# Kinesis의 v2 Bronze 레코드를 버퍼링해 S3 Bronze 영역에 연속 저장한다.
# 별도 서버 없이 스트림을 S3로 전달하되 압축과 5분 버퍼로 저장·조회 비용을 줄인다.

data "aws_iam_policy_document" "firehose_assume_role" {
  count = var.enable_streaming ? 1 : 0

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["firehose.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "firehose" {
  count = var.enable_streaming ? 1 : 0

  name               = "${local.name_prefix}-firehose-role"
  assume_role_policy = data.aws_iam_policy_document.firehose_assume_role[0].json
}

data "aws_iam_policy_document" "firehose" {
  count = var.enable_streaming ? 1 : 0

  # Firehose가 지정된 Kinesis 스트림만 읽을 수 있도록 제한한다.
  statement {
    effect = "Allow"
    actions = [
      "kinesis:DescribeStream",
      "kinesis:DescribeStreamSummary",
      "kinesis:GetRecords",
      "kinesis:GetShardIterator",
      "kinesis:ListShards",
    ]
    resources = [aws_kinesis_stream.telemetry[0].arn]
  }

  # S3 버킷 자체를 확인하는 데 필요한 권한만 허용한다.
  statement {
    effect = "Allow"
    actions = [
      "s3:GetBucketLocation",
      "s3:ListBucket",
      "s3:ListBucketMultipartUploads",
    ]
    resources = [aws_s3_bucket.bronze.arn]
  }

  # Firehose가 Bronze 객체를 쓰거나 실패한 멀티파트 업로드를 정리하도록 허용한다.
  statement {
    effect = "Allow"
    actions = [
      "s3:AbortMultipartUpload",
      "s3:PutObject",
    ]
    resources = ["${aws_s3_bucket.bronze.arn}/*"]
  }
}

resource "aws_iam_role_policy" "firehose" {
  count = var.enable_streaming ? 1 : 0

  name   = "${local.name_prefix}-firehose-policy"
  role   = aws_iam_role.firehose[0].id
  policy = data.aws_iam_policy_document.firehose[0].json
}

resource "aws_kinesis_firehose_delivery_stream" "bronze" {
  count = var.enable_streaming ? 1 : 0

  name        = "${local.name_prefix}-bronze-delivery"
  destination = "extended_s3"

  kinesis_source_configuration {
    kinesis_stream_arn = aws_kinesis_stream.telemetry[0].arn
    role_arn           = aws_iam_role.firehose[0].arn
  }

  extended_s3_configuration {
    role_arn   = aws_iam_role.firehose[0].arn
    bucket_arn = aws_s3_bucket.bronze.arn

    # 수신 날짜만 파티션으로 사용해 동적 파티셔닝 비용과 작은 파일 증가를 피한다.
    prefix              = "bronze/received_date=!{timestamp:yyyy-MM-dd}/"
    error_output_prefix = "bronze-errors/error_type=!{firehose:error-output-type}/received_date=!{timestamp:yyyy-MM-dd}/"

    # 5MiB 또는 5분 중 먼저 충족되는 시점에 압축 파일을 만들어 S3 PUT 횟수를 줄인다.
    buffering_size     = 5
    buffering_interval = 300
    compression_format = "GZIP"
  }

  depends_on = [
    aws_iam_role_policy.firehose,
    aws_s3_bucket_server_side_encryption_configuration.bronze,
  ]

  tags = {
    DataLayer = "bronze-delivery"
  }
}
