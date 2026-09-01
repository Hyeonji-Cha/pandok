from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts" / "aggregate-export-v1.schema.json"
SAMPLE_PATH = ROOT / "examples" / "aggregate-export-v1.synthetic.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def schema() -> dict:
    return load(SCHEMA_PATH)


@pytest.fixture
def sample() -> dict:
    return load(SAMPLE_PATH)


def assert_valid(schema: dict, payload: dict) -> None:
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)


def assert_invalid(schema: dict, payload: dict) -> None:
    errors = list(
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).iter_errors(payload)
    )
    assert errors, "payload unexpectedly passed the aggregate export contract"


def test_synthetic_sample_is_valid(schema: dict, sample: dict) -> None:
    assert_valid(schema, sample)


@pytest.mark.parametrize(
    "forbidden_key",
    [
        "anonymous_user_id",
        "session_id",
        "run_id",
        "event_id",
        "choice_id",
        "steam_id",
        "ip_address",
        "event_time",
    ],
)
def test_identity_or_linkage_field_is_rejected(
    schema: dict,
    sample: dict,
    forbidden_key: str,
) -> None:
    payload = copy.deepcopy(sample)
    payload[forbidden_key] = "forbidden"
    assert_invalid(schema, payload)


def test_session_started_is_not_exportable(schema: dict, sample: dict) -> None:
    payload = copy.deepcopy(sample)
    payload["metrics"]["event_counts"].append(
        {"event_name": "session_started", "count": 1}
    )
    assert_invalid(schema, payload)


def test_unknown_field_is_rejected(schema: dict, sample: dict) -> None:
    payload = copy.deepcopy(sample)
    payload["metrics"]["run_end_counts"][0]["unexpected"] = 1
    assert_invalid(schema, payload)


def test_invalid_end_reason_is_rejected(schema: dict, sample: dict) -> None:
    payload = copy.deepcopy(sample)
    payload["metrics"]["run_end_counts"][0]["end_reason"] = "rage_quit"
    assert_invalid(schema, payload)


def test_negative_count_is_rejected(schema: dict, sample: dict) -> None:
    payload = copy.deepcopy(sample)
    payload["metrics"]["event_counts"][0]["count"] = -1
    assert_invalid(schema, payload)


def test_prod_class_is_contract_valid_but_not_activated_by_test(
    schema: dict,
    sample: dict,
) -> None:
    payload = copy.deepcopy(sample)
    payload["data_class"] = "PRIVACY_RELEASED_PROD_AGGREGATE"
    # Contract validity is not production authorization.
    # Production activation is a separate operational/privacy release gate.
    assert_valid(schema, payload)
