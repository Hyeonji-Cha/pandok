# 제어 시나리오 생성기가 동적 식별자와 시간 관계를 올바르게 만드는지 테스트한다.
# 잘못 연결된 이벤트가 로컬·ECS 생산 단계에서 수집 시스템으로 전송되지 않게 한다.

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

import pytest

from pandok_contracts import (
    ReasonCode,
    SequenceStatus,
    validate_anonymous_sequence,
    validate_sequence,
)
from pandok_producer import (
    ScenarioGenerationError,
    generate_anonymous_controlled_sequence,
    generate_controlled_sequence,
)

from conftest import FIXTURES, read_json


ANONYMOUS_SEQUENCE_PATH = (
    FIXTURES / "v2" / "valid" / "anonymous_p0_run_sequence.json"
)


# 템플릿을 변경하지 않고 새로운 정상 시퀀스를 생성하는지 확인한다.
def test_generate_controlled_sequence_creates_new_valid_run(
    valid_sequence: list[dict[str, Any]],
) -> None:
    original_template = deepcopy(valid_sequence)

    generated = generate_controlled_sequence(
        valid_sequence,
        started_at=datetime(2026, 9, 2, 15, 0, tzinfo=UTC),
    )

    assert validate_sequence(generated) == []
    assert valid_sequence == original_template
    assert generated[0]["event_time"] == "2026-09-02T15:00:00Z"
    assert generated[-1]["event_time"] == "2026-09-02T15:02:10Z"
    assert {event["source_type"] for event in generated} == {
        "CONTROLLED_SCENARIO"
    }
    assert len({event["event_id"] for event in generated}) == len(generated)
    assert {
        event["event_id"] for event in generated
    }.isdisjoint(
        event["event_id"] for event in valid_sequence
    )
    assert len({event["anonymous_user_id"] for event in generated}) == 1
    assert len({event["session_id"] for event in generated}) == 1
    assert generated[0]["run_id"] is None
    assert len(
        {
            event["run_id"]
            for event in generated
            if event["run_id"] is not None
        }
    ) == 1


# shown-selected 쌍의 choice_id는 같고 서로 다른 선택끼리는 다른지 확인한다.
def test_generate_controlled_sequence_preserves_choice_links(
    valid_sequence: list[dict[str, Any]],
) -> None:
    generated = generate_controlled_sequence(valid_sequence)
    choice_ids_by_sequence: dict[int, set[str]] = {}

    for event in generated:
        if "choice_id" not in event:
            continue
        sequence = int(event["choice_sequence"])
        choice_ids_by_sequence.setdefault(sequence, set()).add(
            str(event["choice_id"])
        )

    assert all(
        len(choice_ids) == 1
        for choice_ids in choice_ids_by_sequence.values()
    )
    assert len(
        {
            next(iter(choice_ids))
            for choice_ids in choice_ids_by_sequence.values()
        }
    ) == len(choice_ids_by_sequence)


# 시간대가 없는 시작 시각을 사용하지 못하게 하는지 확인한다.
def test_generate_controlled_sequence_rejects_naive_start_time(
    valid_sequence: list[dict[str, Any]],
) -> None:
    with pytest.raises(ValueError, match="started_at must be timezone-aware"):
        generate_controlled_sequence(
            valid_sequence,
            started_at=datetime(2026, 9, 2, 15, 0),
        )


# v2 생성기가 gameplay 값은 유지하면서 Run 범위의 익명 ID만 새로 만드는지 확인한다.
def test_generate_anonymous_controlled_sequence_creates_new_valid_run() -> None:
    template = read_json(ANONYMOUS_SEQUENCE_PATH)
    original_template = deepcopy(template)

    generated = generate_anonymous_controlled_sequence(template)
    second_generated = generate_anonymous_controlled_sequence(template)
    result = validate_anonymous_sequence(generated)

    assert result.status is SequenceStatus.VALID
    assert template == original_template
    assert len({event["run_id"] for event in generated}) == 1
    assert generated[0]["run_id"] != template[0]["run_id"]
    assert generated[0]["run_id"] != second_generated[0]["run_id"]
    assert len({event["event_id"] for event in generated}) == len(generated)
    assert {
        event["event_id"] for event in generated
    }.isdisjoint(event["event_id"] for event in template)
    assert {event["source_type"] for event in generated} == {
        "CONTROLLED_SCENARIO"
    }
    assert [event["event_sequence"] for event in generated] == [
        event["event_sequence"] for event in template
    ]
    assert [event["run_elapsed_seconds"] for event in generated] == [
        event["run_elapsed_seconds"] for event in template
    ]
    for template_event, generated_event in zip(
        template, generated, strict=True,
    ):
        expected_gameplay = deepcopy(template_event)
        actual_gameplay = deepcopy(generated_event)
        for field in ("event_id", "run_id", "choice_id", "source_type"):
            expected_gameplay.pop(field, None)
            actual_gameplay.pop(field, None)
        assert actual_gameplay == expected_gameplay
    assert all(
        prohibited not in event
        for event in generated
        for prohibited in ("anonymous_user_id", "session_id", "event_time")
    )


# shown-selected 연결에는 같은 새 choice_id를 사용하고 템플릿 ID는 재사용하지 않는다.
def test_generate_anonymous_controlled_sequence_preserves_choice_links() -> None:
    template = read_json(ANONYMOUS_SEQUENCE_PATH)
    generated = generate_anonymous_controlled_sequence(template)
    assert generated[0]["choice_id"] == generated[1]["choice_id"]
    assert generated[0]["choice_id"] != template[0]["choice_id"]


# 네트워크 재시도를 나타내는 동일 이벤트 복제본은 새 논리 이벤트로 바꾸지 않는다.
def test_generate_anonymous_controlled_sequence_preserves_retry_payload() -> None:
    template = read_json(ANONYMOUS_SEQUENCE_PATH)
    template.insert(4, deepcopy(template[3]))
    generated = generate_anonymous_controlled_sequence(template)
    assert generated[3] == generated[4]
    assert generated[3]["event_id"] == generated[4]["event_id"]
    assert generated[3]["event_sequence"] == generated[4]["event_sequence"]


@pytest.mark.parametrize(
    ("change", "reason_code"),
    (
        ("privacy_field", ReasonCode.PROHIBITED_FIELD),
        ("missing_run_end", ReasonCode.MISSING_RUN_END),
    ),
)
def test_generate_anonymous_controlled_sequence_rejects_invalid_template(
    change: str,
    reason_code: ReasonCode,
) -> None:
    template = read_json(ANONYMOUS_SEQUENCE_PATH)
    if change == "privacy_field":
        template[0]["session_id"] = "prohibited"
    else:
        template.pop()

    with pytest.raises(ScenarioGenerationError) as error:
        generate_anonymous_controlled_sequence(template)

    assert reason_code in {issue.code for issue in error.value.issues}
