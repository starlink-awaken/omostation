"""SQLite causal Event Ledger — physical schema (blueprint §10.2).

Implements the authoritative append-only ledger physical model from
`docs/architecture/digital-twin-blueprint-v1.md` §10.2:

- ``event_log`` — append-only causal event store, hash-chained.
- ``projection_checkpoint`` — per-projector replay watermark.
- ``event_outbox`` — durable publish queue written in the same transaction
  as the append (ledger-commit / event-publish atomicity).
- ``schema_migration`` — applied schema versions with content checksums.
- ``integrity_anchor`` — periodic signed root-hash checkpoints.

This module owns the DDL, the SQLite version gate, and the drift-checked
migration path. Runtime behavior (serialized writes, hash chain, outbox)
lives in :mod:`omo.event_ledger.broker`.

Migration integrity guarantees implemented here:

- ``SCHEMA_CHECKSUM`` is derived from the *actual* DDL + trigger + index SQL
  text, so any edit to the physical model changes the fingerprint.
- ``apply_schema`` runs in one explicit transaction; a failure (including a
  malformed pre-existing table detected by drift checks) rolls back every
  statement and leaves no partially-created objects behind.
- Every reopen re-verifies the physical schema against the expected model
  (tables, columns, index columns, UNIQUE, ``CHECK(json_valid)``, triggers)
  and fails closed on drift — it never silently "fixes" an altered schema.
- Drift is never auto-repaired: a missing or modified append-only trigger,
  an extra/missing column, a weakened CHECK, an altered index, or an
  unexpected table all abort with :class:`LedgerSchemaError`. The database
  is left untouched for operator investigation.
"""

from __future__ import annotations

import hashlib
import sqlite3
from typing import Any

# ---------------------------------------------------------------------------
# Schema versioning
# ---------------------------------------------------------------------------

#: Bump this whenever the ledger DDL changes in a way that requires a new
#: migration. The current value defines the schema the broker expects.
LEDGER_SCHEMA_VERSION = "1"

# ---------------------------------------------------------------------------
# DDL (authoritative physical model — blueprint §10.2)
# ---------------------------------------------------------------------------

LEDGER_DDL = """
-- Append-only causal event store (blueprint §10.2).
CREATE TABLE IF NOT EXISTS event_log (
  sequence           INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id           TEXT NOT NULL UNIQUE,
  event_type         TEXT NOT NULL,
  schema_version     TEXT NOT NULL,
  episode_id         TEXT,
  principal_id       TEXT NOT NULL,
  space_id           TEXT NOT NULL,
  role_context_id    TEXT,
  responsibility_id  TEXT,
  mandate_id         TEXT,
  correlation_id     TEXT NOT NULL,
  causation_id       TEXT,
  producer           TEXT NOT NULL,
  idempotency_key    TEXT NOT NULL,
  occurred_at        TEXT NOT NULL,
  recorded_at        TEXT NOT NULL,
  privacy_class      TEXT NOT NULL,
  payload_json       TEXT NOT NULL CHECK(json_valid(payload_json)),
  evidence_uri       TEXT,
  previous_hash      TEXT,
  event_hash         TEXT NOT NULL,
  UNIQUE(producer, idempotency_key)
);

-- Per-projector replay watermark.
CREATE TABLE IF NOT EXISTS projection_checkpoint (
  projector_id  TEXT PRIMARY KEY,
  last_sequence INTEGER NOT NULL,
  updated_at    TEXT NOT NULL
);

-- Durable publish queue; written atomically with the ledger append.
CREATE TABLE IF NOT EXISTS event_outbox (
  event_id        TEXT NOT NULL,
  destination     TEXT NOT NULL,
  state           TEXT NOT NULL,
  attempts        INTEGER NOT NULL DEFAULT 0,
  next_attempt_at TEXT NOT NULL,
  PRIMARY KEY (event_id, destination)
);

-- Applied schema migrations with content checksums.
CREATE TABLE IF NOT EXISTS schema_migration (
  version    TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL,
  checksum   TEXT NOT NULL
);

-- Periodic signed root-hash checkpoints.
CREATE TABLE IF NOT EXISTS integrity_anchor (
  anchor_id     TEXT PRIMARY KEY,
  from_sequence INTEGER NOT NULL,
  to_sequence   INTEGER NOT NULL,
  root_hash     TEXT NOT NULL,
  signed_at     TEXT NOT NULL
);

-- Required indexes (blueprint §10.2).
CREATE INDEX IF NOT EXISTS idx_event_log_episode_sequence
  ON event_log(episode_id, sequence);
CREATE INDEX IF NOT EXISTS idx_event_log_principal_space_time
  ON event_log(principal_id, space_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_event_log_responsibility_time
  ON event_log(responsibility_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_event_log_event_type_time
  ON event_log(event_type, recorded_at);
CREATE INDEX IF NOT EXISTS idx_event_log_mandate_sequence
  ON event_log(mandate_id, sequence);
CREATE INDEX IF NOT EXISTS idx_event_outbox_state_next_attempt
  ON event_outbox(state, next_attempt_at);
"""

