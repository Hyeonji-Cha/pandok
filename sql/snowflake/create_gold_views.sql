-- Silver Iceberg 이벤트를 분석용 Gold 지표와 품질 검사 View로 변환한다.
-- Snowflake Workspace에만 있던 SQL을 Git과 Airflow에서 재사용하기 위해 필요하다.

USE ROLE ACCOUNTADMIN;

CREATE SCHEMA IF NOT EXISTS PANDOK.GOLD;

GRANT USAGE ON SCHEMA PANDOK.GOLD TO ROLE PANDOK_ENGINEER;
GRANT CREATE VIEW ON SCHEMA PANDOK.GOLD TO ROLE PANDOK_ENGINEER;

USE ROLE PANDOK_ENGINEER;
USE WAREHOUSE PANDOK_WH;
USE DATABASE PANDOK;
USE SCHEMA GOLD;

-- 이벤트 한 행마다 반복되는 Run 품질 값을 Run당 한 번만 집계한다.
CREATE OR REPLACE VIEW RUN_QUALITY_SUMMARY AS
WITH ONE_ROW_PER_RUN AS (
  SELECT
    run_id,
    run_status,
    input_event_count,
    unique_event_count,
    exact_retry_count,
    conflicting_duplicate_count,
    ROW_NUMBER() OVER (
      PARTITION BY run_id
      ORDER BY event_sequence DESC
    ) AS row_number_in_run
  FROM PANDOK.SILVER.SILVER_EVENTS
)
SELECT
  run_status,
  COUNT(*) AS run_count,
  SUM(input_event_count) AS input_event_count,
  SUM(unique_event_count) AS unique_event_count,
  SUM(exact_retry_count) AS exact_retry_count,
  SUM(conflicting_duplicate_count) AS conflicting_duplicate_count
FROM ONE_ROW_PER_RUN
WHERE row_number_in_run = 1
GROUP BY run_status;

-- 동의한 실제 플레이 데이터만 사용해 종료 사유와 평균 플레이 시간을 계산한다.
CREATE OR REPLACE VIEW PRODUCT_RUN_OUTCOME AS
WITH ENDED_RUNS AS (
  SELECT
    run_id,
    run_elapsed_seconds,
    TRY_PARSE_JSON(event_payload_json):end_reason::STRING AS end_reason
  FROM PANDOK.SILVER.SILVER_EVENTS
  WHERE source_type = 'CONSENTED_PROD_PLAY'
    AND event_name = 'run_ended'
)
SELECT
  end_reason,
  COUNT(*) AS ended_run_count,
  ROUND(
    100.0 * COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (), 0),
    2
  ) AS ended_run_percentage,
  ROUND(AVG(run_elapsed_seconds), 2) AS average_run_seconds
FROM ENDED_RUNS
GROUP BY end_reason;

-- 체크포인트별 성장·생존 상태의 평균을 계산한다.
CREATE OR REPLACE VIEW PRODUCT_CHECKPOINT_METRICS AS
WITH CHECKPOINTS AS (
  SELECT
    TRY_PARSE_JSON(event_payload_json) AS payload
  FROM PANDOK.SILVER.SILVER_EVENTS
  WHERE source_type = 'CONSENTED_PROD_PLAY'
    AND event_name = 'run_checkpoint'
)
SELECT
  payload:checkpoint_number::NUMBER AS checkpoint_number,
  COUNT(*) AS checkpoint_event_count,
  ROUND(AVG(payload:player_level::NUMBER), 2) AS average_player_level,
  ROUND(AVG(payload:current_xp::FLOAT), 2) AS average_current_xp,
  ROUND(AVG(payload:xp_to_next_level::FLOAT), 2) AS average_xp_to_next_level,
  ROUND(AVG(payload:hp_percent::FLOAT), 2) AS average_hp_percent,
  ROUND(AVG(payload:total_kills::NUMBER), 2) AS average_total_kills,
  ROUND(AVG(payload:current_gold::FLOAT), 2) AS average_current_gold
FROM CHECKPOINTS
GROUP BY checkpoint_number;

