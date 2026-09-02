from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "contract" / "fixtures"


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


# ingestion 테스트에서 실제 v2 Run 이벤트를 공통으로 사용한다.
@pytest.fixture
def anonymous_sequence() -> list[dict[str, Any]]:
    return read_json(
        FIXTURES
        / "v2"
        / "valid"
        / "anonymous_p0_run_sequence.json"
    )
