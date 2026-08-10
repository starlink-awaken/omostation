"""JSONL shadow projection for the causal Event Ledger (BET-Y1Q2-T1-03).

Bridges legacy JSONL governance-history files (e.g.
``.omo/_knowledge/governance-history.jsonl``) into the authoritative causal
ledger without ever writing to the old JSONL.

Design rules:

- **Read-only adapter over the broker**: every healthy record is persisted
  exclusively through :meth:`LedgerBroker.append`. No direct SQL, no other
  write surface, and export/compare never mutate the source file.
- **Idempotent by content**: the broker idempotency key combines a *logical*
  source identity (``--source-id`` or the file basename — never an absolute
  machine path) with a canonical ``(sort_keys, compact, UTF-8)`` SHA-256 of
  the original record. Line numbers and timestamps never enter the key, so a
  second import appends zero new rows.
- **Quarantine instead of abort**: bad JSON, non-object lines, explicit
  unknown ``schema_version``/``version``, and reverse-write markers
  (``authority=ledger`` or ``read_only=true`` at the top level or in
  ``_meta``) are quarantined; healthy lines continue. Without a
  ``--quarantine`` path nothing is written beside the source.
- **Export is explicitly read-only**: every exported line declares
  ``authority="ledger"`` / ``read_only=true`` / ``projection="jsonl-shadow/v1"``
  so re-importing an export is always rejected and the DB never grows.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from omo.event_ledger.broker import DuplicateEventError, LedgerError

#: Fixed shadow event type for every JSONL shadow append.
SHADOW_EVENT_TYPE = "jsonl.shadow.ingest.v1"
#: Fixed shadow producer for every JSONL shadow append.
SHADOW_PRODUCER = "omo-jsonl-shadow"
#: Projection tag written on every exported line.
PROJECTION = "jsonl-shadow/v1"
#: Canonical version label for records without an explicit version.
LEGACY_V0 = "legacy-v0"
#: Explicit version strings accepted as legacy v0 (missing = legacy v0 too).
_KNOWN_VERSIONS = frozenset({"legacy-v0", "v0", "0"})


class JsonlShadowError(LedgerError):
    """Domain error for the JSONL shadow adapter (BET-Y1Q2-T1-03)."""


def _canonical_json_bytes(value: Any) -> bytes:
    """Canonical JSON: sort_keys, compact separators, UTF-8."""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def content_hash(record: dict[str, Any]) -> str:
    """Canonical SHA-256 of the original record (content-only, key-order agnostic)."""
    return hashlib.sha256(_canonical_json_bytes(record)).hexdigest()


def derive_source(file_path: Path | str, source_id: str | None = None) -> str:
    """Logical source identity: ``--source-id`` wins, else the file basename.

    Never an absolute machine path, so idempotency keys stay portable across
    checkouts and machines.
    """
    if source_id:
        return str(source_id)
    return Path(file_path).name


def idempotency_key(source: str, record_hash: str) -> str:
    """Broker idempotency key: logical source identity + content hash."""
    return f"jsonl-shadow:{source}:{record_hash}"


def _detect_version(record: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return ``(version, None)`` for a known version, ``(None, reason)`` otherwise.

    Missing ``schema_version``/``version`` is legacy v0; any explicit version
    outside the known set is quarantined as ``unknown_version``.
    """
    raw = record.get("schema_version", record.get("version"))
    if raw is None:
        return LEGACY_V0, None
    if isinstance(raw, str) and raw.strip().lower() in _KNOWN_VERSIONS:
        return LEGACY_V0, None
    return None, "unknown_version"


def _reverse_write_flagged(record: dict[str, Any]) -> bool:
    """Reverse-write markers at the top level or inside ``_meta``."""
    for container in (record, record.get("_meta")):
        if not isinstance(container, dict):
            continue
        if container.get("authority") == "ledger":
            return True
        if container.get("read_only") is True:
            return True
    return False


