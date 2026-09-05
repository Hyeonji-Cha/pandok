-- Snowflake Gold View를 Glue Catalog 기반 S3 Iceberg 테이블로 전체 갱신한다.
-- 재실행할 때 기존 집계가 누적되지 않고 Athena가 같은 결과를 읽게 하기 위해 필요하다.

USE ROLE PANDOK_ENGINEER;
USE WAREHOUSE PANDOK_WH;
USE DATABASE PANDOK_LAKEHOUSE;
USE SCHEMA pandok_dev;

-- 실제 플레이의 여러 이벤트를 Run당 한 행으로 모은 공통 분석 기반을 보존한다.
CREATE ICEBERG TABLE IF NOT EXISTS gold_run_summary (
  run_id STRING,
  received_date DATE,
  source_type STRING,
  game_version STRING,
  run_status STRING,
  is_started BOOLEAN,
  is_ended BOOLEAN,
  first_received_at TIMESTAMP_LTZ(6),
  last_received_at TIMESTAMP_LTZ(6),
  observed_run_seconds NUMBER(38, 6),
  run_duration_seconds NUMBER(38, 6),
  max_event_sequence NUMBER(38, 0),
  map_id STRING,
  starting_weapon_id STRING,
  starting_max_hp NUMBER(38, 6),
  end_reason STRING,
  final_level NUMBER(38, 0),
  total_kills NUMBER(38, 0),
  total_xp_collected NUMBER(38, 6),
  current_gold NUMBER(38, 6),
  total_gold_collected NUMBER(38, 6),
  hearts_collected NUMBER(38, 0),
  total_healing_received NUMBER(38, 6),
  magnets_collected NUMBER(38, 0),
  miniboss_waves_reached NUMBER(38, 0),
  miniboss_waves_cleared NUMBER(38, 0),
  final_upgrade_count NUMBER(38, 0),
  final_upgrades_json STRING,
  checkpoint_count NUMBER(38, 0),
  highest_checkpoint_number NUMBER(38, 0),
  upgrade_shown_count NUMBER(38, 0),
  upgrade_selected_count NUMBER(38, 0),
  unselected_upgrade_count NUMBER(38, 0),
  input_event_count NUMBER(38, 0),
  unique_event_count NUMBER(38, 0),
  exact_retry_count NUMBER(38, 0),
  conflicting_duplicate_count NUMBER(38, 0),
  quality_issue_count NUMBER(38, 0),
  death_cause STRING
)
  BASE_LOCATION = 'gold/run_summary/'
  TARGET_FILE_SIZE = '16MB'
  ICEBERG_MERGE_ON_READ_BEHAVIOR = 'DISABLED';

-- 이미 생성된 Iceberg 테이블에도 호환 가능한 nullable 필드를 추가한다.
ALTER ICEBERG TABLE gold_run_summary
  ADD COLUMN IF NOT EXISTS death_cause STRING;

DELETE FROM gold_run_summary;

INSERT INTO gold_run_summary
SELECT
  run_id,
  received_date,
  source_type,
  game_version,
  run_status,
  is_started,
  is_ended,
  first_received_at,
  last_received_at,
  observed_run_seconds,
  run_duration_seconds,
  max_event_sequence,
  map_id,
  starting_weapon_id,
  starting_max_hp,
  end_reason,
  final_level,
  total_kills,
  total_xp_collected,
  current_gold,
  total_gold_collected,
  hearts_collected,
  total_healing_received,
  magnets_collected,
  miniboss_waves_reached,
  miniboss_waves_cleared,
  final_upgrade_count,
  final_upgrades_json,
  checkpoint_count,
  highest_checkpoint_number,
  upgrade_shown_count,
  upgrade_selected_count,
  unselected_upgrade_count,
  input_event_count,
  unique_event_count,
  exact_retry_count,
  conflicting_duplicate_count,
  quality_issue_count,
  death_cause
FROM PANDOK.GOLD.PRODUCT_RUN_SUMMARY;

-- 전체 Run의 검증 상태와 중복 품질을 보존한다.
CREATE ICEBERG TABLE IF NOT EXISTS gold_run_quality (
  run_status STRING,
  run_count NUMBER(38, 0),
  input_event_count NUMBER(38, 0),
  unique_event_count NUMBER(38, 0),
  exact_retry_count NUMBER(38, 0),
  conflicting_duplicate_count NUMBER(38, 0)
)
  BASE_LOCATION = 'gold/run_quality/'
  TARGET_FILE_SIZE = '16MB'
  ICEBERG_MERGE_ON_READ_BEHAVIOR = 'DISABLED';

DELETE FROM gold_run_quality;

INSERT INTO gold_run_quality
SELECT
  run_status,
  run_count,
  input_event_count,
  unique_event_count,
  exact_retry_count,
  conflicting_duplicate_count
FROM PANDOK.GOLD.RUN_QUALITY_SUMMARY;

-- 실제 플레이의 종료 사유·비율·평균 지속시간을 보존한다.
CREATE ICEBERG TABLE IF NOT EXISTS gold_run_outcome (
  end_reason STRING,
  ended_run_count NUMBER(38, 0),
  ended_run_percentage NUMBER(38, 2),
  average_run_seconds NUMBER(38, 2)
)
  BASE_LOCATION = 'gold/run_outcome/'
  TARGET_FILE_SIZE = '16MB'
  ICEBERG_MERGE_ON_READ_BEHAVIOR = 'DISABLED';

