"""OMO Event Ledger CLI — governance snapshot + causal event ledger bridge.

Legacy mode (backward compatible)::

    omo ledger [--message "Commit reason"]

New subcommand mode::

    omo ledger append --event-type T.v1 --producer p --payload '{"k":"v"}'
    omo ledger read [--from 1] [--limit 10]
    omo ledger verify [--from 1]
    omo ledger status

Agora stdio mode (--agora)::

    Reads stdin JSON envelope as ``{"args": [...], "kwargs": {...}}``
    (real Agora StdioAdapter contract).  Unwraps ``kwargs.arguments``.
    Success → pure JSON on stdout.  Nonzero → stable JSON receipt on stderr.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .event_ledger.broker import DuplicateEventError, LedgerError
from .event_ledger.surface import (
    AgoraValidationError,
    EventLedgerSurface,
    emit_receipt,
    parse_agora_stdin,
)
from .omo_paths import find_omo_dir
from .omo_shared import load_yaml, write_yaml

# ---------------------------------------------------------------------------
# Legacy governance snapshot (unchanged behaviour)
# ---------------------------------------------------------------------------


def get_omo_dir(base_dir: Path) -> Path:
    return find_omo_dir(base_dir)


def _legacy_snapshot(omo_dir: Path, message: str) -> int:
    now = datetime.now(UTC)
    timestamp = now.strftime("%Y%m%d-%H%M%S")

    ledger_dir = omo_dir / "_delivery" / "governance-evidence" / "ledgers"
    ledger_dir.mkdir(parents=True, exist_ok=True)

    system_yaml = omo_dir / "state" / "system.yaml"
    goals_yaml = omo_dir / "goals" / "current.yaml"
    debt_yaml = omo_dir / "debt" / "dashboard" / "current.yaml"

    snapshot = {
        "timestamp": now.isoformat(),
        "message": message,
        "metrics": {
            "active_tasks": len(list((omo_dir / "tasks" / "active").glob("*.yaml")))
            if (omo_dir / "tasks" / "active").exists()
            else 0,
            "planned_tasks": len(list((omo_dir / "tasks" / "planned").glob("*.yaml")))
            if (omo_dir / "tasks" / "planned").exists()
            else 0,
        },
        "system_state": load_yaml(system_yaml) if system_yaml.exists() else None,
        "goals": load_yaml(goals_yaml) if goals_yaml.exists() else None,
        "debt": load_yaml(debt_yaml) if debt_yaml.exists() else None,
    }

    ledger_file = ledger_dir / f"ledger-{timestamp}.yaml"
    write_yaml(ledger_file, snapshot)
    print(f"✅ 台账记录已生成: {ledger_file}")

    latest_file = ledger_dir / "ledger-latest.yaml"
    shutil.copy(ledger_file, latest_file)
    return 0


SUBCMDS = frozenset({"append", "read", "verify", "status"})

# Allowed fields per subcommand (for Agora envelope validation).
# "db" is always allowed as it's a common flag.
_AGORA_ALLOWED = {
    "append": frozenset(
        {
            "event_type",
            "producer",
            "principal_id",
            "space_id",
            "correlation_id",
            "idempotency_key",
            "payload",
            "episode_id",
            "role_context_id",
            "responsibility_id",
            "mandate_id",
            "causation_id",
            "occurred_at",
            "privacy_class",
            "schema_version",
            "evidence_uri",
            "event_id",
        }
    ),
    "read": frozenset(
        {
            "from_sequence",
            "to_sequence",
            "limit",
            "event_type",
            "producer",
            "episode_id",
        }
    ),
    "verify": frozenset({"from_sequence", "to_sequence"}),
    "status": frozenset(),
}


def main(argv: list[str]) -> int:
    # Subcommand is valid only when argv[0] itself is one of SUBCMDS.
    if argv and argv[0] in SUBCMDS:
        return _subcommand_main(argv)
    return _legacy_main(argv)


# ---------------------------------------------------------------------------
# Legacy entry point — unchanged API
# ---------------------------------------------------------------------------


def _legacy_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="OMO Governance Ledger snapshot")
    parser.add_argument(
        "--message",
        type=str,
        default="Routine Governance Snapshot",
        help="Ledger commit reason",
    )
    args = parser.parse_args(argv)
    omo_dir = get_omo_dir(Path.cwd())
    if not omo_dir.exists():
        print(f"Error: {omo_dir} not found.")
        return 1
    print(f"📖 记录 OMO 治理台账 (Ledger) - 目标: {omo_dir}")
    return _legacy_snapshot(omo_dir, args.message)


# ---------------------------------------------------------------------------
# Subcommand entry point
# ---------------------------------------------------------------------------


def _build_subcommand_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="OMO Causal Event Ledger — append, read, verify, status"
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    pa = sub.add_parser("append", help="Append an event to the ledger")
    pa.add_argument("--event-type", default="GovernanceEvent.v1")
    pa.add_argument("--producer", default="omo-ledger-cli")
    pa.add_argument("--principal-id", default="omo-governance")
    pa.add_argument("--space-id", default="default")
    pa.add_argument("--correlation-id", default=None)
    pa.add_argument("--idempotency-key", default=None)
    pa.add_argument("--payload", default=None, help="JSON string or '-' for stdin")
    pa.add_argument("--payload-file", default=None, help="Read payload JSON from file")
    pa.add_argument("--episode-id", default=None)
    pa.add_argument("--role-context-id", default=None)
    pa.add_argument("--responsibility-id", default=None)
    pa.add_argument("--mandate-id", default=None)
    pa.add_argument("--causation-id", default=None)
    pa.add_argument("--occurred-at", default=None)
    pa.add_argument("--privacy-class", default=None)
    pa.add_argument("--evidence-uri", default=None)
    pa.add_argument("--event-id", default=None)
    _add_common_flags(pa)

    pr = sub.add_parser("read", help="Read events from the ledger")
    pr.add_argument("--from", dest="from_sequence", type=int, default=1)
    pr.add_argument("--to", dest="to_sequence", type=int, default=None)
    pr.add_argument("--limit", type=int, default=None)
    pr.add_argument("--event-type", default=None)
    pr.add_argument("--producer", default=None)
    pr.add_argument("--episode-id", default=None)
    _add_common_flags(pr)

    pv = sub.add_parser("verify", help="Verify the hash chain integrity")
    pv.add_argument("--from", dest="from_sequence", type=int, default=1)
    pv.add_argument("--to", dest="to_sequence", type=int, default=None)
    _add_common_flags(pv)

    ps = sub.add_parser("status", help="Show ledger status")
    _add_common_flags(ps)

    return parser


def _add_common_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--db", default=None, help="Explicit database path")
    p.add_argument(
        "--agora",
        action="store_true",
        help="Read args from stdin JSON envelope, emit receipt",
    )
    p.add_argument("--json", action="store_true", help="Emit JSON output")


# ---------------------------------------------------------------------------
# Agora envelope processing (CLI policy layer)
# ---------------------------------------------------------------------------


def _load_payload(params: dict[str, Any]) -> dict[str, Any] | None:
    """Resolve payload from --payload, --payload-file, or inline dict.

    Returns a dict on success, raises AgoraValidationError(payload_type) for
    any non-mapping decoded or inline value (no traceback, no DB mutation),
    and raises AgoraValidationError(payload_parse/payload_file) for parse
    failures.  ``null`` maps to ``{}``.
    """
    payload_file = params.pop("payload_file", None)
    raw = params.pop("payload", None)
    if raw is None:
        # No --payload; try payload-file, then fall through.
        pass
    elif isinstance(raw, dict):
        return raw
    elif raw == "-":
        raw = sys.stdin.read().strip()
        if raw:
            return _decode_payload(raw, source="payload")
        return None
    elif isinstance(raw, str):
        if raw.strip():
            return _decode_payload(raw, source="payload")
        return None
    else:
        # Non-string, non-dict, non-None: array, number, bool, etc.
        raise AgoraValidationError(
            "payload_type",
            f"payload must be a JSON object, got {type(raw).__name__}",
        )

    if payload_file:
        try:
            decoded = json.loads(Path(payload_file).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AgoraValidationError(
                "payload_file", f"payload file not valid JSON: {exc}"
            ) from None
        except OSError as exc:
            raise AgoraValidationError(
                "payload_file", f"cannot read payload file: {exc}"
            ) from None
        if not isinstance(decoded, dict):
            raise AgoraValidationError(
                "payload_type",
                f"payload file must contain a JSON object, got {type(decoded).__name__}",
            )
        return decoded

    return None


def _decode_payload(raw: str, source: str) -> dict[str, Any]:
    """Decode a raw JSON string into a payload dict; fail on non-mapping."""
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AgoraValidationError(
            "payload_parse", f"{source} is not valid JSON: {exc}"
        ) from None
    if isinstance(decoded, dict):
        return decoded
    if decoded is None:
        return {}
    raise AgoraValidationError(
        "payload_type",
        f"{source} must be a JSON object, got {type(decoded).__name__}",
    )


def _validate_agora_fields(subcmd: str, incoming: dict[str, Any]) -> None:
    """Reject unknown Agora fields before any DB mutation."""
    allowed = _AGORA_ALLOWED.get(subcmd, frozenset()) | {"db"}
    for key in incoming:
        if key not in allowed:
            raise AgoraValidationError(
                "unknown_field", f"unknown field '{key}' for subcommand '{subcmd}'"
            )


def _validate_and_normalize_agora_values(
    subcmd: str, incoming: dict[str, Any]
) -> dict[str, Any]:
    """Reject invalid types/ranges. Returns normalized dict.

    Args are not from argparse — they must be validated explicitly.
    db, string fields, and integer fields are checked per subcommand.
    """
    normalized: dict[str, Any] = {}

    # -- db --------------------------------------------------------------
    db_val = incoming.get("db")
    if db_val is not None:
        if not isinstance(db_val, str) or not db_val.strip():
            raise AgoraValidationError(
                "invalid_field",
                f"db must be a nonempty string, got {type(db_val).__name__}",
            )
        normalized["db"] = db_val

    # -- read / verify integer fields ------------------------------------
    for key in ("from_sequence", "to_sequence", "limit"):
        val = incoming.get(key)
        if val is None:
            continue
        if isinstance(val, bool) or not isinstance(val, int):
            raise AgoraValidationError(
                "invalid_field", f"'{key}' must be an integer, got {type(val).__name__}"
            )
        if val < 1:
            raise AgoraValidationError(
                "invalid_field", f"'{key}' must be >= 1, got {val}"
            )
        normalized[key] = val

    # -- read string-or-null fields --------------------------------------
    for key in ("event_type", "producer", "episode_id"):
        val = incoming.get(key)
        if val is None:
            continue
        if not isinstance(val, str):
            raise AgoraValidationError(
                "invalid_field",
                f"'{key}' must be a string or null, got {type(val).__name__}",
            )
        normalized[key] = val

    # -- append string-or-null metadata (allowed fields minus payload) ---
    append_meta = _AGORA_ALLOWED["append"] - {"payload"}
    for key in append_meta:
        val = incoming.get(key)
        if val is None:
            continue
        if not isinstance(val, str):
            raise AgoraValidationError(
                "invalid_field",
                f"'{key}' must be a string or null, got {type(val).__name__}",
            )
        normalized[key] = val

    # -- payload (delegated to _load_payload — sole policy owner) --------
    if "payload" in incoming:
        normalized["payload"] = incoming["payload"]

    return normalized


def _process_agora_args(subcmd: str, args_list: list[Any]) -> dict[str, Any]:
    """Validate and normalize positional Agora args for the fixed subcommand.

    Rules:
      - args=[] → return empty dict (all params from kwargs/CLI)
      - args=[single_mapping] → return the mapping
      - anything else → raise AgoraValidationError
    """
    if not args_list:
        return {}
    if len(args_list) == 1 and isinstance(args_list[0], dict):
        return dict(args_list[0])
    raise AgoraValidationError(
        "args_shape",
        "positional args must be empty or a single mapping object",
    )


def _subcommand_main(argv: list[str]) -> int:
    parser = _build_subcommand_parser()
    parsed = parser.parse_args(argv)

    is_agora = parsed.agora
    is_json = parsed.json

    params = dict(vars(parsed))
    subcmd = params.pop("subcommand")
    db_path = params.pop("db", None)
    params.pop("agora", None)
    params.pop("json", None)

    # --agora: parse stdin, validate, merge
    if is_agora:
        try:
            args_list, kwargs_dict = parse_agora_stdin()
        except AgoraValidationError as exc:
            _emit_error(
                {"ok": False, "error": exc.message, "reason": exc.reason},
                is_agora=is_agora,
                is_json=is_json,
            )
            return 1

        # Positional args: only empty or single mapping; the CLI subcommand is authoritative.
        try:
            positional_mapping = _process_agora_args(subcmd, args_list)
        except AgoraValidationError as exc:
            _emit_error(
                {"ok": False, "error": exc.message, "reason": exc.reason},
                is_agora=is_agora,
                is_json=is_json,
            )
            return 1

        # Reject ambiguity: positional mapping + nonempty kwargs
        if positional_mapping and kwargs_dict:
            _emit_error(
                {
                    "ok": False,
                    "error": "ambiguous: both positional args and kwargs present",
                    "reason": "ambiguous_args",
                },
                is_agora=is_agora,
                is_json=is_json,
            )
            return 1

        # Determine which dict to validate and merge: positional mapping or kwargs
        incoming = positional_mapping or kwargs_dict

        # Unknown field detection
        try:
            _validate_agora_fields(subcmd, incoming)
        except AgoraValidationError as exc:
            _emit_error(
                {"ok": False, "error": exc.message, "reason": exc.reason},
                is_agora=is_agora,
                is_json=is_json,
            )
            return 1

        # Type/range validation (Agora bypasses argparse)
        try:
            incoming = _validate_and_normalize_agora_values(subcmd, incoming)
        except AgoraValidationError as exc:
            _emit_error(
                {"ok": False, "error": exc.message, "reason": exc.reason},
                is_agora=is_agora,
                is_json=is_json,
            )
            return 1

        # Extract envelope db before merging (db is validated but is a
        # connection parameter, not a data field).
        envelope_db = incoming.pop("db", None)
        if envelope_db is not None:
            if db_path is not None and db_path != envelope_db:
                _emit_error(
                    {
                        "ok": False,
                        "error": f"CLI --db={db_path} conflicts with envelope db={envelope_db}",
                        "reason": "ambiguous_db",
                    },
                    is_agora=is_agora,
                    is_json=is_json,
                )
                return 1
            db_path = envelope_db

        # Merge remaining fields into params (overriding CLI defaults)
        params.update(incoming)

    try:
        surface = EventLedgerSurface(db_path=db_path)
    except Exception as exc:
        _emit_error(
            {
                "ok": False,
                "error": f"failed to open ledger: {exc}",
                "reason": "open_error",
            },
            is_agora=is_agora,
            is_json=is_json,
        )
        return 1

    try:
        if subcmd == "append":
            return _cmd_append(surface, params, is_json, is_agora)
        elif subcmd == "read":
            return _cmd_read(surface, params, is_json, is_agora)
        elif subcmd == "verify":
            return _cmd_verify(surface, params, is_json, is_agora)
        elif subcmd == "status":
            return _cmd_status(surface, is_json, is_agora)
        else:
            _emit_error(
                {
                    "ok": False,
                    "error": f"Unknown subcommand: {subcmd}",
                    "reason": "unknown_subcommand",
                },
                is_agora=is_agora,
                is_json=is_json,
            )
            return 1
    except AgoraValidationError as exc:
        _emit_error(
            {"ok": False, "error": exc.message, "reason": exc.reason},
            is_agora=is_agora,
            is_json=is_json,
        )
        return 1
    except DuplicateEventError as exc:
        _emit_error(
            {"ok": False, "error": str(exc), "reason": "duplicate_event"},
            is_agora=is_agora,
            is_json=is_json,
        )
        return 1
    except LedgerError as exc:
        _emit_error(
            {"ok": False, "error": str(exc), "reason": "ledger_error"},
            is_agora=is_agora,
            is_json=is_json,
        )
        return 1
    finally:
        surface.close()


def _cmd_append(
    surface: EventLedgerSurface, params: dict[str, Any], is_json: bool, is_agora: bool
) -> int:
    payload = _load_payload(params)
    if payload is not None:
        params["payload"] = payload
    elif "payload" in params and params["payload"] is None:
        params["payload"] = {}

    # Pull only known kwargs for the append surface
    allowed = _AGORA_ALLOWED["append"]
    kwargs = {k: v for k, v in params.items() if k in allowed and v is not None}
    # Default fields from argparse must still flow through
    for k in ("event_type", "producer", "principal_id", "space_id"):
        if params.get(k) is not None:
            kwargs.setdefault(k, params[k])

    result = surface.append(**kwargs)
    _emit_receipt(
        {"ok": True, **result.to_dict(), "db_path": str(surface.db_path)},
        is_json,
        is_agora,
    )
    return 0


def _cmd_read(
    surface: EventLedgerSurface, params: dict[str, Any], is_json: bool, is_agora: bool
) -> int:
    result = surface.read(
        from_sequence=params.get("from_sequence", 1),
        to_sequence=params.get("to_sequence"),
        limit=params.get("limit"),
        event_type=params.get("event_type"),
        producer=params.get("producer"),
        episode_id=params.get("episode_id"),
    )
    _emit_receipt(
        {"ok": True, **result.to_dict(), "db_path": str(surface.db_path)},
        is_json,
        is_agora,
    )
    return 0


def _cmd_verify(
    surface: EventLedgerSurface, params: dict[str, Any], is_json: bool, is_agora: bool
) -> int:
    result = surface.verify(
        from_sequence=params.get("from_sequence", 1),
        to_sequence=params.get("to_sequence"),
    )
    _emit_receipt(
        {"ok": result.ok, **result.to_dict(), "db_path": str(surface.db_path)},
        is_json,
        is_agora,
    )
    return 0 if result.ok else 1


def _cmd_status(surface: EventLedgerSurface, is_json: bool, is_agora: bool) -> int:
    result = surface.status()
    _emit_receipt(
        {"ok": True, **result.to_dict(), "db_path": str(surface.db_path)},
        is_json,
        is_agora,
    )
    return 0


# ---------------------------------------------------------------------------
# Receipt emission (CLI policy: maps ok/stderr/stdout)
# ---------------------------------------------------------------------------


def _emit_error(receipt: dict[str, Any], *, is_agora: bool, is_json: bool) -> None:
    """Emit an error receipt. --agora → stderr; --json → stdout; else → stderr."""
    out = emit_receipt(receipt)
    if is_agora:
        print(out, file=sys.stderr)
    elif is_json:
        print(out)
    else:
        print(out, file=sys.stderr)


def _emit_receipt(receipt: dict[str, Any], is_json: bool, is_agora: bool) -> None:
    """Emit a success/result receipt. --agora success → stdout."""
    out = emit_receipt(receipt)
    if is_agora or is_json:
        print(out)
    else:
        print(out)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
