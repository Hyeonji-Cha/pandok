# Athena Gold Iceberg만 조회하는 대시보드 SQL을 관리한다.
# 버전 필터는 허용된 형식만 SQL에 넣어 임의 쿼리 삽입을 막는다.

from __future__ import annotations

import re


_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9._+-]{1,32}$")


def _version_condition(game_version: str | None, *, alias: str = "") -> str:
    if game_version is None:
        return "1 = 1"
    if not _VERSION_PATTERN.fullmatch(game_version):
        raise ValueError("game_version 형식이 올바르지 않습니다.")
    column = f"{alias}.game_version" if alias else "game_version"
    return f"{column} = '{game_version}'"


def build_dashboard_queries(game_version: str | None = None) -> dict[str, str]:
    version_filter = _version_condition(game_version)
    return {
        "run_overview": f"""
            SELECT
              COUNT(*) AS total_run_count,
              COUNT_IF(is_started) AS started_run_count,
              COUNT_IF(is_ended) AS ended_run_count,
              COUNT_IF(NOT is_ended) AS incomplete_run_count
            FROM gold_run_summary
            WHERE {version_filter}
        """,
        "run_endings": f"""
            SELECT
              COALESCE(end_reason, 'incomplete') AS end_reason,
              COALESCE(death_cause, 'not_applicable_or_unknown') AS death_cause,
              COUNT(*) AS run_count,
              ROUND(AVG(run_duration_seconds), 2) AS average_run_seconds
            FROM gold_run_summary
            WHERE {version_filter}
            GROUP BY end_reason, death_cause
            ORDER BY run_count DESC, end_reason, death_cause
        """,
        "run_progression": f"""
            SELECT game_version, checkpoint_number, elapsed_minutes,
                   started_run_count, reached_run_count,
                   reach_percentage, step_dropoff_percentage
            FROM gold_run_progression
            WHERE {version_filter}
            ORDER BY game_version, checkpoint_number
        """,
        "item_performance": f"""
            SELECT game_version, choice_source, item_id, display_name,
                   item_category, intended_effect, primary_metric,
                   selection_count, selected_run_count,
                   outcome_observed_run_count, average_seconds_after_selection,
                   death_within_60_seconds_percentage,
                   average_final_level, average_total_kills, analysis_status
            FROM gold_item_performance_summary
            WHERE {version_filter}
            ORDER BY outcome_observed_run_count DESC, display_name
        """,
        "run_quality": """
            SELECT run_status, run_count, input_event_count, unique_event_count,
                   exact_retry_count, conflicting_duplicate_count
            FROM gold_run_quality
            ORDER BY run_count DESC, run_status
        """,
    }


VERSIONS_QUERY = """
    SELECT DISTINCT game_version
    FROM gold_run_summary
    WHERE game_version IS NOT NULL
    ORDER BY game_version
"""
