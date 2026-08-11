"""Typed storage DTOs; no database implementation details live here."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime


class StorageError(RuntimeError):
    """Safe storage error that never embeds database contents."""


class UnsupportedSchemaError(StorageError):
    """The database was created by a newer incompatible runtime."""


class StorageDegradedError(StorageError):
    """The store cannot accept writes and is restricted to diagnostics."""


class ConfigRevisionConflictError(StorageError):
    """A revision ID was reused with different immutable content."""


class EventConflictError(StorageError):
    """A durable event ID was reused with different immutable content."""


@dataclass(frozen=True, slots=True)
class HealthRecord:
    resource_kind: str
    resource_id: str
    state: str
    observed_at: datetime
    observed_monotonic: float
    stale: bool


@dataclass(frozen=True, slots=True)
class MetricRecord:
    request_id: str
    observed_at: datetime
    latency_ms: float
    success: bool


@dataclass(frozen=True, slots=True)
class DailyMetricAggregate:
    day: date
    request_count: int
    error_count: int
    latency_sum_ms: float


@dataclass(frozen=True, slots=True)
class DurableEventRecord:
    sequence: int
    event_id: str
    schema_version: int
    observed_at: datetime
    priority: str
    kind: str
    payload_json: str
    job_id: str | None
    resource_id: str | None


@dataclass(frozen=True, slots=True)
class RouteAuditWrite:
    request_id: str
    observed_at: datetime
    selected_placement_id: str | None
    candidates: tuple[str, ...]
    rejections: Mapping[str, str]
    config_revision: str


@dataclass(frozen=True, slots=True)
class RouteAuditRecord(RouteAuditWrite):
    sequence: int


@dataclass(frozen=True, slots=True)
class ConfigRevisionWrite:
    revision_id: str
    observed_at: datetime
    rollback_reference: str | None
    config_json: str
    fingerprint: str


@dataclass(frozen=True, slots=True)
class ConfigRevisionRecord(ConfigRevisionWrite):
    sequence: int