def _contains_non_finite(value: Any) -> bool:
    """Recursively detect NaN/Infinity floats (Python json.loads accepts them)."""
    if isinstance(value, float):
        return not math.isfinite(value)
    if isinstance(value, dict):
        return any(_contains_non_finite(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_non_finite(v) for v in value)
    return False


def classify_line(
    raw_line: str, source: str, line_no: int
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
    """Classify one non-empty JSONL line.

    Returns ``(quarantine_entry, record, version)``:

    - healthy: ``(None, record, version)``
    - quarantined: ``(entry, None, None)`` where ``entry`` carries
      ``source`` / ``line`` / ``reason`` / ``detail`` / ``record``.

    Bad JSON — including NaN/Infinity, which Python's ``json.loads`` accepts
    but are not legal JSON — is quarantined as ``parse_error``; quarantine
    entries never carry raw non-finite values so they always serialize.
    """
    try:
        record = json.loads(raw_line)
    except (json.JSONDecodeError, ValueError) as exc:
        return (
            {
                "source": source,
                "line": line_no,
                "reason": "parse_error",
                "detail": f"invalid JSON: {exc}",
                "record": raw_line,
            },
            None,
            None,
        )
    if _contains_non_finite(record):
        return (
            {
                "source": source,
                "line": line_no,
                "reason": "parse_error",
                "detail": "record contains NaN/Infinity, which are not valid JSON",
                "record": raw_line,
            },
            None,
            None,
        )
    if not isinstance(record, dict):
        return (
            {
                "source": source,
                "line": line_no,
                "reason": "not_object",
                "detail": f"line is {type(record).__name__}, expected object",
                "record": record,
            },
            None,
            None,
        )
    if _reverse_write_flagged(record):
        return (
            {
                "source": source,
                "line": line_no,
                "reason": "reverse_write_rejected",
                "detail": "record declares authority=ledger or read_only=true",
                "record": record,
            },
            None,
            None,
        )
    version, reason = _detect_version(record)
    if reason is not None:
        return (
            {
                "source": source,
                "line": line_no,
                "reason": "unknown_version",
                "detail": (
                    "unsupported schema_version/version: "
                    f"{record.get('schema_version', record.get('version'))!r}"
                ),
                "record": record,
            },
            None,
            None,
        )
    return None, record, version


def _write_quarantine(path: Path, entries: list[dict[str, Any]]) -> None:
    lines = [
        json.dumps(entry, ensure_ascii=False, sort_keys=True, allow_nan=False)
        for entry in entries
    ]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _iter_healthy(
    file_path: Path, source: str
) -> tuple[list[tuple[dict[str, Any], str, int]], list[dict[str, Any]], int]:
    """Scan a JSONL file once: healthy ``(record, hash, line_no)`` + quarantined.

    Returns ``(healthy, quarantined, healthy_count)``. Healthy records keep
    their first-seen line number (informational only — never part of the
    idempotency key).
    """
    healthy: list[tuple[dict[str, Any], str, int]] = []
    quarantined: list[dict[str, Any]] = []
    with file_path.open("r", encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line:
                continue
            entry, record, _ = classify_line(line, source, line_no)
            if entry is not None:
                quarantined.append(entry)
                continue
            healthy.append((record, content_hash(record), line_no))
    return healthy, quarantined, len(healthy)


def import_jsonl(
    broker: Any,
    file_path: Path | str,
    *,
    quarantine_path: Path | str | None = None,
    source_id: str | None = None,
) -> dict[str, Any]:
    """Import a JSONL file as shadow events through the broker.

    Returns a report with ``healthy`` / ``imported`` / ``duplicates`` /
    ``quarantined`` counts, quarantine entries, and reason histogram. Every
    healthy record is appended via ``broker.append``; duplicates (already
    imported, or repeated within the file) are caught as no-ops.
    """
    file_path = Path(file_path)
    source = derive_source(file_path, source_id)
    if (
        quarantine_path is not None
        and Path(quarantine_path).resolve() == file_path.resolve()
    ):
        raise JsonlShadowError(
            "quarantine_path must not be the same file as the JSONL source"
        )
    report: dict[str, Any] = {
        "source": source,
        "file": str(file_path),
        "healthy": 0,
        "imported": 0,
        "duplicates": 0,
        "quarantined": 0,
        "quarantine_reasons": {},
        "quarantine_entries": [],
    }

    healthy, quarantined, healthy_count = _iter_healthy(file_path, source)
    report["healthy"] = healthy_count
    report["quarantined"] = len(quarantined)
    report["quarantine_entries"] = quarantined
    for entry in quarantined:
        reason = entry["reason"]
        report["quarantine_reasons"][reason] = (
            report["quarantine_reasons"].get(reason, 0) + 1
        )

    for record, record_hash, line_no in healthy:
        payload = {
            "source": source,
            "hash": record_hash,
            "version": LEGACY_V0,
            "line": line_no,
            "original": record,
        }
        try:
            broker.append(
                event_type=SHADOW_EVENT_TYPE,
                producer=SHADOW_PRODUCER,
                principal_id="jsonl-shadow",
                space_id="default",
                correlation_id=f"jsonl-shadow:{record_hash[:16]}",
                idempotency_key=idempotency_key(source, record_hash),
                payload=payload,
            )
            report["imported"] += 1
        except DuplicateEventError:
            report["duplicates"] += 1

    if quarantine_path is not None and quarantined:
        quarantine = Path(quarantine_path)
        quarantine.parent.mkdir(parents=True, exist_ok=True)
        _write_quarantine(quarantine, quarantined)
        report["quarantine_file"] = str(quarantine)
    return report


def _is_adapter_export(path: Path) -> bool:
    """True when an existing file is a legal export of this adapter.

    Every non-empty line must be a JSON object that simultaneously carries the
    full adapter export envelope: ``projection`` exactly matching
    ``PROJECTION``, ``authority == "ledger"``, ``read_only is True``, and the
    ``source`` / ``hash`` / ``original`` fields. A line that merely fakes the
    ``projection`` field (e.g. arbitrary authoritative JSONL) is NOT treated
    as an adapter export, so it can never be overwritten. The ``original``
    business schema is deliberately not validated beyond field presence.
    Empty or non-matching files are likewise never overwritten.
    """
    if not path.exists():
        return False
    lines = [
        line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if not lines:
        return False
    for line in lines:
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            return False
        if not isinstance(obj, dict):
            return False
        if obj.get("projection") != PROJECTION:
            return False
        if obj.get("authority") != "ledger":
            return False
        if obj.get("read_only") is not True:
            return False
        if not all(key in obj for key in ("source", "hash", "original")):
            return False
    return True


def export_jsonl(broker: Any, output_path: Path | str) -> dict[str, Any]:
    """Export this adapter's shadow events as legal JSONL in stable order.

    Every line is a top-level object declaring ``authority="ledger"``,
    ``read_only=true``, ``projection="jsonl-shadow/v1"`` plus the stored
    ``source`` / ``hash`` / ``original`` record — re-importing an export is
    therefore always rejected. Only ``output_path`` is written.

    An existing file is never clobbered unless it is already a legal export
    of this adapter; legacy/authoritative JSONL is rejected before any write.
    """
    output_path = Path(output_path)
    if output_path.exists() and not _is_adapter_export(output_path):
        raise JsonlShadowError(
            f"refusing to overwrite {output_path}: not a {PROJECTION} export"
        )
    events = broker.read(event_type=SHADOW_EVENT_TYPE, producer=SHADOW_PRODUCER)
    lines = []
    for event in events:
        payload = json.loads(event["payload_json"])
        lines.append(
            json.dumps(
                {
                    "authority": "ledger",
                    "read_only": True,
                    "projection": PROJECTION,
                    "source": payload["source"],
                    "hash": payload["hash"],
                    "original": payload["original"],
                },
                ensure_ascii=False,
                sort_keys=True,
                allow_nan=False,
            )
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return {"exported": len(lines), "output": str(output_path)}


def _set_digest(records_by_hash: dict[str, Any]) -> str:
    """Deterministic SHA-256 over the sorted hash set."""
    digest = hashlib.sha256()
    for record_hash in sorted(records_by_hash):
        digest.update(record_hash.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def compare_jsonl(
    broker: Any, file_path: Path | str, source_id: str | None = None
) -> dict[str, Any]:
    """Compare the source's healthy record set against ledger shadow events.

    Reads the source directly (same classification as import — never via
    import) and compares against the ledger's shadow events for the same
    logical source. Output is deterministic and stable across runs; physical
    duplicates in the source never produce false ``missing`` reports.
    """
    file_path = Path(file_path)
    source = derive_source(file_path, source_id)

    source_by_hash: dict[str, Any] = {}
    source_rows = 0
    duplicate = 0
    quarantined = 0
    healthy, quarantined_entries, _ = _iter_healthy(file_path, source)
    quarantined = len(quarantined_entries)
    for record, record_hash, _line_no in healthy:
        source_rows += 1
        if record_hash in source_by_hash:
            duplicate += 1
        else:
            source_by_hash[record_hash] = record

    ledger_by_hash: dict[str, Any] = {}
    for event in broker.read(event_type=SHADOW_EVENT_TYPE, producer=SHADOW_PRODUCER):
        payload = json.loads(event["payload_json"])
        if payload.get("source") != source:
            continue
        ledger_by_hash[payload["hash"]] = payload.get("original")

    missing = sorted(set(source_by_hash) - set(ledger_by_hash))
    extra = sorted(set(ledger_by_hash) - set(source_by_hash))
    return {
        "source": source,
        "source_rows": source_rows,
        "source_unique": len(source_by_hash),
        "ledger_rows": len(ledger_by_hash),
        "missing": len(missing),
        "extra": len(extra),
        "duplicate": duplicate,
        "quarantined": quarantined,
        "missing_hashes": missing,
        "extra_hashes": extra,
        "source_digest": _set_digest(source_by_hash),
        "ledger_digest": _set_digest(ledger_by_hash),
        "ok": not missing and not extra,
    }


__all__ = [
    "LEGACY_V0",
    "PROJECTION",
    "SHADOW_EVENT_TYPE",
    "SHADOW_PRODUCER",
    "JsonlShadowError",
    "classify_line",
    "compare_jsonl",
    "content_hash",
    "derive_source",
    "export_jsonl",
    "idempotency_key",
    "import_jsonl",
]
