-- Plain Parquet Silver를 Glue Catalog 기반 Iceberg v2 테이블로 변환한다.
-- Athena와 Snowflake가 같은 snapshot과 스키마를 조회할 수 있게 하기 위해 필요하다.

CREATE TABLE pandok_dev.silver_events_iceberg
WITH (
    table_type = 'ICEBERG',
    is_external = false,
    location = 's3://__SILVER_BUCKET__/iceberg/silver_events/',
    format = 'PARQUET',
    write_compression = 'SNAPPY',
    partitioning = ARRAY['received_date']
)
AS
SELECT
    run_id,
    event_id,
    event_name,
    event_sequence,
    run_elapsed_seconds,
    source_type,
    game_version,
    schema_version,
    run_status,
    first_received_at,
    ingestion_channel,
    event_payload_json,
    quality_issues_json,
    input_event_count,
    unique_event_count,
    exact_retry_count,
    conflicting_duplicate_count,

    -- CTAS에서는 파티션 컬럼을 SELECT의 마지막에 둔다.
    received_date
FROM pandok_dev.silver_events;