# S3 Silver Parquet의 컬럼과 위치를 Glue Data Catalog에 등록한다.
# Athena와 Snowflake가 동일한 Silver 구조를 테이블처럼 조회할 수 있게 하기 위해 필요하다.

resource "aws_glue_catalog_database" "pandok" {
  name = replace(local.name_prefix, "-", "_")
}

resource "aws_glue_catalog_table" "silver_events" {
  database_name = aws_glue_catalog_database.pandok.name
  name          = "silver_events"
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    EXTERNAL                                 = "TRUE"
    classification                           = "parquet"
    "projection.enabled"                     = "true"
    "projection.received_date.type"          = "date"
    "projection.received_date.format"        = "yyyy-MM-dd"
    "projection.received_date.range"         = "NOW-30DAYS,NOW"
    "projection.received_date.interval"      = "1"
    "projection.received_date.interval.unit" = "DAYS"

    # 날짜 파티션을 매번 Glue에 등록하지 않고 S3 경로에서 바로 찾는다.
    "storage.location.template" = "s3://${aws_s3_bucket.silver.id}/silver/received_date=$${received_date}/"
  }

  partition_keys {
    name = "received_date"
    type = "string"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.silver.id}/silver/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    columns {
      name = "run_id"
      type = "string"
    }

    columns {
      name = "event_id"
      type = "string"
    }

    columns {
      name = "event_name"
      type = "string"
    }

    columns {
      name = "event_sequence"
      type = "bigint"
    }

    columns {
      name = "run_elapsed_seconds"
      type = "double"
    }

    columns {
      name = "source_type"
      type = "string"
    }

    columns {
      name = "game_version"
      type = "string"
    }

    columns {
      name = "schema_version"
      type = "string"
    }

    columns {
      name = "run_status"
      type = "string"
    }

    columns {
      name = "first_received_at"
      type = "timestamp"
    }

    columns {
      name = "ingestion_channel"
      type = "string"
    }

    columns {
      name = "event_payload_json"
      type = "string"
    }

    columns {
      name = "quality_issues_json"
      type = "string"
    }

    columns {
      name = "input_event_count"
      type = "bigint"
    }

    columns {
      name = "unique_event_count"
      type = "bigint"
    }

    columns {
      name = "exact_retry_count"
      type = "bigint"
    }

    columns {
      name = "conflicting_duplicate_count"
      type = "bigint"
    }
  }
}