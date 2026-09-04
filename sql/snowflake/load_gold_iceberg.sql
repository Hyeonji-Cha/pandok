-- Snowflake Gold View를 Glue Catalog 기반 S3 Iceberg 테이블로 전체 갱신한다.
-- 재실행할 때 기존 집계가 누적되지 않고 Athena가 같은 결과를 읽게 하기 위해 필요하다.

USE ROLE PANDOK_ENGINEER;
USE WAREHOUSE PANDOK_WH;
USE DATABASE PANDOK_LAKEHOUSE;
USE SCHEMA pandok_dev;

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
