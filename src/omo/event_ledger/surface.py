"""EventLedgerSurface — small, stable surface API for the causal Event Ledger.

Resolves a database path with explicit ``db_path``, ``OMO_EVENT_LEDGER_DB``
environment variable, or the workspace default
``workspace/runtime/omo/event-ledger.sqlite3``.  All persistence delegates to
:class:`LedgerBroker` — no second SQLite connection or business logic lives
here.

Usage::

    from omo.event_ledger.surface import EventLedgerSurface

    surface = EventLedgerSurface()
    surface.append(payload={"key": "value"}, producer="test", ...)
    surface.read()
    surface.verify()
    surface.status()
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

from omo.event_ledger.broker import (
    DEFAULT_PRIVACY_CLASS,
    DEFAULT_SCHEMA_VERSION,
    LedgerBroker,
)


def _workspace_root() -> Path:
    return Path(os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace")))


def _default_db_path() -> Path:
    return (_workspace_root() / "runtime" / "omo" / "event-ledger.sqlite3").resolve()


def _resolve_db_path(explicit: Path | str | None = None) -> Path:
    if explicit is not None:
        return Path(explicit).resolve()
    env = os.environ.get("OMO_EVENT_LEDGER_DB")
    if env:
        return Path(env).resolve()
    return _default_db_path()


@dataclass
class AppendResult:
    sequence: int
    event_id: str
    db_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "event_id": self.event_id,
            "db_path": self.db_path,
        }


@dataclass
class ReadResult:
    events: list[dict[str, Any]]
    count: int
    db_path: str

    def to_dict(self) -> dict[str, Any]:
        return {"events": self.events, "count": self.count, "db_path": self.db_path}


@dataclass
class VerifyResult:
    ok: bool
    total: int
    first_bad_sequence: int | None
    error: str | None
    db_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "total": self.total,
            "first_bad_sequence": self.first_bad_sequence,
            "error": self.error,
            "db_path": self.db_path,
        }


@dataclass
class StatusResult:
    count: int
    last_sequence: int
    db_path: str
    journal_mode: str
    wal_enabled: bool
    sqlite_version: str
    schema_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "last_sequence": self.last_sequence,
            "db_path": self.db_path,
            "journal_mode": self.journal_mode,
            "wal_enabled": self.wal_enabled,
            "sqlite_version": self.sqlite_version,
            "schema_version": self.schema_version,
        }


class AgoraValidationError(ValueError):
    """Typed validation error from envelope parsing or field validation.

    Carries a ``reason`` string for stable dispatch and a ``message`` for
    human-readable details.  No sys.exit here — the CLI maps this to the
    appropriate receipt/output channel.
    """

    def __init__(self, reason: str, message: str = "") -> None:
        super().__init__(f"{reason}: {message}" if message else reason)
        self.reason = reason
        self.message = message or reason


class EventLedgerSurface:
    """Thin surface over :class:`LedgerBroker`.

    Resolves the database path once at construction time.  ``close()`` /
    the context manager interface clean up the underlying broker.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._resolved_path = _resolve_db_path(db_path)
        self._broker: LedgerBroker | None = None

    @property
    def db_path(self) -> Path:
        return self._resolved_path

    @property
    def broker(self) -> LedgerBroker:
        if self._broker is None:
            self._broker = LedgerBroker.connect(self._resolved_path)
        return self._broker

    def close(self) -> None:
        if self._broker is not None:
            self._broker.close()
            self._broker = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def append(
        self,
        *,
        event_type: str = "GovernanceEvent.v1",
        producer: str = "omo-ledger-cli",
        principal_id: str = "omo-governance",
        space_id: str = "default",
        correlation_id: str | None = None,
        idempotency_key: str | None = None,
        payload: dict[str, Any] | None = None,
        episode_id: str | None = None,
        role_context_id: str | None = None,
        responsibility_id: str | None = None,
        mandate_id: str | None = None,
        causation_id: str | None = None,
        occurred_at: str | None = None,
        privacy_class: str = DEFAULT_PRIVACY_CLASS,
        schema_version: str = DEFAULT_SCHEMA_VERSION,
        evidence_uri: str | None = None,
        event_id: str | None = None,
    ) -> AppendResult:
        """Append one event through the broker; returns a typed receipt."""
        from uuid import uuid4

        broker = self.broker
        cid = correlation_id or f"corr_{uuid4().hex[:12]}"
        ik = idempotency_key or f"ik_{uuid4().hex[:12]}"

        sequence = broker.append(
            event_type=event_type,
            producer=producer,
            principal_id=principal_id,
            space_id=space_id,
            correlation_id=cid,
            idempotency_key=ik,
            payload=payload or {},
            episode_id=episode_id,
            role_context_id=role_context_id,
            responsibility_id=responsibility_id,
            mandate_id=mandate_id,
            causation_id=causation_id,
            occurred_at=occurred_at,
            privacy_class=privacy_class,
            schema_version=schema_version,
            evidence_uri=evidence_uri,
            event_id=event_id,
        )
        return AppendResult(
            sequence=sequence,
            event_id=broker.read(from_sequence=sequence, to_sequence=sequence)[0][
                "event_id"
            ],
            db_path=str(self._resolved_path),
        )

    def read(
        self,
        from_sequence: int = 1,
        to_sequence: int | None = None,
        limit: int | None = None,
        event_type: str | None = None,
        producer: str | None = None,
        episode_id: str | None = None,
    ) -> ReadResult:
        events = self.broker.read(
            from_sequence=from_sequence,
            to_sequence=to_sequence,
            limit=limit,
            event_type=event_type,
            producer=producer,
            episode_id=episode_id,
        )
        return ReadResult(
            events=events, count=len(events), db_path=str(self._resolved_path)
        )

    def verify(
        self, from_sequence: int = 1, to_sequence: int | None = None
    ) -> VerifyResult:
        result = self.broker.verify_chain(
            from_sequence=from_sequence, to_sequence=to_sequence
        )
        return VerifyResult(
            ok=result["ok"],
            total=result["total"],
            first_bad_sequence=result["first_bad_sequence"],
            error=result["error"],
            db_path=str(self._resolved_path),
        )

    def status(self) -> StatusResult:
        broker = self.broker
        return StatusResult(
            count=broker.count(),
            last_sequence=broker.last_sequence(),
            db_path=str(self._resolved_path),
            journal_mode=broker.journal_mode(),
            wal_enabled=broker.wal_enabled,
            sqlite_version=broker.sqlite_version(),
            schema_version=broker.schema_version(),
        )


