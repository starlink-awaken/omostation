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
from typing import Any
from typing import Optional

SCHEMA = "claims-shadow-preflight/v1"
AUTHORITY_ID = "omo-claims-authority-r0"
ACCEPTED_SPEC_SHA256 = "sha256:b643890f3fda5bee575630018b155fb68ba0ce6f58af9c2b6772a2ff29bb0197"
CLOSURE_PATHS = {
    "spec": "docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md",
    "ledger": "docs/plans/3y-bet-ledger.yaml",
    "policy": ".omo/_truth/registry/swarm-coordination.yaml",
    "helper": "bin/plan/bet-ledger.py",
}

RECOVERY_SCHEMA = "claims-preflight-recovery/v1"
RECOVERY_RULES = {
    "dirty_tracked_closure_path": {
        "classification": "isolated_workspace_recovery",
        "canonical_mutation_required": False,
        "action": (
            "Create a fresh managed clone from the exact origin/main SHA, recursively check out the pinned "
            "child, verify closure objects by digest, and rerun read-only preflight against that clone."
        ),
    },
    "child_source_dirty": {
        "classification": "isolated_workspace_recovery",
        "canonical_mutation_required": False,
        "action": (
            "Use a fresh managed clone and recursively check out pinned child commits; never clean or overwrite "
            "concurrent work in the canonical integration root."
        ),
    },
    "child_head_gitlink_mismatch": {
        "classification": "isolated_workspace_recovery",
        "canonical_mutation_required": False,
        "action": (
            "Verify the child origin/main successor in a fresh clone and require child HEAD to equal the root "
            "gitlink before rerunning preflight."
        ),
    },
    "closure_unreadable": {
        "classification": "isolated_workspace_recovery",
        "canonical_mutation_required": False,
        "action": (
            "Re-read the required closure objects from a fresh exact-main clone and independently compare their "
            "SHA-256 digests; do not synthesize missing files."
        ),
    },
    "accepted_spec_digest_mismatch": {
        "classification": "source_review_required",
        "canonical_mutation_required": True,
        "action": (
            "Stop and compare the accepted Spec digest with the current source through a governed review PR; "
            "never rewrite a historical receipt."
        ),
    },
    "production_verifier_interface_unavailable": {
        "classification": "isolated_workspace_recovery",
        "canonical_mutation_required": False,
        "action": (
            "Import the production verifier closure from a recursively checked-out managed clone and rerun the "
            "read-only preflight."
        ),
    },
    "authority_store_asymmetric_presence": {
        "classification": "operations_triage_required",
        "canonical_mutation_required": False,
        "action": (
            "Quarantine the partial authority directory and require an operator-reviewed recovery transaction; "
            "do not initialize or repair the store automatically."
        ),
    },
    "operation_specific_host_authorization_unproven": {
        "classification": "human_authorization_required",
        "canonical_mutation_required": False,
        "action": (
            "Require a fresh principal authorization packet bound to the exact R0 descriptor before activation; "
            "general approval is not sufficient."
        ),
    },
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
    child_status_rc, child_status = _git(child, "status", "--porcelain", "--untracked-files=no")
    reads_ok = not any((
        first_rc, second_rc, origin_rc, gitlink_rc, child_rc,
        status_rc, child_status_rc,
    ))
    dirty_paths = [
        line[3:].strip() for line in (status.splitlines() if status else [])
        if line.strip()
    ]
    dirty_count = len(dirty_paths)
    closure_path_values = set(CLOSURE_PATHS.values())
    dirty_closure_paths = sorted(path for path in dirty_paths if path in closure_path_values)
    dirty_nonclosure_count = dirty_count - len(dirty_closure_paths)
    child_dirty_count = sum(1 for line in child_status.splitlines() if line.strip())

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

    hard_blockers: list[str] = []
    advisories: list[str] = []
    if not reads_ok:
        hard_blockers.append("git_read_failed")
    else:
        if head_first != head_second:
            hard_blockers.append("root_head_double_read_mismatch")
        if head_first != origin_main:
            advisories.append("root_head_not_equal_origin_main")
        if dirty_count:
            if dirty_closure_paths:
                hard_blockers.append("dirty_tracked_closure_path")
            if dirty_nonclosure_count:
                advisories.append("nonclosure_dirty_tracked_integration_root")
        if child_dirty_count:
            hard_blockers.append("child_source_dirty")
        if child_head != root_gitlink:
            hard_blockers.append("child_head_gitlink_mismatch")
    if any(value is None for value in closure.values()):
        hard_blockers.append("closure_unreadable")
    elif closure.get("spec") != ACCEPTED_SPEC_SHA256:
        hard_blockers.append("accepted_spec_digest_mismatch")
    if verifier_error:
        hard_blockers.append("production_verifier_interface_unavailable")
    if store.exists() != high_water.exists():
        hard_blockers.append("authority_store_asymmetric_presence")

    # No script can prove an external Human decision. Activation callers must
    # separately record and independently verify that decision outside Git.
    authorization_status = "UNPROVEN"
    blockers = [*hard_blockers, "operation_specific_host_authorization_unproven"]
    readiness = "BLOCKED" if hard_blockers else "AWAITING_AUTHORIZATION"
    if not hard_blockers and not reads_ok:
        readiness = "BLOCKED"
    blockers = [*hard_blockers, "operation_specific_host_authorization_unproven"]
    recovery_items: dict[str, dict[str, Any]] = {}
    for blocker in blockers:
        rule = RECOVERY_RULES.get(blocker)
        recovery_items[blocker] = {
            "classification": rule["classification"] if rule else "manual_triage_required",
            "canonical_mutation_required": bool(rule and rule["canonical_mutation_required"]),
            "action": rule["action"] if rule else "Triage with the governance owner before any mutation.",
        }

    recovery = {
        "schema": RECOVERY_SCHEMA,
        "available": True,
        "activation_authorized": False,
        "canonical_workspace_mutation_recommended": any(
            item["canonical_mutation_required"] for item in recovery_items.values()
        ),
        "human_authorization_required": [
            blocker for blocker, item in recovery_items.items()
            if item["classification"] == "human_authorization_required"
        ],
        "isolated_workspace_recovery": [
            blocker for blocker, item in recovery_items.items()
            if item["classification"] == "isolated_workspace_recovery"
        ],
        "remaining_after_isolated_recovery": [
            blocker for blocker, item in recovery_items.items()
            if item["classification"] != "isolated_workspace_recovery"
        ],
        "items": recovery_items,
        "next_safe_action": (
            "Run read-only preflight in a fresh managed exact-main clone; Claims Authority remains inactive."
            if hard_blockers else
            "Keep Claims Authority inactive until a fresh operation-specific principal authorization is verified."
        ),
    }

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
        "dirty_closure_paths": dirty_closure_paths,
        "dirty_nonclosure_count": dirty_nonclosure_count,
        "child_dirty_count": child_dirty_count,
        "closure": closure,
        "runtime_state": {
            "store_exists": store.exists(),
            "highwater_exists": high_water.exists(),
            "activation_witness_exists": witness.exists(),
        },
        "operation_specific_authorization": "UNPROVEN",
        "activation_allowed": False,
        "verifier_error": verifier_error,
        "recovery": recovery,
        "hard_blockers": hard_blockers,
        "advisories": advisories,
        "blockers": blockers,
        "readiness": readiness,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--integration-root",
        type=Path,
        help=(
            "Read-only integration root to observe. Defaults to the canonical workspace. "
            "Use only for an isolated managed exact-main clone."
        ),
    )
    args = parser.parse_args()
    account_home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    integration_root = (
        args.integration_root.expanduser().resolve()
        if args.integration_root else account_home / "Workspace"
    )
    report = collect_preflight(integration_root, account_home=account_home)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if args.json or report["available"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
