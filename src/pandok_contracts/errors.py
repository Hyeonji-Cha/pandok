"""Stable validation errors exposed by the contract library and CLI."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class ReasonCode(StrEnum):
    """Machine-stable failure categories."""

    INVALID_JSON = "invalid_json"
    SCHEMA_INVALID = "schema_invalid"
    PROHIBITED_FIELD = "prohibited_field"
    DUPLICATE_CONFLICT = "duplicate_conflict"
    CORRELATION_MISMATCH = "correlation_mismatch"
    MISSING_RUN_START = "missing_run_start"
    MISSING_RUN_END = "missing_run_end"
    EVENT_SEQUENCE_GAP = "event_sequence_gap"
    EVENT_SEQUENCE_CONFLICT = "event_sequence_conflict"
    EVENT_ORDER_INVALID = "event_order_invalid"
    CHOICE_NOT_FOUND = "choice_not_found"
    CHOICE_MISMATCH = "choice_mismatch"
    COUNTER_DECREASED = "counter_decreased"
    EVENT_ARRIVAL_TOO_LATE = "event_arrival_too_late"


class SequenceStatus(StrEnum):
    """Processing decision for one anonymous Run sequence."""

    VALID = "valid"
    INCOMPLETE = "incomplete"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One actionable contract failure."""

    code: ReasonCode
    message: str
    path: tuple[str | int, ...] = ()
    event_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["code"] = self.code.value
        value["path"] = list(self.path)
        return value


@dataclass(frozen=True, slots=True)
class SequenceValidationResult:
    """Status and evidence produced by anonymous Run validation."""

    status: SequenceStatus
    issues: tuple[ValidationIssue, ...] = ()
