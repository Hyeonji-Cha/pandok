-- 재복원된 Plain Parquet Silver를 지정한 날짜의 Iceberg snapshot으로 다시 적재한다.
-- retry·late-event 판정이 변경되어도 해당 날짜를 최신 결과로 교체하기 위해 필요하다.

INSERT INTO pandok_dev.silver_events_iceberg
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
    received_date
FROM pandok_dev.silver_events
WHERE received_date = '__RECEIVED_DATE__';