DELETE FROM gold_run_outcome;

INSERT INTO gold_run_outcome
SELECT
  end_reason,
  ended_run_count,
  ended_run_percentage,
  average_run_seconds
FROM PANDOK.GOLD.PRODUCT_RUN_OUTCOME;

-- 실제 플레이의 체크포인트별 성장·생존 평균을 보존한다.
CREATE ICEBERG TABLE IF NOT EXISTS gold_checkpoint_metrics (
  checkpoint_number NUMBER(38, 0),
  checkpoint_event_count NUMBER(38, 0),
  average_player_level NUMBER(38, 2),
  average_current_xp NUMBER(38, 2),
  average_xp_to_next_level NUMBER(38, 2),
  average_hp_percent NUMBER(38, 2),
  average_total_kills NUMBER(38, 2),
  average_current_gold NUMBER(38, 2)
)
  BASE_LOCATION = 'gold/checkpoint_metrics/'
  TARGET_FILE_SIZE = '16MB'
  ICEBERG_MERGE_ON_READ_BEHAVIOR = 'DISABLED';

DELETE FROM gold_checkpoint_metrics;

INSERT INTO gold_checkpoint_metrics
SELECT
  checkpoint_number,
  checkpoint_event_count,
  average_player_level,
  average_current_xp,
  average_xp_to_next_level,
  average_hp_percent,
  average_total_kills,
  average_current_gold
FROM PANDOK.GOLD.PRODUCT_CHECKPOINT_METRICS;

-- 버전별 60초 구간 도달률과 이탈률을 보존해 난이도 급증 지점을 비교한다.
CREATE ICEBERG TABLE IF NOT EXISTS gold_run_progression (
  game_version STRING,
  checkpoint_number NUMBER(38, 0),
  elapsed_minutes NUMBER(38, 0),
  started_run_count NUMBER(38, 0),
  reached_run_count NUMBER(38, 0),
  reach_percentage NUMBER(38, 2),
  previous_reached_run_count NUMBER(38, 0),
  step_dropoff_percentage NUMBER(38, 2)
)
  BASE_LOCATION = 'gold/run_progression/'
  TARGET_FILE_SIZE = '16MB'
  ICEBERG_MERGE_ON_READ_BEHAVIOR = 'DISABLED';

DELETE FROM gold_run_progression;

INSERT INTO gold_run_progression
SELECT
  game_version,
  checkpoint_number,
  elapsed_minutes,
  started_run_count,
  reached_run_count,
  reach_percentage,
  previous_reached_run_count,
  step_dropoff_percentage
FROM PANDOK.GOLD.PRODUCT_RUN_PROGRESSION;

-- 선택 직후 성과를 보존해 인기와 실제 생존 결과를 함께 비교한다.
CREATE ICEBERG TABLE IF NOT EXISTS gold_upgrade_post_selection (
  game_version STRING,
  choice_source STRING,
  item_id STRING,
  rarity STRING,
  selection_minute NUMBER(38, 0),
  selection_count NUMBER(38, 0),
  selected_run_count NUMBER(38, 0),
  outcome_observed_run_count NUMBER(38, 0),
  average_seconds_after_selection NUMBER(38, 2),
  death_within_60_seconds_count NUMBER(38, 0),
  death_within_60_seconds_percentage NUMBER(38, 2),
  average_final_level NUMBER(38, 2),
  average_total_kills NUMBER(38, 2),
  analysis_status STRING
)
  BASE_LOCATION = 'gold/upgrade_post_selection/'
  TARGET_FILE_SIZE = '16MB'
  ICEBERG_MERGE_ON_READ_BEHAVIOR = 'DISABLED';

DELETE FROM gold_upgrade_post_selection;

INSERT INTO gold_upgrade_post_selection
SELECT
  game_version,
  choice_source,
  item_id,
  rarity,
  selection_minute,
  selection_count,
  selected_run_count,
  outcome_observed_run_count,
  average_seconds_after_selection,
  death_within_60_seconds_count,
  death_within_60_seconds_percentage,
  average_final_level,
  average_total_kills,
  analysis_status
FROM PANDOK.GOLD.PRODUCT_UPGRADE_POST_SELECTION;

-- 실제 플레이의 업그레이드 노출·선택·선택률을 보존한다.
CREATE ICEBERG TABLE IF NOT EXISTS gold_upgrade_funnel (
  choice_source STRING,
  item_id STRING,
  rarity STRING,
  exposure_count NUMBER(38, 0),
  selection_count NUMBER(38, 0),
  selection_percentage NUMBER(38, 2)
)
  BASE_LOCATION = 'gold/upgrade_funnel/'
  TARGET_FILE_SIZE = '16MB'
  ICEBERG_MERGE_ON_READ_BEHAVIOR = 'DISABLED';

DELETE FROM gold_upgrade_funnel;

INSERT INTO gold_upgrade_funnel
SELECT
  choice_source,
  item_id,
  rarity,
  exposure_count,
  selection_count,
  selection_percentage
FROM PANDOK.GOLD.PRODUCT_UPGRADE_FUNNEL;