LEDGER_TRIGGERS = """
-- Append-only enforcement: any direct UPDATE/DELETE on event_log is rejected.
-- INSERTs are only reachable through the serialized LedgerBroker write path.
CREATE TRIGGER IF NOT EXISTS trg_event_log_no_update
BEFORE UPDATE ON event_log
BEGIN
  SELECT RAISE(ABORT, 'event_log is append-only: UPDATE forbidden');
END;

CREATE TRIGGER IF NOT EXISTS trg_event_log_no_delete
BEFORE DELETE ON event_log
BEGIN
  SELECT RAISE(ABORT, 'event_log is append-only: DELETE forbidden');
END;

-- Blueprint §10.2: Decision/Mandate/Action/Evidence/Outcome events must link
-- to an Episode. This is the DB-level backstop; the broker enforces the same
-- rule at its API boundary. Other event classes (e.g. SignalObserved) may
-- legally be stored without an episode.
CREATE TRIGGER IF NOT EXISTS trg_event_log_episode_required
BEFORE INSERT ON event_log
WHEN (NEW.event_type IN ('Decision', 'Mandate', 'Action', 'Evidence', 'Outcome')
      OR NEW.event_type GLOB 'Decision.*'
      OR NEW.event_type GLOB 'Mandate.*'
      OR NEW.event_type GLOB 'Action.*'
      OR NEW.event_type GLOB 'Evidence.*'
      OR NEW.event_type GLOB 'Outcome.*')
 AND (NEW.episode_id IS NULL OR NEW.episode_id = '')
BEGIN
  SELECT RAISE(ABORT, 'event_log episode_id required for Decision/Mandate/Action/Evidence/Outcome events');
END;
"""

#: Canonical schema fingerprint computed from the actual DDL + trigger + index
#: SQL text. Any modification to the physical model (columns, constraints,
#: indexes, triggers, types) changes this checksum.
SCHEMA_CHECKSUM = hashlib.sha256(
    (LEDGER_DDL + "\n" + LEDGER_TRIGGERS).encode("utf-8")
).hexdigest()

# ---------------------------------------------------------------------------
# SQLite security version gate (blueprint §10.2)
# ---------------------------------------------------------------------------
#
# The blueprint requires an officially patched SQLite for production WAL
# writes: "运行版本必须为官方已修复版本（≥3.51.3，或含修复的 3.44.6/3.50.7
# 回移版本），否则禁止启用正式 WAL 写入。"
#
# Allowed set:
#   * >= 3.51.3 (any later official release)
#   * the patched backport lines 3.44.6+ and 3.50.7+
#
# Any other version still works (broker falls back to the default rollback
# journal mode) but must not enable WAL — and, on reopen, a persistent WAL
# database must be downgraded to DELETE or rejected (fail closed).

_SQLITE_SAFE_MIN = (3, 51, 3)
_SQLITE_SAFE_BACKPORTS = (
    ((3, 44, 0), (3, 44, 6)),
    ((3, 50, 0), (3, 50, 7)),
)


def is_wal_allowed(version_info: tuple[int, int, int] | list[int] | None) -> bool:
    """Return True when a SQLite version is in the blueprint safe set.

    Safe set (per blueprint §10.2):
      - major.minor.patch >= 3.51.3
      - the patched 3.44.6+ backport line (3.44.6 <= v < 3.45.0)
      - the patched 3.50.7+ backport line (3.50.7 <= v < 3.51.0)
    """
    if version_info is None:
        return False
    ver = (int(version_info[0]), int(version_info[1]), int(version_info[2]))
    if ver >= _SQLITE_SAFE_MIN:
        return True
    for low, patched in _SQLITE_SAFE_BACKPORTS:
        if low <= ver < (low[0], low[1] + 1, 0) and ver >= patched:
            return True
    return False


