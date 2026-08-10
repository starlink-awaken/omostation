"""Ledger Broker — the single authoritative write path for the SQLite
causal Event Ledger (blueprint §10.2 / §25.2 W1-03).

Design rules enforced here:

- **Single broker, serialized writes** — a process-wide ``threading.RLock``
  keyed by the resolved database path serializes every transaction; agents
  never touch the database directly, and every broker handle on the same DB
  file shares the same lock.
- **Idempotent append** — ``UNIQUE(producer, idempotency_key)`` plus an
  explicit pre-check make duplicate appends a controlled error.
- **Transactional hash chain** — ``event_hash`` is the SHA-256 of a canonical
  JSON encoding of the full row (including ``previous_hash`` and ``sequence``);
  ``previous_hash`` links to the prior row's hash. The whole append commits in
  one SQLite transaction, so the chain is always contiguous and atomic.
- **Episode linkage** — Decision/Mandate/Action/Evidence/Outcome events must
  carry an ``episode_id``; enforced at the broker boundary and by a DB trigger.
- **Outbox atomicity** — every append writes its outbox rows in the same
  transaction; ledger-commit and event-publish cannot diverge.
- **Replay** — ``read()`` returns a deterministic, sequence-ordered slice;
  ``verify_chain(from_sequence=N)`` supports partial-chain verification.
- **Integrity anchors** — created only over a verified chain; periodic
  root-hash checkpoints over event ranges.
- **SQLite version gate** — WAL is enabled only for the blueprint-approved
  patched versions. On an unsafe runtime the broker downgrades a persistent
  WAL database to DELETE (or fails closed) and reports the *actual* journal
  mode; ``force_wal`` is deliberately not part of the public API.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import threading
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self
from uuid import uuid4

from omo.event_ledger.schema import (
    LEDGER_SCHEMA_VERSION,
    LedgerSchemaError,
    apply_schema,
    is_wal_allowed,
)

#: Default event envelope schema version written into ``event_log``.
#: Aligns with the W1-02 ``EventEnvelope`` M2 model (blueprint §11.2 / §11.3):
#: the column carries a CloudEvents-style spec version string so downstream
#: consumers (W1-04 broker API, Cockpit, Agora) can dispatch on the envelope
#: format. This is a mapping note only — the authoritative DDL stays in this
#: package and is NOT copied from ECOS M2 compiler output.
DEFAULT_SCHEMA_VERSION = "event-envelope/v1"
#: Default privacy class when the caller does not declare one.
DEFAULT_PRIVACY_CLASS = "internal"
#: Default outbox destination for a bare append.
DEFAULT_OUTBOX_DESTINATION = "ledger"
#: Blueprint §10.2 mandates busy_timeout >= 5000 ms.
BUSY_TIMEOUT_MS = 5000
#: Outbox states.
OUTBOX_PENDING = "pending"
OUTBOX_SENT = "sent"
OUTBOX_FAILED = "failed"

#: Event classes that MUST carry an ``episode_id`` (blueprint §10.2).
EPISODE_REQUIRED_CLASSES = frozenset(
    {"Decision", "Mandate", "Action", "Evidence", "Outcome"}
)

#: Columns stored in ``event_log`` (order used for canonical hashing).
_EVENT_LOG_COLUMNS = (
    "sequence",
    "event_id",
    "event_type",
    "schema_version",
    "episode_id",
    "principal_id",
    "space_id",
    "role_context_id",
    "responsibility_id",
    "mandate_id",
    "correlation_id",
    "causation_id",
    "producer",
    "idempotency_key",
    "occurred_at",
    "recorded_at",
    "privacy_class",
    "payload_json",
    "evidence_uri",
    "previous_hash",
    "event_hash",
)

#: Process-wide per-path write locks: the "single broker serializes writes"
#: constraint (blueprint §10.2) is enforced by sharing one RLock between every
#: broker instance that resolves to the same database file.
_LOCK_REGISTRY: dict[str, threading.RLock] = {}
_LOCK_REGISTRY_GUARD = threading.Lock()


def _path_key(path: Path | str) -> str:
    return str(Path(path).resolve())


def _broker_lock(path: Path | str) -> threading.RLock:
    """Return the process-wide RLock shared by all brokers for this file."""
    key = _path_key(path)
    with _LOCK_REGISTRY_GUARD:
        lock = _LOCK_REGISTRY.get(key)
        if lock is None:
            lock = threading.RLock()
            _LOCK_REGISTRY[key] = lock
        return lock


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    """Deterministic JSON encoding used for all ledger hashing."""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


class LedgerError(RuntimeError):
    """Base error for the causal event ledger."""


class DuplicateEventError(LedgerError):
    """An event with the same ``(producer, idempotency_key)`` already exists."""


class IntegrityViolationError(LedgerError):
    """Hash chain verification failed."""


class InvalidPayloadError(LedgerError):
    """Event payload is not valid JSON data."""


class LedgerBroker:
    """Serialized, append-only writer and reader for the causal Event Ledger.

    All broker instances that resolve to the same database path share a
    process-wide re-entrant lock, so writes are serialized across handles.
    """

    def __init__(
        self,
        db_path: Path | str,
        *,
        conn: sqlite3.Connection,
        journal_mode: str,
        lock: threading.RLock,
    ) -> None:
        self.db_path = Path(db_path)
        self._conn = conn
        self._journal_mode = journal_mode
        self._lock = lock

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def connect(
        cls,
        db_path: Path | str,
        *,
        busy_timeout_ms: int = BUSY_TIMEOUT_MS,
    ) -> LedgerBroker:
        """Open (creating if needed) a ledger database and apply the schema.

        Journal mode is decided by the SQLite version gate (blueprint §10.2):

        - safe version (>= 3.51.3, or patched 3.44.6+/3.50.7+): enable WAL;
        - unsafe version: a persistent WAL database is downgraded to DELETE,
          and if the downgrade cannot be applied the connect fails closed.

        ``wal_enabled`` always reports the actual ``PRAGMA journal_mode``.
        """
        if busy_timeout_ms < BUSY_TIMEOUT_MS:
            raise LedgerError(
                f"busy_timeout_ms must be >= {BUSY_TIMEOUT_MS}, got {busy_timeout_ms}"
            )
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Acquire the process-wide lock for this resolved path BEFORE any
        # connection work: apply_schema() itself writes to the database, and
        # journal-mode configuration mutates it too. Two brokers concurrently
        # connecting to the same file must not interleave those writes outside
        # the single-writer boundary.
        lock = _broker_lock(path)
        with lock:
            conn: sqlite3.Connection | None = None
            try:
                conn = sqlite3.connect(str(path), check_same_thread=False)
                conn.row_factory = sqlite3.Row
                conn.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
                conn.execute("PRAGMA foreign_keys = ON")

                version_ok = is_wal_allowed(sqlite3.sqlite_version_info)
                journal_mode = cls._configure_journal_mode(conn, allow_wal=version_ok)

                apply_schema(conn)

                return cls(path, conn=conn, journal_mode=journal_mode, lock=lock)
            except BaseException:
                # Explicitly close the connection on any setup failure
                # (journal configuration, schema migration, drift check) so
                # file handles and locks are not leaked.
                if conn is not None:
                    try:
                        conn.close()
                    except sqlite3.Error:
                        pass
                raise

    @staticmethod
    def _configure_journal_mode(conn: sqlite3.Connection, *, allow_wal: bool) -> str:
        """Set/verify journal mode; returns the actual (post-set) mode.

        On an unsafe runtime this downgrades a persistent WAL database to
        DELETE. If the downgrade fails (e.g. the mode cannot be changed),
        the connect fails closed by raising.
        """
        if allow_wal:
            mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        else:
            current = conn.execute("PRAGMA journal_mode").fetchone()[0]
            if str(current).upper() != "WAL":
                return str(current).lower()
            # Persistent WAL on an unsafe version: downgrade, or fail closed.
            mode = conn.execute("PRAGMA journal_mode=DELETE").fetchone()[0]
            if str(mode).upper() == "WAL":
                raise LedgerError(
                    "unsafe SQLite version cannot downgrade persistent WAL "
                    "database; refusing to operate in WAL mode (fail closed)"
                )
        return str(mode).lower()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    @property
    def wal_enabled(self) -> bool:
        return self._journal_mode == "wal"

    def journal_mode(self) -> str:
        return self._journal_mode

    def sqlite_version(self) -> str:
        return sqlite3.sqlite_version

    # ------------------------------------------------------------------
    # Append path (the only legal writer)
    # ------------------------------------------------------------------

    def append(
        self,
        event_type: str,
        *,
        producer: str,
        principal_id: str,
        space_id: str,
        correlation_id: str,
        idempotency_key: str,
        payload: Mapping[str, Any] | None = None,
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
        destinations: Iterable[str] | None = (DEFAULT_OUTBOX_DESTINATION,),
    ) -> int:
        """Append one event and return its ``sequence``.

        The event row and its outbox rows commit in a single transaction. A
        duplicate ``(producer, idempotency_key)`` raises
        :class:`DuplicateEventError`. Invalid (non-JSON) payloads raise
        :class:`InvalidPayloadError`. Decision/Mandate/Action/Evidence/Outcome
        events without an ``episode_id`` raise :class:`LedgerError`.
        """
        self._require_episode(event_type, episode_id)
        recorded_at = _utc_now()
        occurred = occurred_at or recorded_at
        payload_json = self._encode_payload(payload)

        with self._lock:
            return self._append_serialized(
                event_type=event_type,
                producer=producer,
                principal_id=principal_id,
                space_id=space_id,
                correlation_id=correlation_id,
                idempotency_key=idempotency_key,
                payload_json=payload_json,
                episode_id=episode_id,
                role_context_id=role_context_id,
                responsibility_id=responsibility_id,
                mandate_id=mandate_id,
                causation_id=causation_id,
                occurred_at=occurred,
                recorded_at=recorded_at,
                privacy_class=privacy_class,
                schema_version=schema_version,
                evidence_uri=evidence_uri,
                event_id=event_id,
                destinations=tuple(destinations) if destinations else (),
            )

    @staticmethod
    def _require_episode(event_type: str, episode_id: str | None) -> None:
        cls_name = event_type.split(".")[0]
        if cls_name in EPISODE_REQUIRED_CLASSES and not episode_id:
            raise LedgerError(
                f"{event_type} requires an episode_id "
                f"({cls_name} events must link to an Episode)"
            )

    def _encode_payload(self, payload: Mapping[str, Any] | None) -> str:
        value = {} if payload is None else payload
        if not isinstance(value, Mapping):
            raise InvalidPayloadError("payload must be a JSON object")
        try:
            encoded = json.dumps(
                value, ensure_ascii=False, sort_keys=True, allow_nan=False
            )
        except (TypeError, ValueError) as exc:
            raise InvalidPayloadError(
                f"payload is not JSON-serializable: {exc}"
            ) from exc
        # Reject non-finite floats even if json.dumps would emit them; SQLite
        # json_valid() also rejects NaN/Infinity.
        if _contains_non_finite(value):
            raise InvalidPayloadError(
                "payload contains NaN/Infinity, which are not valid JSON"
            )
        # The database CHECK(json_valid(...)) is the final authority; verify
        # at the boundary too so callers get a typed error before a rollback.
        if not _json_valid(encoded):
            raise InvalidPayloadError("payload failed JSON validation")
        return encoded

    def _append_serialized(
        self,
        *,
        event_type: str,
        producer: str,
        principal_id: str,
        space_id: str,
        correlation_id: str,
        idempotency_key: str,
        payload_json: str,
        episode_id: str | None,
        role_context_id: str | None,
        responsibility_id: str | None,
        mandate_id: str | None,
        causation_id: str | None,
        occurred_at: str,
        recorded_at: str,
        privacy_class: str,
        schema_version: str,
        evidence_uri: str | None,
        event_id: str | None,
        destinations: tuple[str, ...],
    ) -> int:
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            # Read the chain tip inside the transaction so the computed
            # previous_hash and sequence are race-free.
            tip = self._conn.execute(
                "SELECT sequence, event_hash FROM event_log "
                "ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            prev_seq = tip["sequence"] if tip is not None else 0
            previous_hash = tip["event_hash"] if tip is not None else None
            next_sequence = prev_seq + 1

            row_event_id = event_id or f"evt_{uuid4().hex}"

            # Duplicate guard: the UNIQUE constraint is the backstop; a fast
            # explicit check gives a typed error without a constraint exception.
            dup = self._conn.execute(
                "SELECT 1 FROM event_log WHERE producer = ? AND idempotency_key = ?",
                (producer, idempotency_key),
            ).fetchone()
            if dup is not None:
                self._conn.rollback()
                raise DuplicateEventError(
                    f"duplicate event: producer={producer!r} "
                    f"idempotency_key={idempotency_key!r}"
                )

            row = {
                "sequence": next_sequence,
                "event_id": row_event_id,
                "event_type": event_type,
                "schema_version": schema_version,
                "episode_id": episode_id,
                "principal_id": principal_id,
                "space_id": space_id,
                "role_context_id": role_context_id,
                "responsibility_id": responsibility_id,
                "mandate_id": mandate_id,
                "correlation_id": correlation_id,
                "causation_id": causation_id,
                "producer": producer,
                "idempotency_key": idempotency_key,
                "occurred_at": occurred_at,
                "recorded_at": recorded_at,
                "privacy_class": privacy_class,
                "payload_json": payload_json,
                "evidence_uri": evidence_uri,
                "previous_hash": previous_hash,
                "event_hash": None,
            }
            event_hash = self._hash_row(row)
            row["event_hash"] = event_hash

            self._conn.execute(
                "INSERT INTO event_log ("
                + ", ".join(_EVENT_LOG_COLUMNS)
                + ") VALUES ("
                + ", ".join("?" for _ in _EVENT_LOG_COLUMNS)
                + ")",
                tuple(row[col] for col in _EVENT_LOG_COLUMNS),
            )

            for destination in destinations:
                self._conn.execute(
                    "INSERT INTO event_outbox("
                    "event_id, destination, state, attempts, next_attempt_at) "
                    "VALUES (?, ?, ?, 0, ?)",
                    (row_event_id, destination, OUTBOX_PENDING, recorded_at),
                )

            self._conn.execute("COMMIT")
            return int(next_sequence)
        except (LedgerError, sqlite3.Error) as exc:
            # Any failure inside the transaction rolls the whole append back —
            # including the outbox rows, so ledger-commit and publish can never
            # diverge. A sqlite3.IntegrityError on UNIQUE(producer,
            # idempotency_key) only happens under a rare race with the explicit
            # pre-check; normalize it to our typed error.
            try:
                self._conn.rollback()
            except sqlite3.Error:
                pass
            if isinstance(exc, sqlite3.Error):
                dup = self._conn.execute(
                    "SELECT 1 FROM event_log WHERE producer = ? AND idempotency_key = ?",
                    (producer, idempotency_key),
                ).fetchone()
                if dup is not None:
                    raise DuplicateEventError(
                        f"duplicate event: producer={producer!r} "
                        f"idempotency_key={idempotency_key!r}"
                    ) from exc
                raise LedgerError(f"append failed: {exc}") from exc
            raise

    def _hash_row(self, row: Mapping[str, Any]) -> str:
        """Canonical SHA-256 over the full row (excluding the event_hash slot)."""
        canonical = {col: row[col] for col in _EVENT_LOG_COLUMNS if col != "event_hash"}
        return hashlib.sha256(_canonical_json(canonical)).hexdigest()

    # ------------------------------------------------------------------
    # Replay / read
    # ------------------------------------------------------------------

    def read(
        self,
        from_sequence: int = 1,
        *,
        to_sequence: int | None = None,
        limit: int | None = None,
        event_type: str | None = None,
        producer: str | None = None,
        episode_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return a deterministic, sequence-ordered slice of events."""
        clauses: list[str] = ["sequence >= ?"]
        params: list[Any] = [int(from_sequence)]
        if to_sequence is not None:
            clauses.append("sequence <= ?")
            params.append(int(to_sequence))
        if event_type is not None:
            clauses.append("event_type = ?")
            params.append(event_type)
        if producer is not None:
            clauses.append("producer = ?")
            params.append(producer)
        if episode_id is not None:
            clauses.append("episode_id = ?")
            params.append(episode_id)
        sql = (
            "SELECT * FROM event_log WHERE "
            + " AND ".join(clauses)
            + " ORDER BY sequence ASC"
        )
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        with self._lock:
            rows = self._conn.execute(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def count(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) FROM event_log").fetchone()
        return int(row[0])

    def last_sequence(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT MAX(sequence) FROM event_log").fetchone()
        return int(row[0]) if row[0] is not None else 0

    # ------------------------------------------------------------------
    # Integrity: hash chain + anchors
    # ------------------------------------------------------------------

    def verify_chain(
        self, from_sequence: int = 1, to_sequence: int | None = None
    ) -> dict[str, Any]:
        """Recompute the hash chain and report the first broken link.

        ``from_sequence`` starts a partial verification: the initial
        ``previous_hash`` is read from sequence ``from_sequence - 1``, so a
        clean sub-range verifies even when it does not start at sequence 1.

        Returns ``{"ok": bool, "total": int, "first_bad_sequence": int|None,
        "error": str|None}``. Also verifies sequence continuity so a
        smuggled row cannot hide behind a re-written hash.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM event_log ORDER BY sequence ASC"
            ).fetchall()
        # Everything below works against this single snapshot: ``total`` and
        # the prior-row lookup must never re-query self._conn, which could
        # observe a concurrent append and make the result internally
        # inconsistent.
        total = len(rows)
        rows_by_sequence = {int(row["sequence"]): row for row in rows}
        explicit_to = to_sequence is not None
        if to_sequence is None:
            to_sequence = rows[-1]["sequence"] if rows else 0
        low = int(from_sequence)
        high = int(to_sequence)

        if low < 1:
            return {
                "ok": False,
                "total": total,
                "first_bad_sequence": low,
                "error": f"from_sequence must be >= 1, got {low}",
            }

        if not rows:
            # Empty ledger: the default invocation (from=1, no explicit upper
            # bound) succeeds vacuously; an explicit 1..N request cannot be
            # satisfied because there are no events.
            if not explicit_to and low == 1:
                return {
                    "ok": True,
                    "total": 0,
                    "first_bad_sequence": None,
                    "error": None,
                }
            return {
                "ok": False,
                "total": 0,
                "first_bad_sequence": low,
                "error": (
                    f"empty ledger cannot satisfy requested range [{low}, {high}]"
                ),
            }

        tail = int(rows[-1]["sequence"])
        if low > tail:
            return {
                "ok": False,
                "total": total,
                "first_bad_sequence": low,
                "error": f"from_sequence {low} is beyond the chain tail {tail}",
            }
        if high < low:
            return {
                "ok": False,
                "total": total,
                "first_bad_sequence": low,
                "error": f"invalid range: to_sequence {high} < from_sequence {low}",
            }

        # Partial start: the first row's previous_hash must equal the stored
        # hash of the row just before the range (or None when starting at 1).
        # Both come from the same snapshot as ``rows``.
        if low == 1:
            previous_hash: str | None = None
        else:
            prior = rows_by_sequence.get(low - 1)
            if prior is None:
                return {
                    "ok": False,
                    "total": total,
                    "first_bad_sequence": low,
                    "error": (
                        f"sequence gap: row {low - 1} missing before start {low}"
                    ),
                }
            previous_hash = prior["event_hash"]

        expected_sequence = low
        for row in rows:
            seq = int(row["sequence"])
            if seq < low:
                continue
            if seq > high:
                break
            if seq != expected_sequence:
                return {
                    "ok": False,
                    "total": total,
                    "first_bad_sequence": seq,
                    "error": (f"sequence gap: expected {expected_sequence}, got {seq}"),
                }
            if row["previous_hash"] != previous_hash:
                return {
                    "ok": False,
                    "total": total,
                    "first_bad_sequence": seq,
                    "error": (
                        f"previous_hash mismatch at seq {seq}: "
                        f"stored {row['previous_hash']!r}, expected {previous_hash!r}"
                    ),
                }
            recomputed = self._hash_row(row)
            if row["event_hash"] != recomputed:
                return {
                    "ok": False,
                    "total": total,
                    "first_bad_sequence": seq,
                    "error": f"event_hash mismatch at seq {seq}",
                }
            previous_hash = row["event_hash"]
            expected_sequence = seq + 1
        if expected_sequence <= high:
            # The chain is shorter than the requested range: rows ran out
            # before reaching to_sequence, so the range is incomplete.
            return {
                "ok": False,
                "total": total,
                "first_bad_sequence": expected_sequence,
                "error": (
                    f"sequence gap: chain ends at {expected_sequence - 1}, "
                    f"requested through {high}"
                ),
            }
        return {
            "ok": True,
            "total": total,
            "first_bad_sequence": None,
            "error": None,
        }

    def create_anchor(
        self,
        *,
        from_sequence: int = 1,
        to_sequence: int | None = None,
        anchor_id: str | None = None,
    ) -> dict[str, Any]:
        """Compute and persist a root-hash checkpoint over an event range.

        Refuses to anchor over a broken or gapped chain: the range is verified
        with :meth:`verify_chain` first and :class:`IntegrityViolationError` is
        raised on failure, so an anchor never blesses corrupted data.
        """
        explicit_to = to_sequence is not None
        if to_sequence is None:
            to_sequence = self.last_sequence()
        if to_sequence < from_sequence:
            if explicit_to:
                raise LedgerError(
                    "anchor range empty: "
                    f"from_sequence={from_sequence} > to_sequence={to_sequence}"
                )
            # Defaulted to=tail with from beyond the tail: the chain is shorter
            # than the requested range — that is an integrity problem, not a
            # caller range typo.
            chain = self.verify_chain(
                from_sequence=from_sequence, to_sequence=to_sequence
            )
            raise IntegrityViolationError(
                f"cannot anchor over broken chain [{from_sequence}, {to_sequence}]: "
                f"{chain['error']}"
            )
        chain = self.verify_chain(from_sequence=from_sequence, to_sequence=to_sequence)
        if not chain["ok"]:
            raise IntegrityViolationError(
                f"cannot anchor over broken chain [{from_sequence}, {to_sequence}]: "
                f"{chain['error']}"
            )
        with self._lock:
            rows = self._conn.execute(
                "SELECT event_hash FROM event_log "
                "WHERE sequence BETWEEN ? AND ? ORDER BY sequence ASC",
                (from_sequence, to_sequence),
            ).fetchall()
        if not rows:
            raise LedgerError(
                f"no events in anchor range [{from_sequence}, {to_sequence}]"
            )
        digest = hashlib.sha256()
        for row in rows:
            digest.update(row["event_hash"].encode("ascii"))
            digest.update(b"\n")
        root_hash = digest.hexdigest()
        anchor = {
            "anchor_id": anchor_id
            or f"anchor_{_utc_now().replace(':', '').replace('-', '')}",
            "from_sequence": int(from_sequence),
            "to_sequence": int(to_sequence),
            "root_hash": root_hash,
            "signed_at": _utc_now(),
        }
        with self._lock:
            self._conn.execute(
                "INSERT INTO integrity_anchor("
                "anchor_id, from_sequence, to_sequence, root_hash, signed_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    anchor["anchor_id"],
                    anchor["from_sequence"],
                    anchor["to_sequence"],
                    anchor["root_hash"],
                    anchor["signed_at"],
                ),
            )
            self._conn.commit()
        return anchor

    def verify_anchor(self, anchor_id: str) -> dict[str, Any]:
        """Recompute the root hash over an anchor's range and compare.

        Before folding the hashes, every row in the range is re-hashed from its
        stored content — a tampered payload whose ``event_hash`` was not
        updated therefore fails here, not just at a later chain walk.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM integrity_anchor WHERE anchor_id = ?", (anchor_id,)
            ).fetchone()
        if row is None:
            raise LedgerError(f"no anchor with id {anchor_id!r}")
        low, high = int(row["from_sequence"]), int(row["to_sequence"])
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM event_log "
                "WHERE sequence BETWEEN ? AND ? ORDER BY sequence ASC",
                (low, high),
            ).fetchall()
        if len(rows) != high - low + 1:
            return {
                "ok": False,
                "anchor_id": anchor_id,
                "from_sequence": low,
                "to_sequence": high,
                "expected": row["root_hash"],
                "actual": None,
                "error": (
                    f"range [{low}, {high}] has {len(rows)} rows, "
                    f"expected {high - low + 1}"
                ),
            }
        digest = hashlib.sha256()
        for db_row in rows:
            stored_hash = db_row["event_hash"]
            recomputed = self._hash_row(db_row)
            if stored_hash != recomputed:
                return {
                    "ok": False,
                    "anchor_id": anchor_id,
                    "from_sequence": low,
                    "to_sequence": high,
                    "expected": row["root_hash"],
                    "actual": None,
                    "error": (
                        f"event_hash mismatch at seq {db_row['sequence']}: "
                        f"stored {stored_hash!r}, recomputed {recomputed!r}"
                    ),
                }
            digest.update(stored_hash.encode("ascii"))
            digest.update(b"\n")
        recomputed_root = digest.hexdigest()
        ok = recomputed_root == row["root_hash"]
        return {
            "ok": ok,
            "anchor_id": anchor_id,
            "from_sequence": low,
            "to_sequence": high,
            "expected": row["root_hash"],
            "actual": recomputed_root,
            "error": None if ok else "root_hash mismatch",
        }

    def anchors(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM integrity_anchor ORDER BY to_sequence ASC"
            ).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # WAL checkpoint observability (blueprint §10.2 "checkpoint 观测")
    # ------------------------------------------------------------------

    def wal_checkpoint(self, mode: str = "PASSIVE") -> dict[str, Any]:
        """Run ``PRAGMA wal_checkpoint`` and return a receipt.

        ``mode`` is one of PASSIVE / FULL / RESTART / TRUNCATE. Returns the
        raw (busy, log_frames, checkpointed_frames) triple plus convenience
        flags. On a non-WAL database the triple is (0, 0, 0).
        """
        mode = mode.upper()
        if mode not in {"PASSIVE", "FULL", "RESTART", "TRUNCATE"}:
            raise LedgerError(f"invalid wal_checkpoint mode: {mode!r}")
        with self._lock:
            row = self._conn.execute(f"PRAGMA wal_checkpoint({mode})").fetchone()
        busy, log_frames, checkpointed = int(row[0]), int(row[1]), int(row[2])
        return {
            "busy": busy,
            "log_frames": log_frames,
            "checkpointed_frames": checkpointed,
            "ok": busy == 0,
            "mode": mode,
            "journal_mode": self._journal_mode,
        }

    # ------------------------------------------------------------------
    # Projection checkpoints
    # ------------------------------------------------------------------

    def checkpoint_set(self, projector_id: str, last_sequence: int) -> dict[str, Any]:
        """Record/update a projector's replay watermark (UPSERT)."""
        with self._lock:
            self._conn.execute(
                "INSERT INTO projection_checkpoint(projector_id, last_sequence, updated_at) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(projector_id) DO UPDATE SET "
                "last_sequence = excluded.last_sequence, "
                "updated_at = excluded.updated_at",
                (projector_id, int(last_sequence), _utc_now()),
            )
            self._conn.commit()
        return self.checkpoint_get(projector_id)  # type: ignore[return-value]

    def checkpoint_get(self, projector_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM projection_checkpoint WHERE projector_id = ?",
                (projector_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    # ------------------------------------------------------------------
    # Outbox
    # ------------------------------------------------------------------

    def outbox_pending(
        self, destination: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        clauses = ["state = ?"]
        params: list[Any] = [OUTBOX_PENDING]
        if destination is not None:
            clauses.append("destination = ?")
            params.append(destination)
        sql = (
            "SELECT * FROM event_outbox WHERE "
            + " AND ".join(clauses)
            + " ORDER BY next_attempt_at ASC, event_id ASC"
            + " LIMIT ?"
        )
        params.append(int(limit))
        with self._lock:
            rows = self._conn.execute(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def outbox_mark(
        self, event_id: str, destination: str, *, state: str, attempts: int
    ) -> None:
        if state not in (OUTBOX_SENT, OUTBOX_FAILED):
            raise LedgerError(f"invalid outbox state: {state!r}")
        with self._lock:
            self._conn.execute(
                "UPDATE event_outbox SET state = ?, attempts = ?, next_attempt_at = ? "
                "WHERE event_id = ? AND destination = ?",
                (state, int(attempts), _utc_now(), event_id, destination),
            )
            self._conn.commit()

    def outbox_entries(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM event_outbox ORDER BY event_id, destination"
            ).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Migration / introspection
    # ------------------------------------------------------------------

    def schema_version(self) -> str:
        return LEDGER_SCHEMA_VERSION

    def migration_status(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT version, applied_at, checksum "
                "FROM schema_migration ORDER BY version"
            ).fetchall()
        return [dict(row) for row in rows]


def _json_valid(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except (ValueError, TypeError):
        return False


def _contains_non_finite(value: Any) -> bool:
    if isinstance(value, float):
        return not math.isfinite(value)
    if isinstance(value, Mapping):
        return any(_contains_non_finite(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_non_finite(v) for v in value)
    return False


__all__ = [
    "BUSY_TIMEOUT_MS",
    "DEFAULT_OUTBOX_DESTINATION",
    "DEFAULT_PRIVACY_CLASS",
    "DEFAULT_SCHEMA_VERSION",
    "EPISODE_REQUIRED_CLASSES",
    "OUTBOX_FAILED",
    "OUTBOX_PENDING",
    "OUTBOX_SENT",
    "DuplicateEventError",
    "IntegrityViolationError",
    "InvalidPayloadError",
    "LedgerBroker",
    "LedgerError",
    "_canonical_json",
]
