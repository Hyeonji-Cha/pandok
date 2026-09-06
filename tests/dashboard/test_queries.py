# 대시보드 버전 필터가 Gold SQL에 안전하게 반영되는지만 검증한다.

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).parents[2] / "dashboard" / "queries.py"
SPEC = importlib.util.spec_from_file_location("pandok_dashboard_queries", MODULE_PATH)
queries = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(queries)


def test_builds_item_summary_query_with_version_filter():
    result = queries.build_dashboard_queries("0.1.0")

    assert "gold_item_performance_summary" in result["item_performance"]
    assert "game_version = '0.1.0'" in result["item_performance"]
    assert len(result) == 5


def test_rejects_unsafe_game_version():
    with pytest.raises(ValueError, match="game_version"):
        queries.build_dashboard_queries("0.1.0' OR 1=1 --")
