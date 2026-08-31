from __future__ import annotations

from copy import deepcopy

from pandok_contracts.errors import ReasonCode
from pandok_contracts.validator import validate_sequence


# 정상 P0 Run 전체가 오류 없이 통과하는지 확인한다.
def test_complete_p0_sequence_is_valid(valid_sequence):
    assert validate_sequence(valid_sequence) == []


# 네트워크 도착 순서가 뒤바뀌어도 이벤트 시각 기준 검증이 유지되는지 확인한다.
def test_arrival_order_does_not_change_event_time_validation(valid_sequence):
    assert validate_sequence(list(reversed(valid_sequence))) == []


# 선택 결과가 앞서 노출된 선택지 중 하나인지 확인한다.
def test_selected_item_must_be_one_of_shown_options(valid_sequence):
    events = deepcopy(valid_sequence)
    selected = next(
        event
        for event in events
        if event["event_name"] == "upgrade_selected"
        and event["choice_source"] == "statue"
    )
    selected["selected_item_id"] = "blood_scent"
    issues = validate_sequence(events)
    assert any(issue.code == ReasonCode.CHOICE_MISMATCH for issue in issues)


# Run의 누적 카운터가 이전 값보다 감소하면 거부하는지 확인한다.
def test_cumulative_counter_must_not_decrease(valid_sequence):
    events = deepcopy(valid_sequence)
    events[-1]["total_kills"] = 10
    issues = validate_sequence(events)
    assert any(issue.code == ReasonCode.COUNTER_DECREASED for issue in issues)


# 같은 event_id와 동일 Payload를 가진 재시도는 허용하는지 확인한다.
def test_identical_retry_is_allowed(valid_sequence):
    events = deepcopy(valid_sequence)
    events.append(deepcopy(events[-2]))
    assert validate_sequence(events) == []


# 같은 event_id의 Payload가 달라지면 충돌로 처리하는지 확인한다.
def test_same_event_id_with_different_payload_is_conflict(valid_sequence):
    events = deepcopy(valid_sequence)
    conflict = deepcopy(events[-2])
    conflict["total_kills"] += 1
    events.append(conflict)
    issues = validate_sequence(events)
    assert any(issue.code == ReasonCode.DUPLICATE_CONFLICT for issue in issues)


# 같은 event_id의 source_type이 달라지면 서로 다른 출처의 충돌로 처리하는지 확인한다.
def test_same_event_id_with_different_source_type_is_conflict(valid_sequence):
    events = deepcopy(valid_sequence)
    conflict = deepcopy(events[-2])
    conflict["source_type"] = "LOAD_TEST"
    events.append(conflict)

    issues = validate_sequence(events)

    assert any(issue.code == ReasonCode.DUPLICATE_CONFLICT for issue in issues)


# 하나의 Run에 속한 모든 이벤트의 source_type이 같은지 확인한다.
def test_source_type_must_match_within_run(valid_sequence):
    # 원본 Fixture를 보존하면서 Checkpoint의 출처만 LOAD_TEST로 변경한다.
    events = deepcopy(valid_sequence)
    events[-2]["source_type"] = "LOAD_TEST"

    issues = validate_sequence(events)

    # Run 시작과 출처가 다르면 source_type 상관관계 오류가 발생해야 한다.
    assert any(
        issue.code == ReasonCode.CORRELATION_MISMATCH
        and issue.path == ("source_type",)
        for issue in issues
    )


# 첫 Checkpoint 전에 종료된 짧은 Run도 허용하는지 확인한다.
def test_run_can_end_before_first_checkpoint(valid_sequence):
    events = deepcopy(valid_sequence)
    session = next(event for event in events if event["event_name"] == "session_started")
    start = next(event for event in events if event["event_name"] == "run_started")
    ended = next(event for event in events if event["event_name"] == "run_ended")
    ended["event_time"] = "2026-09-01T12:30:40Z"
    ended["run_duration_seconds"] = 30
    assert validate_sequence([session, start, ended]) == []


# run_started가 없는 Run 시퀀스를 거부하는지 확인한다.
def test_missing_run_start_is_rejected(valid_sequence):
    issues = validate_sequence([valid_sequence[-1]])
    assert any(issue.code == ReasonCode.MISSING_RUN_START for issue in issues)


# Checkpoint가 번호에 맞는 60초 경계에서 발생하는지 확인한다.
def test_checkpoint_occurs_on_its_sixty_second_boundary(valid_sequence):
    events = deepcopy(valid_sequence)
    events[-2]["run_elapsed_seconds"] = 75
    issues = validate_sequence(events)
    assert any(issue.code == ReasonCode.EVENT_ORDER_INVALID for issue in issues)


# Checkpoint 번호가 반드시 증가하는지 확인한다.
def test_checkpoint_number_must_strictly_increase(valid_sequence):
    events = deepcopy(valid_sequence)
    checkpoint = deepcopy(
        next(event for event in events if event["event_name"] == "run_checkpoint")
    )
    checkpoint["event_id"] = "00000000-0000-4000-8000-000000000011"
    checkpoint["event_time"] = "2026-09-01T12:31:45Z"
    events.insert(-1, checkpoint)
    issues = validate_sequence(events)
    assert any(issue.code == ReasonCode.COUNTER_DECREASED for issue in issues)


