# 제어 시나리오 생성기가 동적 식별자와 시간 관계를 올바르게 만드는지 테스트한다.
# 잘못 연결된 이벤트가 로컬·ECS 생산 단계에서 수집 시스템으로 전송되지 않게 한다.

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

import pytest

from pandok_contracts import validate_sequence
from pandok_producer import generate_controlled_sequence


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
