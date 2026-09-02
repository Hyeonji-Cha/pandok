# 미리 만든 정상 v2 이벤트 예시를 복사해 실행마다 Run 범위 UUID를 새로 만든다.
# Unity 없이 수집 파이프라인을 반복 검증할 CONTROLLED_SCENARIO 데이터를 만들기 위해 사용한다.
# Bronze 포장은 수집 계층에 맡겨 Türkiye Gateway처럼 원본 이벤트만 공급한다.

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from typing import Any
from uuid import UUID, uuid4

from pandok_contracts import (
    SequenceStatus,
    ValidationIssue,
    validate_anonymous_sequence,
)


# 생성 전후 계약 검증에서 발견된 오류들을 하나의 예외로 전달한다.
# 호출부가 오류 코드 목록을 확인하고 생성 실패 원인을 기록할 수 있게 한다.
class ScenarioGenerationError(ValueError):
    """Represent a controlled scenario that violates the event contract."""

    def __init__(self, issues: Sequence[ValidationIssue]) -> None:
        # 여러 검증 오류를 변경 불가능한 형태로 예외 안에 보관한다.
        self.issues = tuple(issues)

        # 로그에서 오류 코드와 내용을 한 번에 확인할 수 있도록 문자열로 합친다.
        message = "; ".join(
            f"{issue.code.value}: {issue.message}"
            for issue in self.issues
        )
        super().__init__(message)


def generate_anonymous_controlled_sequence(
    template_events: Sequence[Mapping[str, Any]],
    *,
    uuid_factory: Callable[[], UUID] = uuid4,
) -> list[dict[str, Any]]:
    """Create one contract-valid anonymous v2 Run from a template."""
    # 반복 생성 과정에서 원본 fixture가 바뀌지 않도록 깊은 복사한다.
    generated_events = deepcopy(
        [dict(event) for event in template_events]
    )

    template_result = validate_anonymous_sequence(generated_events)
    if template_result.status is not SequenceStatus.VALID:
        raise ScenarioGenerationError(template_result.issues)

    run_id = str(uuid_factory())
    event_ids: dict[str, str] = {}
    choice_ids: dict[str, str] = {}

    # 원본 ID를 새 ID에 대응시켜 동일 논리 이벤트의 retry와 선택 연결을 보존한다.
    for event in generated_events:
        original_event_id = str(event["event_id"])
        if original_event_id not in event_ids:
            event_ids[original_event_id] = str(uuid_factory())
        event["event_id"] = event_ids[original_event_id]
        event["run_id"] = run_id
        event["source_type"] = "CONTROLLED_SCENARIO"

        original_choice_id = event.get("choice_id")
        if isinstance(original_choice_id, str):
            if original_choice_id not in choice_ids:
                choice_ids[original_choice_id] = str(uuid_factory())
            event["choice_id"] = choice_ids[original_choice_id]

    generated_result = validate_anonymous_sequence(generated_events)
    if generated_result.status is not SequenceStatus.VALID:
        raise ScenarioGenerationError(generated_result.issues)

    return generated_events
