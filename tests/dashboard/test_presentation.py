# 영문 Gold 스키마는 유지하면서 대시보드 표시만 한국어로 바뀌는지 검증한다.

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).parents[2] / "dashboard" / "presentation.py"
SPEC = importlib.util.spec_from_file_location("pandok_dashboard_presentation", MODULE_PATH)
presentation = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(presentation)


def test_localizes_columns_and_known_values_without_mutating_source():
    source = [
        {
            "end_reason": "player_death",
            "death_cause": "enemy_damage",
            "analysis_status": "INSUFFICIENT_SAMPLE",
            "run_count": "3",
        }
    ]

    result = presentation.localize_rows(source)

    assert result == [
        {
            "종료 사유": "플레이어 사망",
            "사망 원인": "적 공격",
            "분석 상태": "표본 부족",
            "Run 수": "3",
        }
    ]
    assert source[0]["end_reason"] == "player_death"


def test_preserves_unknown_columns_and_values():
    assert presentation.localize_rows([{"new_metric": "new_value"}]) == [
        {"new_metric": "new_value"}
    ]


def test_distinguishes_death_cause_collection_states():
    rows = [
        {"death_cause": "not_collected_legacy"},
        {"death_cause": "unknown"},
        {"death_cause": "not_applicable"},
    ]

    assert presentation.localize_rows(rows) == [
        {"사망 원인": "미수집(이전 계약)"},
        {"사망 원인": "분류 불가"},
        {"사망 원인": "해당 없음"},
    ]
