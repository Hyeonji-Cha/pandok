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


@pytest.fixture
def valid_sequence() -> list[dict[str, Any]]:
    return read_json(FIXTURES / "valid" / "p0_run_sequence.json")
