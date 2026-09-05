-- Snowflake와 Athena가 같은 Gold Iceberg 핵심 건수를 읽는지 작은 결과로 대조한다.
-- 상세 행 전체를 Airflow XCom으로 옮기지 않아 데이터 증가 시에도 전달량을 제한한다.

SELECT
  CONCAT('run_quality:', run_status) AS dataset_key,
  COUNT(*) AS row_count,
  COALESCE(SUM(run_count), 0) AS metric_1_count,
  COALESCE(SUM(input_event_count), 0) AS metric_2_count,
  COALESCE(SUM(unique_event_count), 0) AS metric_3_count,
  COALESCE(SUM(exact_retry_count), 0) AS metric_4_count,
  COALESCE(SUM(conflicting_duplicate_count), 0) AS metric_5_count
FROM __TABLE_PREFIX__gold_run_quality
GROUP BY run_status

UNION ALL

SELECT
  'run_progression' AS dataset_key,
  COUNT(*) AS row_count,
  COALESCE(SUM(started_run_count), 0) AS metric_1_count,
  COALESCE(SUM(reached_run_count), 0) AS metric_2_count,
  COALESCE(SUM(previous_reached_run_count), 0) AS metric_3_count,
  COUNT_IF(reached_run_count < previous_reached_run_count) AS metric_4_count,
  COUNT_IF(step_dropoff_percentage > 0) AS metric_5_count
FROM __TABLE_PREFIX__gold_run_progression

UNION ALL

SELECT
  'upgrade_post_selection' AS dataset_key,
  COUNT(*) AS row_count,
  COALESCE(SUM(selection_count), 0) AS metric_1_count,
  COALESCE(SUM(selected_run_count), 0) AS metric_2_count,
  COALESCE(SUM(outcome_observed_run_count), 0) AS metric_3_count,
  COALESCE(SUM(death_within_60_seconds_count), 0) AS metric_4_count,
  COUNT_IF(analysis_status = 'INSUFFICIENT_SAMPLE') AS metric_5_count
FROM __TABLE_PREFIX__gold_upgrade_post_selection;
