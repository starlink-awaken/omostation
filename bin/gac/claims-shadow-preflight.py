#!/usr/bin/env python3
"""Read-only Claims Authority WP1 Task 16 preflight.

This command never activates, repairs, initializes, fetches, rebases or mutates
the authority store. It reports whether the fixed canonical integration root is
coherent enough for a separately authorized host activation decision.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import pwd
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from typing import Any

SCHEMA = "claims-shadow-preflight/v1"
AUTHORITY_ID = "omo-claims-authority-r0"
ACCEPTED_SPEC_SHA256 = "sha256:b643890f3fda5bee575630018b155fb68ba0ce6f58af9c2b6772a2ff29bb0197"
CLOSURE_PATHS = {
    "spec": "docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md",
    "ledger": "docs/plans/3y-bet-ledger.yaml",
    "policy": ".omo/_truth/registry/swarm-coordination.yaml",
    "helper": "bin/plan/bet-ledger.py",
}


def _git(root: Path, *args: str) -> tuple[int, str]:
    result = subprocess.run(
        ["git", "-C", str(root), *args], text=True, capture_output=True, check=False
    )
    return result.returncode, (result.stdout or result.stderr).strip()


def _sha256(path: Path) -> Optional[str]:
    try:
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _load_verifiers(root: Path) -> Any:
    source_root = root / "projects/omo/src"
    sys.path.insert(0, str(source_root))
    try:
        module = importlib.import_module("omo.workflow.claims_verifiers")
    finally:
        try:
            sys.path.remove(str(source_root))
        except ValueError:
            pass
    return module


def collect_preflight(
    root: Path,
    *,
    account_home: Path,
    observed_at: Optional[str] = None,
    verifiers: Any = None,
) -> dict:
    root = root.resolve()
    account_home = account_home.resolve()
    checked_at = observed_at or datetime.now(timezone.utc).isoformat()
    child = root / "projects/omo"

    first_rc, head_first = _git(root, "rev-parse", "HEAD")
    second_rc, head_second = _git(root, "rev-parse", "HEAD")
    origin_rc, origin_main = _git(root, "rev-parse", "origin/main")
    gitlink_rc, root_gitlink = _git(root, "rev-parse", "HEAD:projects/omo")
    child_rc, child_head = _git(child, "rev-parse", "HEAD")
    status_rc, status = _git(root, "status", "--porcelain", "--untracked-files=no")
    reads_ok = not any((first_rc, second_rc, origin_rc, gitlink_rc, child_rc, status_rc))
    dirty_count = sum(1 for line in status.splitlines() if line.strip()) if status else 0

    closure: dict[str, str | None] = {
        label: _sha256(root / relative) for label, relative in CLOSURE_PATHS.items()
    }
    try:
        if verifiers is None:
            verifiers = _load_verifiers(root)
        closure["operator_authorization_verifier_digest"] = (
            verifiers.operator_authorization_verifier_digest()
        )
        closure["stopped_process_verifier_digest"] = (
            verifiers.stopped_process_verifier_digest()
        )
        closure["production_verifier_closure_digest"] = (
            verifiers.production_verifier_closure_digest()
        )
        verifier_error = None
    except Exception as exc:  # noqa: BLE001 - preflight must report, not crash
        verifier_error = type(exc).__name__

    authority_dir = account_home / "agents/_shared/runtime" / AUTHORITY_ID
    store = authority_dir / "store.sqlite3"
    high_water = authority_dir / "highwater.json"
    witness = authority_dir / "activation-witness.json"

    blockers: list[str] = []
    if not reads_ok:
        blockers.append("git_read_failed")
    else:
        if head_first != head_second:
            blockers.append("root_head_double_read_mismatch")
        if head_first != origin_main:
            blockers.append("root_head_not_equal_origin_main")
        if dirty_count:
            blockers.append("dirty_tracked_integration_root")
        if child_head != root_gitlink:
            blockers.append("child_head_gitlink_mismatch")
    if any(value is None for value in closure.values()):
        blockers.append("closure_unreadable")
    elif closure.get("spec") != ACCEPTED_SPEC_SHA256:
        blockers.append("accepted_spec_digest_mismatch")
    if verifier_error:
        blockers.append("production_verifier_interface_unavailable")
    if store.exists() != high_water.exists():
        blockers.append("authority_store_asymmetric_presence")

    # No script can prove an external Human decision. Activation callers must
    # separately record and independently verify that decision outside Git.
    blockers.append("operation_specific_host_authorization_unproven")
    return {
        "schema": SCHEMA,
        "authority_id": AUTHORITY_ID,
        "checked_at": checked_at,
        "available": True,
        "root_head_oid": head_first if first_rc == 0 else None,
        "origin_main_oid": origin_main if origin_rc == 0 else None,
        "child_head_oid": child_head if child_rc == 0 else None,
        "root_child_gitlink_oid": root_gitlink if gitlink_rc == 0 else None,
        "dirty_tracked_count": dirty_count,
        "closure": closure,
        "runtime_state": {
            "store_exists": store.exists(),
            "highwater_exists": high_water.exists(),
            "activation_witness_exists": witness.exists(),
        },
        "operation_specific_authorization": "UNPROVEN",
        "activation_allowed": False,
        "blockers": blockers,
        "readiness": "BLOCKED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    account_home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    integration_root = account_home / "Workspace"
    report = collect_preflight(integration_root, account_home=account_home)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if args.json or report["available"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
