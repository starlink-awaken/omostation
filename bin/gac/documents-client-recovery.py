#!/usr/bin/env python3
"""Plan, apply, verify, or roll back Documents client recovery relocation."""

# ruff: noqa: UP006, UP035, UP045 -- this host tool must parse on Python 3.9.

from __future__ import annotations

import argparse
import json
import stat
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.documents_client_recovery_relocation import (  # noqa: E402
    ERROR_SCHEMA,
    RelocationError,
    RelocationPaths,
    apply_relocation,
    plan_relocation,
    rollback_relocation,
    verify_relocation,
)

DEFAULT_DOCUMENTS_ROOT = Path.home() / "Documents"
DEFAULT_SOURCE_RELATIVES = (".codex-optimize-log", ".cc-switch-recovery2")
DEFAULT_TARGET_ROOT = (
    Path.home() / "Library" / "Application Support" / "CC_Switch Recovery" / "2026-08-30"
)
DEFAULT_ROLLBACK_RECEIPT = DEFAULT_TARGET_ROOT.parent / "2026-08-30.rollback-receipt.json"


def _load_json_mapping(path: Path, label: str) -> Dict[str, Any]:
    try:
        metadata = path.lstat()
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RelocationError(label + " is unavailable or malformed", code="CONSUMER_RECEIPT_INVALID") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode) or not isinstance(payload, dict):
        raise RelocationError(label + " must be a regular JSON object", code="CONSUMER_RECEIPT_INVALID")
    return payload


def _paths(args: argparse.Namespace) -> RelocationPaths:
    documents = args.documents_root.expanduser().absolute()
    relative_values: Sequence[str] = args.source_relative or DEFAULT_SOURCE_RELATIVES
    sources = tuple(documents / value for value in relative_values)
    if len(sources) != 2:
        raise RelocationError("exactly two source roots are required", code="SOURCE_ROOT_SET_INVALID")
    source_roots: Tuple[Path, Path] = (sources[0], sources[1])
    return RelocationPaths(
        documents_root=documents,
        source_roots=source_roots,
        target_root=args.target_root.expanduser().absolute(),
        rollback_receipt=args.rollback_receipt.expanduser().absolute(),
    )


def _consumer_receipt(args: argparse.Namespace) -> Dict[str, Any]:
    if args.consumer_receipt is None:
        raise RelocationError("consumer receipt is required", code="CONSUMER_RECEIPT_REQUIRED")
    return _load_json_mapping(args.consumer_receipt.expanduser().absolute(), "consumer receipt")


def _execute(args: argparse.Namespace) -> Dict[str, Any]:
    paths = _paths(args)
    if args.command == "plan":
        return plan_relocation(paths, consumer_receipt=_consumer_receipt(args))
    if args.command == "apply":
        return apply_relocation(paths, consumer_receipt=_consumer_receipt(args))
    if args.command == "verify":
        return verify_relocation(paths, consumer_receipt=_consumer_receipt(args))
    if args.command == "rollback":
        return rollback_relocation(paths)
    raise RelocationError("unknown command", code="COMMAND_INVALID")


def _error_payload(command: str, error: Exception) -> Dict[str, Any]:
    code = error.code if isinstance(error, RelocationError) else "RELOCATION_FAILED"
    return {
        "schema": ERROR_SCHEMA,
        "status": "error",
        "code": code,
        "command": command,
        "error": str(error),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "apply", "verify", "rollback"))
    parser.add_argument("--documents-root", type=Path, default=DEFAULT_DOCUMENTS_ROOT)
    parser.add_argument("--source-relative", action="append")
    parser.add_argument("--target-root", type=Path, default=DEFAULT_TARGET_ROOT)
    parser.add_argument("--rollback-receipt", type=Path, default=DEFAULT_ROLLBACK_RECEIPT)
    parser.add_argument("--consumer-receipt", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = _execute(args)
    except (OSError, RelocationError) as exc:
        print(json.dumps(_error_payload(args.command, exc), ensure_ascii=False, indent=2, sort_keys=True))
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.json else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
