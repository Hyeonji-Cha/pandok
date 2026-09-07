-- 검증된 PANDOK Gold를 개발자의 자연어 질문에 연결하는 Snowflake 의미 계층이다.
-- 원본 이벤트와 식별자를 노출하지 않고 Run·무기·옵션·킬·생존 질문만 지원한다.

USE ROLE PANDOK_ENGINEER;
USE WAREHOUSE PANDOK_WH;
USE DATABASE PANDOK;
USE SCHEMA GOLD;

CREATE OR REPLACE SEMANTIC VIEW PANDOK_GAME_ANALYTICS
  TABLES (
    runs AS PANDOK.GOLD.PRODUCT_RUN_SUMMARY
      PRIMARY KEY (run_id)
      WITH SYNONYMS ('runs', 'play attempts', '플레이 시도', '런')
      COMMENT = 'One anonymous gameplay Run. Use only aggregate metrics and never return run_id.',

    weapon_popularity AS (
      SELECT
        game_version,
        weapon_id,
        display_name,
        starting_run_count AS starting_run_count_value,
        exposure_count AS exposure_count_value,
        selection_count AS selection_count_value,
        first_selected_run_count AS first_selected_run_count_value
      FROM PANDOK.GOLD.PRODUCT_WEAPON_POPULARITY
    )
      PRIMARY KEY (game_version, weapon_id)
      WITH SYNONYMS ('weapon popularity', 'weapon choices', '무기 인기', '무기 선택')
      COMMENT = 'Version and weapon level popularity metrics using actual exposure as the selection-rate denominator.',

    weapon_performance AS (
      SELECT
        game_version,
        weapon_id,
        display_name,
        analysis_status,
        outcome_observed_run_count AS observed_run_count_value,
        average_total_kills AS average_total_kills_value,
        kills_per_minute AS kills_per_minute_value,
        average_run_seconds AS average_run_seconds_value,
        death_percentage AS death_percentage_value
      FROM PANDOK.GOLD.PRODUCT_WEAPON_PERFORMANCE
    )
      PRIMARY KEY (game_version, weapon_id)
      WITH SYNONYMS ('weapon performance', 'weapon kills', '무기 성과', '무기 킬 수')
      COMMENT = 'Descriptive starting-weapon outcomes. These values do not establish causal effects.',

    option_outcomes AS (
      SELECT
        game_version,
        choice_source,
        item_id,
        display_name,
        item_category,
        analysis_status,
        offered_run_count AS offered_run_count_value,
        selected_run_count AS selected_run_count_value,
        not_selected_run_count AS not_selected_run_count_value,
        selected_average_kills AS selected_average_kills_value,
        not_selected_average_kills AS not_selected_average_kills_value,
        average_kill_difference AS average_kill_difference_value,
        average_run_seconds_difference AS average_run_seconds_difference_value
      FROM PANDOK.GOLD.PRODUCT_OPTION_OUTCOME_COMPARISON
    )
      PRIMARY KEY (game_version, choice_source, item_id)
      WITH SYNONYMS ('option outcomes', 'selected versus not selected', '옵션 성과', '선택 비선택 비교')
      COMMENT = 'Compares ended Runs that were offered the same option and then selected or did not select it.'
  )

  FACTS (
    PRIVATE runs.run_seconds AS run_duration_seconds,
    PRIVATE runs.kill_count AS total_kills,
    PRIVATE runs.final_level_value AS final_level,
    PRIVATE runs.total_xp_value AS total_xp_collected,
    PRIVATE runs.total_gold_value AS total_gold_collected,

    PRIVATE weapon_popularity.raw_starting_run_count AS starting_run_count_value,
    PRIVATE weapon_popularity.raw_exposure_count AS exposure_count_value,
    PRIVATE weapon_popularity.raw_selection_count AS selection_count_value,
    PRIVATE weapon_popularity.raw_first_selected_run_count AS first_selected_run_count_value,

    PRIVATE weapon_performance.raw_observed_run_count AS observed_run_count_value,
    PRIVATE weapon_performance.raw_average_total_kills AS average_total_kills_value,
    PRIVATE weapon_performance.raw_kills_per_minute AS kills_per_minute_value,
    PRIVATE weapon_performance.raw_average_run_seconds AS average_run_seconds_value,
    PRIVATE weapon_performance.raw_death_percentage AS death_percentage_value,

    PRIVATE option_outcomes.raw_offered_run_count AS offered_run_count_value,
    PRIVATE option_outcomes.raw_selected_run_count AS selected_run_count_value,
    PRIVATE option_outcomes.raw_not_selected_run_count AS not_selected_run_count_value,
    PRIVATE option_outcomes.raw_selected_average_kills AS selected_average_kills_value,
    PRIVATE option_outcomes.raw_not_selected_average_kills AS not_selected_average_kills_value,
    PRIVATE option_outcomes.raw_average_kill_difference AS average_kill_difference_value,
    PRIVATE option_outcomes.raw_average_run_seconds_difference AS average_run_seconds_difference_value
  )

  DIMENSIONS (
    runs.game_version AS game_version
      WITH SYNONYMS ('version', 'build version', '게임 버전'),
    runs.received_date AS received_date
      WITH SYNONYMS ('date', '수신 날짜'),
    runs.starting_weapon AS starting_weapon_id
      WITH SYNONYMS ('starting weapon', 'initial weapon', '시작 무기'),
    runs.run_status AS run_status
      WITH SYNONYMS ('quality status', 'Run 상태'),
    runs.end_reason AS end_reason
      WITH SYNONYMS ('ending reason', '종료 사유'),
    runs.death_cause AS death_cause
      WITH SYNONYMS ('cause of death', '사망 원인'),

    weapon_popularity.game_version AS game_version,
    weapon_popularity.weapon_id AS weapon_id
      WITH SYNONYMS ('weapon', '무기'),
    weapon_popularity.weapon_name AS display_name
      WITH SYNONYMS ('weapon name', '무기 이름'),

    weapon_performance.game_version AS game_version,
    weapon_performance.weapon_id AS weapon_id
      WITH SYNONYMS ('starting weapon', '시작 무기'),
    weapon_performance.weapon_name AS display_name
      WITH SYNONYMS ('weapon name', '무기 이름'),
    weapon_performance.sample_status AS analysis_status
      WITH SYNONYMS ('sample status', '표본 상태'),

    option_outcomes.game_version AS game_version,
    option_outcomes.choice_source AS choice_source
      WITH SYNONYMS ('option source', '선택 경로'),
    option_outcomes.item_id AS item_id
      WITH SYNONYMS ('option', 'item', '옵션', '아이템'),
    option_outcomes.item_name AS display_name
      WITH SYNONYMS ('option name', '아이템 이름'),
    option_outcomes.item_category AS item_category
      WITH SYNONYMS ('category', '아이템 분류'),
    option_outcomes.sample_status AS analysis_status
      WITH SYNONYMS ('sample status', '표본 상태')
  )

  METRICS (
    runs.run_count AS COUNT(runs.run_id)
      WITH SYNONYMS ('total runs', 'play attempts', '총 Run 수'),
    runs.started_run_count AS COUNT_IF(runs.is_started)
      WITH SYNONYMS ('started runs', '시작 Run 수'),
    runs.ended_run_count AS COUNT_IF(runs.is_ended)
      WITH SYNONYMS ('ended runs', '종료 Run 수'),
    runs.incomplete_run_count AS COUNT_IF(NOT runs.is_ended)
      WITH SYNONYMS ('incomplete runs', '미완료 Run 수'),
    runs.average_kill_count AS AVG(runs.kill_count)
      WITH SYNONYMS ('average score', 'average kills', '평균 점수', '평균 킬 수')
      COMMENT = 'Score means total kill count in PANDOK; it is not a separate game score field.',
    runs.total_kill_count AS SUM(runs.kill_count)
      WITH SYNONYMS ('total score', 'total kills', '총점', '총 킬 수'),
    runs.average_run_seconds AS AVG(runs.run_seconds)
      WITH SYNONYMS ('average survival time', '평균 생존시간', '평균 플레이시간'),
    runs.kills_per_minute AS
      60.0 * SUM(runs.kill_count) / NULLIF(SUM(runs.run_seconds), 0)
      WITH SYNONYMS ('kill rate', 'KPM', '분당 킬 수'),
    runs.death_percentage AS
      100.0 * COUNT_IF(runs.end_reason = 'player_death')
        / NULLIF(COUNT_IF(runs.is_ended), 0)
      WITH SYNONYMS ('death rate', '사망률'),

    weapon_popularity.starting_run_count AS SUM(weapon_popularity.raw_starting_run_count)
      WITH SYNONYMS ('starting weapon count', '시작 무기 횟수'),
    weapon_popularity.exposure_count AS SUM(weapon_popularity.raw_exposure_count)
      WITH SYNONYMS ('times offered', '노출 횟수'),
    weapon_popularity.selection_count AS SUM(weapon_popularity.raw_selection_count)
      WITH SYNONYMS ('times selected', '선택 횟수'),
    weapon_popularity.first_selected_run_count AS
      SUM(weapon_popularity.raw_first_selected_run_count)
      WITH SYNONYMS ('first weapon choices', '최초 선택 횟수'),
    weapon_popularity.exposure_adjusted_selection_percentage AS
      100.0 * SUM(weapon_popularity.raw_selection_count)
        / NULLIF(SUM(weapon_popularity.raw_exposure_count), 0)
      WITH SYNONYMS ('weapon popularity', 'selection rate', '노출 대비 선택률'),

    weapon_performance.observed_run_count AS
      SUM(weapon_performance.raw_observed_run_count)
      WITH SYNONYMS ('observed runs', '관측 Run 수'),
    weapon_performance.average_kill_count AS MAX(weapon_performance.raw_average_total_kills)
      WITH SYNONYMS ('average score', 'average kills', '평균 킬 수'),
    weapon_performance.kills_per_minute AS MAX(weapon_performance.raw_kills_per_minute)
      WITH SYNONYMS ('KPM', '분당 킬 수'),
    weapon_performance.average_survival_seconds AS MAX(weapon_performance.raw_average_run_seconds)
      WITH SYNONYMS ('average survival time', '평균 생존시간'),
    weapon_performance.death_percentage AS MAX(weapon_performance.raw_death_percentage)
      WITH SYNONYMS ('death rate', '사망률'),

    option_outcomes.offered_run_count AS SUM(option_outcomes.raw_offered_run_count)
      WITH SYNONYMS ('offered runs', '제시 Run 수'),
    option_outcomes.selected_run_count AS SUM(option_outcomes.raw_selected_run_count)
      WITH SYNONYMS ('selected runs', '선택 Run 수'),
    option_outcomes.not_selected_run_count AS SUM(option_outcomes.raw_not_selected_run_count)
      WITH SYNONYMS ('not selected runs', '비선택 Run 수'),
    option_outcomes.selected_average_kills AS MAX(option_outcomes.raw_selected_average_kills)
      WITH SYNONYMS ('selected average score', '선택 평균 킬 수'),
    option_outcomes.not_selected_average_kills AS
      MAX(option_outcomes.raw_not_selected_average_kills)
      WITH SYNONYMS ('not selected average score', '비선택 평균 킬 수'),
    option_outcomes.average_kill_difference AS MAX(option_outcomes.raw_average_kill_difference)
      WITH SYNONYMS ('kill difference', 'score difference', '평균 킬 차이'),
    option_outcomes.average_survival_seconds_difference AS
      MAX(option_outcomes.raw_average_run_seconds_difference)
      WITH SYNONYMS ('survival difference', '생존시간 차이')
  )

  COMMENT = 'PANDOK developer analytics for anonymous Run, weapon, option, kill-count, survival, death-cause, and game-version questions.'

  AI_SQL_GENERATION
    'Use only the semantic dimensions and metrics defined here. Score means total kill count, not a separate score field. For weapon popularity, prefer exposure_adjusted_selection_percentage and show exposure_count. For performance, show both average kill count and kills per minute. Always include game version when using weapon_performance or option_outcomes metrics. Treat INSUFFICIENT_SAMPLE as insufficient evidence. Treat DESCRIPTIVE_ONLY as association and never claim causation. Never select or reveal run_id. Limit detailed results to 20 rows.'

  AI_QUESTION_CATEGORIZATION
    'Accept only questions about anonymous Runs, weapons, options, kill counts, survival time, game version, ending reasons, death causes, popularity, and sample status. If a question asks about players, identities, sessions, devices, locations, exact event times, unsupported game fields, predictions, or causal proof, explain that the semantic view does not support it.'
;

-- 생성 결과와 공개된 의미 표현을 사람이 확인하는 읽기 전용 검증 명령이다.
DESCRIBE SEMANTIC VIEW PANDOK.GOLD.PANDOK_GAME_ANALYTICS;
SHOW SEMANTIC METRICS IN PANDOK.GOLD.PANDOK_GAME_ANALYTICS;
SHOW SEMANTIC DIMENSIONS IN PANDOK.GOLD.PANDOK_GAME_ANALYTICS;
