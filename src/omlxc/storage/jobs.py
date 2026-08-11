"""Typed persisted Job values and restart policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from omlxc.domain import JobState, RiskLevel


class JobConflictError(ValueError):
    """An idempotency key or Job ID was reused for a different operation."""


class RunningRecoveryPolicy(StrEnum):
    REQUEUE = "requeue"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class StoredJob:
    id: str
    kind: str
    initiator: str
    risk: RiskLevel
    state: JobState
    progress: float
    created_at: datetime
    updated_at: datetime
    rollback_reference: str | None
    attempt: int
    error_code: str | None
    idempotency_key: str | None
    payload_fingerprint: str
