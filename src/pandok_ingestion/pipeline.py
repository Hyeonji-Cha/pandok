from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, cast

from pandok_contracts import ValidationIssue, validate_event

from .bronze import build_bronze_record


class EventContractError(ValueError):
    """Represent an event rejected by the telemetry contract."""

    def __init__(self, issues: Sequence[ValidationIssue]) -> None:
        self.issues = tuple(issues)
        message = "; ".join(
            f"{issue.code.value}: {issue.message}"
            for issue in self.issues
        )
        super().__init__(message)


def prepare_bronze_record(
    event: Any,
    ingestion_channel: str,
    *,
    received_at: datetime | None = None,
) -> dict[str, Any]:
    """Validate an event before building its Bronze record."""
    issues = validate_event(event)

    if issues:
        raise EventContractError(issues)

    validated_event = cast(Mapping[str, Any], event)

    return build_bronze_record(
        validated_event,
        ingestion_channel,
        received_at=received_at,
    )