def wal_allowed_for_current() -> bool:
    """Evaluate the version gate against the running sqlite3 library."""
    return is_wal_allowed(sqlite3.sqlite_version_info)


# ---------------------------------------------------------------------------
# Expected physical model (drift verification target)
# ---------------------------------------------------------------------------

#: Expected event_log columns: name -> (SQL type normalized, NOT NULL flag).
#: ``sequence`` is an INTEGER PRIMARY KEY (AUTOINCREMENT), so PRAGMA
#: ``notnull`` reports 0 for it; we model it as not-flagged.
_EXPECTED_EVENT_LOG_COLUMNS: dict[str, tuple[str, bool]] = {
    "sequence": ("INTEGER", False),
    "event_id": ("TEXT", True),
    "event_type": ("TEXT", True),
    "schema_version": ("TEXT", True),
    "episode_id": ("TEXT", False),
    "principal_id": ("TEXT", True),
    "space_id": ("TEXT", True),
    "role_context_id": ("TEXT", False),
    "responsibility_id": ("TEXT", False),
    "mandate_id": ("TEXT", False),
    "correlation_id": ("TEXT", True),
    "causation_id": ("TEXT", False),
    "producer": ("TEXT", True),
    "idempotency_key": ("TEXT", True),
    "occurred_at": ("TEXT", True),
    "recorded_at": ("TEXT", True),
    "privacy_class": ("TEXT", True),
    "payload_json": ("TEXT", True),
    "evidence_uri": ("TEXT", False),
    "previous_hash": ("TEXT", False),
    "event_hash": ("TEXT", True),
}

#: Expected companion table columns, mirroring what PRAGMA table_info reports:
#: columns declared ``NOT NULL`` are flagged True even when they are part of a
#: composite PRIMARY KEY; single-column PRIMARY KEYs without explicit NOT NULL
#: report ``notnull=0`` and are modeled False.
_EXPECTED_TABLE_COLUMNS: dict[str, dict[str, tuple[str, bool]]] = {
    "projection_checkpoint": {
        "projector_id": ("TEXT", False),
        "last_sequence": ("INTEGER", True),
        "updated_at": ("TEXT", True),
    },
    "event_outbox": {
        "event_id": ("TEXT", True),
        "destination": ("TEXT", True),
        "state": ("TEXT", True),
        "attempts": ("INTEGER", True),
        "next_attempt_at": ("TEXT", True),
    },
    "schema_migration": {
        "version": ("TEXT", False),
        "applied_at": ("TEXT", True),
        "checksum": ("TEXT", True),
    },
    "integrity_anchor": {
        "anchor_id": ("TEXT", False),
        "from_sequence": ("INTEGER", True),
        "to_sequence": ("INTEGER", True),
        "root_hash": ("TEXT", True),
        "signed_at": ("TEXT", True),
    },
}

#: Expected indexes: name -> (table, ordered column list).
_EXPECTED_INDEXES: dict[str, tuple[str, tuple[str, ...]]] = {
    "idx_event_log_episode_sequence": ("event_log", ("episode_id", "sequence")),
    "idx_event_log_principal_space_time": (
        "event_log",
        ("principal_id", "space_id", "recorded_at"),
    ),
    "idx_event_log_responsibility_time": (
        "event_log",
        ("responsibility_id", "recorded_at"),
    ),
    "idx_event_log_event_type_time": ("event_log", ("event_type", "recorded_at")),
    "idx_event_log_mandate_sequence": ("event_log", ("mandate_id", "sequence")),
    "idx_event_outbox_state_next_attempt": (
        "event_outbox",
        ("state", "next_attempt_at"),
    ),
}

#: Expected append-only triggers: name -> normalized CREATE TRIGGER SQL.
#: These mirror the authoritative definitions in LEDGER_TRIGGERS; verify_schema
#: compares both name presence AND definition equivalence so a modified
#: trigger body/condition is drift, not just a dropped one.
_EXPECTED_TRIGGERS: dict[str, str] = {}


