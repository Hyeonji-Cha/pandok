-- Silver Iceberg 이벤트를 분석용 Gold 지표와 품질 검사 View로 변환한다.
-- Snowflake Workspace에만 있던 SQL을 Git과 Airflow에서 재사용하기 위해 필요하다.

-- PANDOK.GOLD 스키마와 권한은 최초 설정에서 이미 생성했다고 가정한다.
-- 반복 실행 DAG가 과도한 ACCOUNTADMIN 권한을 사용하지 않도록 운영 역할만 사용한다.
USE ROLE PANDOK_ENGINEER;
USE WAREHOUSE PANDOK_WH;
USE DATABASE PANDOK;
USE SCHEMA GOLD;

-- 여러 Silver 이벤트 행을 Run당 한 행으로 모아 후속 분석의 공통 기준을 만든다.
-- map_id는 현재 단일 맵이므로 비교 지표로 사용하지 않고 향후 확장과 추적을 위해서만 보존한다.
CREATE OR REPLACE VIEW RUN_SUMMARY AS
WITH PARSED_EVENTS AS (
  SELECT
    *,
    TRY_PARSE_JSON(event_payload_json) AS payload
  FROM PANDOK.SILVER.SILVER_EVENTS
),
SUMMARIZED_RUNS AS (
  SELECT
    run_id,
    MIN(received_date) AS received_date,
    MAX(source_type) AS source_type,
    MAX(game_version) AS game_version,
    MAX(run_status) AS run_status,
    COUNT_IF(event_name = 'run_started') > 0 AS is_started,
    COUNT_IF(event_name = 'run_ended') > 0 AS is_ended,
    MIN(first_received_at) AS first_received_at,
    MAX(first_received_at) AS last_received_at,
    MAX(run_elapsed_seconds) AS observed_run_seconds,
    MAX(IFF(event_name = 'run_ended', run_elapsed_seconds, NULL))
      AS run_duration_seconds,
    MAX(event_sequence) AS max_event_sequence,

    -- 시작 조건은 run_started에서만 가져오며 없는 값은 임의로 채우지 않는다.
    MAX(IFF(event_name = 'run_started', payload:map_id::STRING, NULL))
      AS map_id,
    MAX(IFF(event_name = 'run_started', payload:starting_weapon_id::STRING, NULL))
      AS starting_weapon_id,
    MAX(IFF(event_name = 'run_started', payload:starting_max_hp::FLOAT, NULL))
      AS starting_max_hp,

    -- 종료 결과는 run_ended가 없는 미완료 Run에서 NULL로 유지한다.
    MAX(IFF(event_name = 'run_ended', payload:end_reason::STRING, NULL))
      AS end_reason,
    MAX(IFF(event_name = 'run_ended', payload:final_level::NUMBER, NULL))
      AS final_level,
    MAX(IFF(event_name = 'run_ended', payload:total_kills::NUMBER, NULL))
      AS total_kills,
    MAX(IFF(event_name = 'run_ended', payload:total_xp_collected::FLOAT, NULL))
      AS total_xp_collected,
    MAX(IFF(event_name = 'run_ended', payload:current_gold::FLOAT, NULL))
      AS current_gold,
    MAX(IFF(event_name = 'run_ended', payload:total_gold_collected::FLOAT, NULL))
      AS total_gold_collected,
    MAX(IFF(event_name = 'run_ended', payload:hearts_collected::NUMBER, NULL))
      AS hearts_collected,
    MAX(IFF(event_name = 'run_ended', payload:total_healing_received::FLOAT, NULL))
      AS total_healing_received,
    MAX(IFF(event_name = 'run_ended', payload:magnets_collected::NUMBER, NULL))
      AS magnets_collected,
    MAX(IFF(event_name = 'run_ended', payload:miniboss_waves_reached::NUMBER, NULL))
      AS miniboss_waves_reached,
    MAX(IFF(event_name = 'run_ended', payload:miniboss_waves_cleared::NUMBER, NULL))
      AS miniboss_waves_cleared,
    MAX(IFF(event_name = 'run_ended', ARRAY_SIZE(payload:final_upgrades), NULL))
      AS final_upgrade_count,
    MAX(IFF(event_name = 'run_ended', TO_JSON(payload:final_upgrades), NULL))
      AS final_upgrades_json,

    -- 이벤트 횟수는 Run의 행동량과 선택 미완료 여부를 빠르게 비교할 때 사용한다.
    COUNT_IF(event_name = 'run_checkpoint') AS checkpoint_count,
    MAX(IFF(event_name = 'run_checkpoint', payload:checkpoint_number::NUMBER, NULL))
      AS highest_checkpoint_number,
    COUNT_IF(event_name = 'upgrade_options_shown') AS upgrade_shown_count,
    COUNT_IF(event_name = 'upgrade_selected') AS upgrade_selected_count,
    GREATEST(
      COUNT_IF(event_name = 'upgrade_options_shown')
        - COUNT_IF(event_name = 'upgrade_selected'),
      0
    ) AS unselected_upgrade_count,

    -- Run마다 반복 저장된 Silver 품질 metadata는 한 번만 남긴다.
    MAX(input_event_count) AS input_event_count,
    MAX(unique_event_count) AS unique_event_count,
    MAX(exact_retry_count) AS exact_retry_count,
    MAX(conflicting_duplicate_count) AS conflicting_duplicate_count,
    MAX(COALESCE(ARRAY_SIZE(TRY_PARSE_JSON(quality_issues_json)), 0))
      AS quality_issue_count
  FROM PARSED_EVENTS
  GROUP BY run_id
)
SELECT *
FROM SUMMARIZED_RUNS;

-- 운영 분석에 테스트 데이터가 섞이지 않도록 동의한 실제 플레이 Run만 분리한다.
CREATE OR REPLACE VIEW PRODUCT_RUN_SUMMARY AS
SELECT *
FROM RUN_SUMMARY
WHERE source_type = 'CONSENTED_PROD_PLAY';

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
    'run_summary_consistency',
    COUNT(*)
  FROM RUN_SUMMARY
  WHERE (is_ended AND run_status <> 'valid')
     OR (NOT is_ended AND run_status <> 'incomplete')
     OR (is_ended AND (
       end_reason IS NULL
       OR run_duration_seconds IS NULL
       OR final_level IS NULL
       OR total_kills IS NULL
       OR current_gold IS NULL
     ))
     OR upgrade_selected_count > upgrade_shown_count
     OR input_event_count
       <> unique_event_count + exact_retry_count + conflicting_duplicate_count

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