# 선택지 노출 순번이 반드시 증가하는지 확인한다.
def test_choice_sequence_must_increase(valid_sequence):
    events = deepcopy(valid_sequence)
    shown = deepcopy(
        next(
            event
            for event in events
            if event["event_name"] == "upgrade_options_shown"
            and event["choice_source"] == "statue"
        )
    )
    selected = deepcopy(
        next(
            event
            for event in events
            if event["event_name"] == "upgrade_selected"
            and event["choice_source"] == "statue"
        )
    )
    shown["event_id"] = "00000000-0000-4000-8000-000000000009"
    shown["choice_id"] = "40000000-0000-4000-8000-000000000003"
    shown["event_time"] = "2026-09-01T12:31:20Z"
    shown["choice_sequence"] = 2
    selected["event_id"] = "00000000-0000-4000-8000-000000000010"
    selected["choice_id"] = shown["choice_id"]
    selected["event_time"] = "2026-09-01T12:31:21Z"
    selected["choice_sequence"] = 2
    events[-1:-1] = [shown, selected]
    issues = validate_sequence(events)
    assert any(issue.code == ReasonCode.COUNTER_DECREASED for issue in issues)


# 선택 결과의 출처가 노출 이벤트의 선택지 출처와 같은지 확인한다.
def test_selected_choice_source_must_match_shown_source(valid_sequence):
    events = deepcopy(valid_sequence)
    selected = next(
        event
        for event in events
        if event["event_name"] == "upgrade_selected"
        and event["choice_source"] == "statue"
    )
    selected["choice_source"] = "level_up_upgrade"
    issues = validate_sequence(events)
    assert any(issue.code == ReasonCode.CHOICE_MISMATCH for issue in issues)


# 같은 시각의 노출·선택 이벤트가 도착 순서와 무관하게 연결되는지 확인한다.
def test_same_time_choice_link_is_independent_of_arrival_order(valid_sequence):
    events = deepcopy(valid_sequence)
    shown = next(
        event
        for event in events
        if event["event_name"] == "upgrade_options_shown"
        and event["choice_source"] == "statue"
    )
    selected = next(
        event
        for event in events
        if event["event_name"] == "upgrade_selected"
        and event["choice_source"] == "statue"
    )
    selected["event_time"] = shown["event_time"]
    events.remove(selected)
    events.insert(events.index(shown), selected)
    assert validate_sequence(events) == []


# 선택 이벤트가 선택지 노출 시각보다 먼저 발생하면 거부하는지 확인한다.
def test_selection_cannot_occur_before_its_shown_choice(valid_sequence):
    events = deepcopy(valid_sequence)
    selected = next(
        event
        for event in events
        if event["event_name"] == "upgrade_selected"
        and event["choice_source"] == "statue"
    )
    selected["event_time"] = "2026-09-01T12:31:09Z"
    issues = validate_sequence(events)
    assert any(issue.code == ReasonCode.EVENT_ORDER_INVALID for issue in issues)


# 하나의 choice_id가 서로 다른 선택지 노출을 가리키지 못하게 하는지 확인한다.
def test_choice_id_cannot_identify_different_shown_choices(valid_sequence):
    events = deepcopy(valid_sequence)
    shown = deepcopy(
        next(
            event
            for event in events
            if event["event_name"] == "upgrade_options_shown"
            and event["choice_source"] == "statue"
        )
    )
    shown["event_id"] = "00000000-0000-4000-8000-000000000015"
    shown["event_time"] = "2026-09-01T12:31:20Z"
    shown["options"][0]["rarity"] = "legendary"
    events.insert(-1, shown)
    issues = validate_sequence(events)
    assert any(issue.code == ReasonCode.CHOICE_MISMATCH for issue in issues)


# 시작 무기 선택은 경과 시간 0일 때 run_started보다 먼저 올 수 있는지 확인한다.
def test_initial_weapon_choice_may_precede_run_started(valid_sequence):
    events = deepcopy(valid_sequence)
    start_time = next(
        event["event_time"] for event in events if event["event_name"] == "run_started"
    )
    initial_choices = [
        event for event in events if event.get("choice_source") == "level_up_weapon"
    ]
    assert len(initial_choices) == 2
    assert all(event["event_time"] < start_time for event in initial_choices)
    assert all(event["run_elapsed_seconds"] == 0 for event in initial_choices)
    assert validate_sequence(events) == []


# 시작 무기 선택 외의 Run 이벤트가 run_started보다 앞서면 거부하는지 확인한다.
def test_non_initial_event_must_not_precede_run_started(valid_sequence):
    events = deepcopy(valid_sequence)
    checkpoint = next(
        event for event in events if event["event_name"] == "run_checkpoint"
    )
    checkpoint["event_time"] = "2026-09-01T12:30:07Z"
    issues = validate_sequence(events)
    assert any(issue.code == ReasonCode.EVENT_ORDER_INVALID for issue in issues)