def _normalize_sql(sql: str) -> str:
    """Normalize SQL for definition-equivalence comparison.

    Collapses all whitespace runs to a single space, strips the
    ``IF NOT EXISTS`` modifier and any trailing ``;`` — both of which
    sqlite_master.sql drops when storing the canonical definition.
    Uppercases nothing — string literals (trigger messages) are case-sensitive.
    """
    return " ".join(sql.replace("IF NOT EXISTS", "").rstrip(";").split())


def _trigger_definitions_from_script(
    script: str,
) -> list[tuple[str, str]]:
    """Extract (trigger_name, sql) pairs from a CREATE TRIGGER script."""
    definitions: list[tuple[str, str]] = []
    for stmt in _iter_statements(script):
        first_line = stmt.splitlines()[0]
        tokens = first_line.split()
        # tokens: CREATE TRIGGER [IF NOT EXISTS] <name>
        if tokens[:2] != ["CREATE", "TRIGGER"]:
            continue
        name = tokens[-1]
        definitions.append((name, _normalize_sql(stmt)))
    return definitions


class LedgerSchemaError(RuntimeError):
    """Schema migration mismatch or unsupported ledger schema."""


# ---------------------------------------------------------------------------
# SQL statement helpers
# ---------------------------------------------------------------------------


def _iter_statements(script: str) -> list[str]:
    """Split a multi-statement SQL script into individual statements.

    Uses :func:`sqlite3.complete_statement` so semicolons inside trigger
    bodies (BEGIN…END) are not treated as statement boundaries. ``--`` line
    comments are stripped first. Returns executable, comment-free statements.
    """
    statements: list[str] = []
    buf = ""
    for line in script.splitlines():
        comment = line.find("--")
        line = line if comment == -1 else line[:comment]
        buf += line + "\n"
        if not buf.strip():
            continue
        if sqlite3.complete_statement(buf):
            statements.append(buf.strip())
            buf = ""
    if buf.strip():
        statements.append(buf.strip())
    return statements


#: Populate expected trigger definitions from the authoritative script so the
#: verification target can never drift from the DDL that fresh databases get.
_EXPECTED_TRIGGERS.update(
    {
        name: _normalize_sql(sql)
        for name, sql in _trigger_definitions_from_script(LEDGER_TRIGGERS)
    }
)


# ---------------------------------------------------------------------------
# Drift verification
# ---------------------------------------------------------------------------