-- 노출 선택지를 행으로 펼친 뒤 실제 선택과 연결해 아이템 선택률을 계산한다.
CREATE OR REPLACE VIEW PRODUCT_UPGRADE_FUNNEL AS
WITH SHOWN_EVENTS AS (
  SELECT
    run_id,
    TRY_PARSE_JSON(event_payload_json) AS payload
  FROM PANDOK.SILVER.SILVER_EVENTS
  WHERE source_type = 'CONSENTED_PROD_PLAY'
    AND event_name = 'upgrade_options_shown'
),
EXPOSED_OPTIONS AS (
  SELECT
    run_id,
    payload:choice_id::STRING AS choice_id,
    payload:choice_source::STRING AS choice_source,
    flattened_option.value:item_id::STRING AS item_id,
    flattened_option.value:rarity::STRING AS rarity
  FROM SHOWN_EVENTS,
  LATERAL FLATTEN(INPUT => payload:options) AS flattened_option
),
SELECTED_EVENTS AS (
  SELECT
    run_id,
    TRY_PARSE_JSON(event_payload_json):choice_id::STRING AS choice_id,
    TRY_PARSE_JSON(event_payload_json):selected_item_id::STRING
      AS selected_item_id
  FROM PANDOK.SILVER.SILVER_EVENTS
  WHERE source_type = 'CONSENTED_PROD_PLAY'
    AND event_name = 'upgrade_selected'
)
SELECT
  exposed.choice_source,
  exposed.item_id,
  exposed.rarity,
  COUNT(*) AS exposure_count,
  COUNT_IF(selected.selected_item_id IS NOT NULL) AS selection_count,
  ROUND(
    100.0 * COUNT_IF(selected.selected_item_id IS NOT NULL)
    / NULLIF(COUNT(*), 0),
    2
  ) AS selection_percentage
FROM EXPOSED_OPTIONS AS exposed
LEFT JOIN SELECTED_EVENTS AS selected
  ON exposed.run_id = selected.run_id
  AND exposed.choice_id = selected.choice_id
  AND exposed.item_id = selected.selected_item_id
GROUP BY
  exposed.choice_source,
  exposed.item_id,
  exposed.rarity;

-- 비정상 범위가 하나라도 있으면 후속 리포트 적재를 중단할 수 있게 한다.
CREATE OR REPLACE VIEW QUALITY_CHECKS AS
WITH CHECK_RESULTS AS (
  SELECT
    'run_quality_non_negative' AS check_name,
    COUNT(*) AS failed_row_count
  FROM RUN_QUALITY_SUMMARY
  WHERE run_count < 0
     OR input_event_count < 0
     OR unique_event_count < 0
     OR exact_retry_count < 0
     OR conflicting_duplicate_count < 0

  UNION ALL

  SELECT
    'run_outcome_percentage',
    CASE
      WHEN COUNT(*) = 0 THEN 0
      WHEN ABS(SUM(ended_run_percentage) - 100) > 0.1 THEN 1
      ELSE 0
    END
  FROM PRODUCT_RUN_OUTCOME

  UNION ALL

  SELECT
    'checkpoint_value_ranges',
    COUNT(*)
  FROM PRODUCT_CHECKPOINT_METRICS
  WHERE checkpoint_number < 1
     OR checkpoint_event_count < 1
     OR average_player_level < 0
     OR average_current_xp < 0
     OR average_xp_to_next_level <= 0
     OR average_hp_percent < 0
     OR average_hp_percent > 100
     OR average_total_kills < 0
     OR average_current_gold < 0

  UNION ALL

  SELECT
    'upgrade_funnel_ranges',
    COUNT(*)
  FROM PRODUCT_UPGRADE_FUNNEL
  WHERE exposure_count < 1
     OR selection_count < 0
     OR selection_count > exposure_count
     OR selection_percentage < 0
     OR selection_percentage > 100
)
SELECT
  check_name,
  failed_row_count,
  IFF(failed_row_count = 0, 'PASS', 'FAIL') AS check_status
FROM CHECK_RESULTS;