# ----------------------------------------------------------------
# Agora stdio envelope parsing (pure data layer — no sys.exit)
# ----------------------------------------------------------------
#
# Real contract (StdioAdapter._build_stdio_request):
#   {"args": <tuple serialized as JSON array>, "kwargs": <dict>}
#
# resolve_bos_uri can pass kwargs as {"arguments": {...}} (dict or JSON string).


def _unwrap_arguments(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Unwrap ``kwargs.arguments`` when it is the sole key (resolve_bos_uri)."""
    if "arguments" not in kwargs:
        return kwargs
    if len(kwargs) > 1:
        raise AgoraValidationError(
            "ambiguous_kwargs", "kwargs has both 'arguments' and other keys"
        )
    inner = kwargs["arguments"]
    if isinstance(inner, dict):
        return dict(inner)
    if isinstance(inner, str):
        try:
            parsed = json.loads(inner)
        except json.JSONDecodeError:
            raise AgoraValidationError(
                "arguments_parse", "kwargs.arguments is not valid JSON"
            ) from None
        if not isinstance(parsed, dict):
            raise AgoraValidationError(
                "arguments_type", "kwargs.arguments must be a JSON object"
            ) from None
        return parsed
    raise AgoraValidationError(
        "arguments_type", "kwargs.arguments must be an object or JSON string"
    ) from None


def parse_agora_stdin() -> tuple[list[Any], dict[str, Any]]:
    """Parse JSON stdin in the real Agora StdioAdapter envelope format.

    The real contract always sends ``{"args": <JSON array>, "kwargs": <dict>}``.
    Returns normalized ``(args_list, kwargs_dict)`` on success or raises
    :class:`AgoraValidationError` with a stable ``reason`` on failure.

    If stdin is empty / tty, returns ``([], {})``.
    """
    if sys.stdin.isatty():
        return [], {}
    raw = sys.stdin.read().strip()
    if not raw:
        return [], {}
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AgoraValidationError(
            "parse_error", f"invalid stdin JSON: {exc}"
        ) from None

    if not isinstance(envelope, dict):
        raise AgoraValidationError(
            "envelope_type", "stdin JSON must be an object"
        ) from None

    args = envelope.get("args", [])
    kwargs_raw = envelope.get("kwargs", {})

    # Only accept the real contract: args must be a list (JSON array).
    if not isinstance(args, list):
        raise AgoraValidationError("args_type", "args must be a JSON array") from None
    if not isinstance(kwargs_raw, dict):
        raise AgoraValidationError("kwargs_type", "kwargs must be an object") from None

    kwargs = _unwrap_arguments(kwargs_raw)
    return list(args), kwargs


def emit_receipt(result: dict[str, Any]) -> str:
    """Produce a stable JSON receipt string."""
    return json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)


__all__ = [
    "AgoraValidationError",
    "AppendResult",
    "EventLedgerSurface",
    "ReadResult",
    "StatusResult",
    "VerifyResult",
    "_default_db_path",
    "_resolve_db_path",
    "emit_receipt",
    "parse_agora_stdin",
]