def _table_sql(conn: sqlite3.Connection, name: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone()
    if row is None:
        raise LedgerSchemaError(f"missing table: {name}")
    return row[0] or ""


def _normalize_type(sql_type: str | None) -> str:
    return " ".join((sql_type or "").upper().split())


def _expected_table_stmt(table: str) -> str:
    """Return the authoritative CREATE TABLE statement for a ledger table."""
    for stmt in _iter_statements(LEDGER_DDL):
        if _ddl_head_name(stmt, "TABLE") == table:
            return stmt
    raise LedgerSchemaError(f"no DDL defined for expected table {table}")


def _expected_index_stmt(index_name: str) -> str:
    """Return the authoritative CREATE INDEX statement for a ledger index."""
    for stmt in _iter_statements(LEDGER_DDL):
        if _ddl_head_name(stmt, "INDEX") == index_name:
            return stmt
    raise LedgerSchemaError(f"no DDL defined for expected index {index_name}")


def _ddl_head_name(stmt: str, kind: str) -> str | None:
    """Extract the object name from a CREATE <kind> statement head line.

    Head tokens: CREATE <kind> [IF NOT EXISTS] <name> [optional '('].
    """
    tokens = stmt.splitlines()[0].split()
    if len(tokens) < 3 or tokens[0] != "CREATE" or tokens[1] != kind:
        return None
    if tokens[2] == "IF":  # IF NOT EXISTS name [ '(' ]
        name = tokens[5] if len(tokens) > 5 else None
    else:
        name = tokens[2]
    if name and name.endswith("("):
        name = name[:-1]
    return name


def _index_sql(conn: sqlite3.Connection, index_name: str) -> str | None:
    """Return the stored CREATE INDEX SQL for a named index, or None."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?",
        (index_name,),
    ).fetchone()
    return row[0] if row is not None else None


def verify_schema(conn: sqlite3.Connection) -> dict[str, Any]:
    """Verify the live physical schema against the expected model.

    Raises :class:`LedgerSchemaError` on any drift. Checks:
    - all five tables exist and their stored CREATE TABLE DDL equals the
      authoritative DDL when whitespace-normalized — this catches extra or
      missing columns, weakened/removed ``CHECK(json_valid)``, changed types,
      NOT NULL, and UNIQUE constraint changes in one exact comparison;
    - ``event_log`` columns match name/type/NOT NULL exactly (with a clear
      per-column error message);
    - companion table columns match name/type;
    - every required index exists on its expected table with the exact
      ordered column list;
    - every append-only trigger exists with an equivalent normalized
      definition.
    """
    expected_tables = {"event_log", *_EXPECTED_TABLE_COLUMNS}
    actual_tables = table_names(conn)
    missing_tables = expected_tables - actual_tables
    if missing_tables:
        raise LedgerSchemaError(
            f"schema drift: missing tables: {sorted(missing_tables)}"
        )
    unexpected_tables = actual_tables - expected_tables
    if unexpected_tables:
        raise LedgerSchemaError(
            f"schema drift: unexpected tables: {sorted(unexpected_tables)}"
        )

    # Exact normalized DDL comparison per table: the strongest drift check.
    # It detects extra columns, weakened CHECK, altered UNIQUE, etc.
    for table in sorted(expected_tables):
        stored_sql = _table_sql(conn, table)
        expected_sql = _normalize_sql(_expected_table_stmt(table))
        if _normalize_sql(stored_sql) != expected_sql:
            raise LedgerSchemaError(f"schema drift: {table} DDL changed")

    for name, (col_type, not_null) in _EXPECTED_EVENT_LOG_COLUMNS.items():
        actual = _column_info(conn, "event_log", name)
        _check_column("event_log", name, col_type, not_null, actual)

    for table, columns in _EXPECTED_TABLE_COLUMNS.items():
        for col_name, (col_type, not_null) in columns.items():
            actual = _column_info(conn, table, col_name)
            _check_column(table, col_name, col_type, not_null, actual)

    for index_name, (table, columns) in _EXPECTED_INDEXES.items():
        stored_sql = _index_sql(conn, index_name)
        if stored_sql is None:
            raise LedgerSchemaError(f"schema drift: missing index: {index_name}")
        # Exact normalized DDL comparison against the authoritative CREATE
        # INDEX statement — catches UNIQUE/partial WHERE changes, wrong table,
        # and altered column lists in one check.
        if _normalize_sql(stored_sql) != _normalize_sql(
            _expected_index_stmt(index_name)
        ):
            raise LedgerSchemaError(
                f"schema drift: index {index_name} definition changed"
            )
        # Belt-and-braces: verify the index is attached to the expected table
        # with the exact ordered columns.
        info = _index_info(conn, index_name)
        if info is None:
            raise LedgerSchemaError(f"schema drift: missing index: {index_name}")
        actual_table, actual_columns = info
        if actual_table != table:
            raise LedgerSchemaError(
                f"schema drift: index {index_name} is on table {actual_table!r}, "
                f"expected {table!r}"
            )
        if list(actual_columns) != list(columns):
            raise LedgerSchemaError(
                f"schema drift: index {index_name} columns {list(actual_columns)} "
                f"!= expected {list(columns)}"
            )

    for trigger_name in sorted(_EXPECTED_TRIGGERS):
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'trigger' AND name = ?",
            (trigger_name,),
        ).fetchone()
        if row is None:
            raise LedgerSchemaError(f"schema drift: missing trigger: {trigger_name}")
        actual_sql = _normalize_sql(row[0] or "")
        expected_sql = _EXPECTED_TRIGGERS[trigger_name]
        if actual_sql != expected_sql:
            raise LedgerSchemaError(
                f"schema drift: trigger {trigger_name} definition changed"
            )

    return {"tables": sorted(actual_tables), "ok": True}


def _column_info(
    conn: sqlite3.Connection, table: str, column: str
) -> tuple[str, bool] | None:
    rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    for row in rows:
        # PRAGMA table_info columns: cid, name, type, notnull, dflt_value, pk
        if row[1] == column:
            return (_normalize_type(row[2]), bool(row[3]))
    return None


def _check_column(
    table: str,
    column: str,
    expected_type: str,
    expected_not_null: bool,
    actual: tuple[str, bool] | None,
) -> None:
    if actual is None:
        raise LedgerSchemaError(f"schema drift: {table} missing column {column}")
    actual_type, actual_not_null = actual
    if actual_type != expected_type:
        raise LedgerSchemaError(
            f"schema drift: {table}.{column} type {actual_type!r} "
            f"!= expected {expected_type!r}"
        )
    if actual_not_null != expected_not_null:
        raise LedgerSchemaError(
            f"schema drift: {table}.{column} NOT NULL={actual_not_null} "
            f"!= expected {expected_not_null}"
        )


def _index_info(
    conn: sqlite3.Connection, index_name: str
) -> tuple[str, list[str]] | None:
    """Return (table_name, ordered column list) for a named index, or None."""
    row = conn.execute(
        "SELECT tbl_name FROM sqlite_master WHERE type = 'index' AND name = ?",
        (index_name,),
    ).fetchone()
    if row is None:
        return None
    entries = conn.execute(f'PRAGMA index_info("{index_name}")').fetchall()
    # PRAGMA index_info columns: seqno, cid, name
    return (row[0], [entry[2] for entry in entries])


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


def apply_schema(
    conn: sqlite3.Connection,
    *,
    schema_version: str = LEDGER_SCHEMA_VERSION,
    checksum: str = SCHEMA_CHECKSUM,
) -> None:
    """Create or verify the ledger schema in one explicit transaction.

    Fresh database: applies the full DDL + trigger script, records the
    migration, and verifies the result — all in one transaction, so a
    malformed pre-existing table never leaves a partial schema behind.

    Already-migrated database: does **not** re-apply the DDL or triggers
    (which would silently repair drift). Instead it verifies the live
    physical schema — tables, columns, index columns, UNIQUE, JSON CHECK,
    and the exact trigger definitions — and fails closed on any drift,
    including a dropped or modified append-only trigger.

    A recorded checksum mismatch always fails closed.
    """
    conn.execute("BEGIN")
    try:
        has_migration_table = (
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' "
                "AND name = 'schema_migration'"
            ).fetchone()
            is not None
        )
        applied = None
        if has_migration_table:
            applied = conn.execute(
                "SELECT checksum FROM schema_migration WHERE version = ?",
                (schema_version,),
            ).fetchone()

        if applied is None:
            # Fresh ledger: full create in one transaction.
            for stmt in _iter_statements(LEDGER_DDL + "\n" + LEDGER_TRIGGERS):
                conn.execute(stmt)
            conn.execute(
                "INSERT INTO schema_migration(version, applied_at, checksum) "
                "VALUES (?, datetime('now'), ?)",
                (schema_version, checksum),
            )
        else:
            if applied[0] != checksum:
                raise LedgerSchemaError(
                    f"schema_migration version {schema_version} checksum mismatch: "
                    f"recorded {applied[0]!r}, expected {checksum!r}"
                )
            # Already migrated: do NOT re-run DDL or triggers — any missing or
            # modified trigger is drift and must fail closed, never be silently
            # repaired. verify_schema below performs the exact check.

        verify_schema(conn)
        conn.execute("COMMIT")
    except BaseException:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise


def table_names(conn: sqlite3.Connection) -> set[str]:
    """Return the set of user tables currently present in the database."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row[0] for row in rows}


def schema_fingerprint(conn: sqlite3.Connection) -> dict[str, Any]:
    """Return a summary of the physical schema for diagnostics/tests."""
    return {
        "tables": sorted(table_names(conn)),
        "migrations": [
            dict(row)
            for row in conn.execute(
                "SELECT version, checksum FROM schema_migration ORDER BY version"
            ).fetchall()
        ],
        "triggers": [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger' "
                "AND tbl_name = 'event_log' ORDER BY name"
            ).fetchall()
        ],
    }


__all__ = [
    "LEDGER_DDL",
    "LEDGER_SCHEMA_VERSION",
    "LEDGER_TRIGGERS",
    "SCHEMA_CHECKSUM",
    "LedgerSchemaError",
    "apply_schema",
    "is_wal_allowed",
    "schema_fingerprint",
    "table_names",
    "verify_schema",
    "wal_allowed_for_current",
]
