"""OMO causal Event Ledger — authoritative SQLite append-only substrate.

Implements blueprint §10.2 (Ledger minimal physical model) and §25.2 W1-03:
append-only ``event_log`` with a transactional SHA-256 chain, idempotent
``(producer, idempotency_key)`` dedup, append-only triggers, outbox written
atomically with the append, projection checkpoints, drift-checked schema
migrations, and periodic integrity anchors. All writes are serialized through
:class:`LedgerBroker` — every broker handle on the same database path shares
one process-wide lock, and WAL is gated to blueprint-safe SQLite versions.
"""

from __future__ import annotations

from omo.event_ledger.broker import (
    BUSY_TIMEOUT_MS,
    DEFAULT_OUTBOX_DESTINATION,
    DEFAULT_PRIVACY_CLASS,
    DEFAULT_SCHEMA_VERSION,
    EPISODE_REQUIRED_CLASSES,
    OUTBOX_FAILED,
    OUTBOX_PENDING,
    OUTBOX_SENT,
    DuplicateEventError,
    IntegrityViolationError,
    InvalidPayloadError,
    LedgerBroker,
    LedgerError,
)
from omo.event_ledger.schema import (
    LEDGER_DDL,
    LEDGER_SCHEMA_VERSION,
    LEDGER_TRIGGERS,
    SCHEMA_CHECKSUM,
    LedgerSchemaError,
    apply_schema,
    is_wal_allowed,
    schema_fingerprint,
    table_names,
    verify_schema,
    wal_allowed_for_current,
)
from omo.event_ledger.surface import (
    AgoraValidationError,
    AppendResult,
    EventLedgerSurface,
    ReadResult,
    StatusResult,
    VerifyResult,
    emit_receipt,
    parse_agora_stdin,
)

__all__ = [
    "BUSY_TIMEOUT_MS",
    "DEFAULT_OUTBOX_DESTINATION",
    "DEFAULT_PRIVACY_CLASS",
    "DEFAULT_SCHEMA_VERSION",
    "EPISODE_REQUIRED_CLASSES",
    "LEDGER_DDL",
    "LEDGER_SCHEMA_VERSION",
    "LEDGER_TRIGGERS",
    "OUTBOX_FAILED",
    "OUTBOX_PENDING",
    "OUTBOX_SENT",
    "SCHEMA_CHECKSUM",
    "AgoraValidationError",
    "AppendResult",
    "DuplicateEventError",
    "EventLedgerSurface",
    "IntegrityViolationError",
    "InvalidPayloadError",
    "LedgerBroker",
    "LedgerError",
    "LedgerSchemaError",
    "ReadResult",
    "StatusResult",
    "VerifyResult",
    "apply_schema",
    "emit_receipt",
    "is_wal_allowed",
    "parse_agora_stdin",
    "schema_fingerprint",
    "table_names",
    "verify_schema",
    "wal_allowed_for_current",
]
