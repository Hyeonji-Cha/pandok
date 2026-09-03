# Türkiye Gateway가 v2 telemetry를 전송할 최소 HTTP API와 Lambda 경로를 만든다.
# 단일 POST 경로·요청 제한·로그 비활성화로 공개 진입점의 공격면과 비용을 줄인다.

resource "aws_apigatewayv2_api" "ingestion" {
  name          = "${local.name_prefix}-ingestion-api"
  protocol_type = "HTTP"

  tags = {
    Component = "ingestion-api"
  }
}

resource "aws_apigatewayv2_integration" "ingestion_lambda" {
  api_id                 = aws_apigatewayv2_api.ingestion.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.ingestion.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
  timeout_milliseconds   = 12000
}

resource "aws_apigatewayv2_route" "telemetry_v2" {
  api_id    = aws_apigatewayv2_api.ingestion.id
  route_key = "POST /telemetry/v2"
  target    = "integrations/${aws_apigatewayv2_integration.ingestion_lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.ingestion.id
  name        = "$default"
  auto_deploy = true

  # Access log와 상세 지표를 만들지 않고 요청 폭주만 제한한다.
  default_route_settings {
    detailed_metrics_enabled = false
    throttling_rate_limit    = var.ingestion_api_rate_limit
    throttling_burst_limit   = var.ingestion_api_burst_limit
  }

  tags = {
    Component = "ingestion-api"
  }
}

# 이 API의 telemetry v2 POST 경로만 ingestion Lambda를 호출할 수 있다.
resource "aws_lambda_permission" "api_gateway_ingestion" {
  statement_id  = "AllowIngestionApiInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingestion.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.ingestion.execution_arn}/*/POST/telemetry/v2"
}
