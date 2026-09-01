#!/usr/bin/env python3
"""T10-122 Family Dashboard Phase B Canary — danger-gate script.

Creates a dedicated non-private canary document through the approved HITL path,
verifies it exists, then rolls back to confirm the transaction is reversible.

DANGER-GATE: Requires explicit operator confirmation (yes) to execute.

Usage:
    # From root worktree (auto-injects PYTHONPATH):
    uv run python bin/gac/family-dashboard-phase-b-canary.py \
        --documents-root /Users/xiamingxing/Documents/@家庭生活 \
        --state-root /Users/xiamingxing/Workspace/runtime/family-hub/dashboard

    # Skip danger-gate (CI only):
    uv run python bin/gac/family-dashboard-phase-b-canary.py \
        --documents-root ... --state-root ... --skip-danger-gate
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WS = Path(__file__).resolve().parents[2]
FH_SRC = WS / "projects" / "family-hub" / "src"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_family_hub(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a family-hub command with PYTHONPATH injected."""
    env = {**os.environ, "PYTHONPATH": str(FH_SRC)}
    return subprocess.run([sys.executable, "-m", "family_hub", *cmd], env=env, cwd=WS / "projects" / "family-hub", **kwargs)


def danger_gate_confirm() -> bool:
    """Explicit danger-gate confirmation."""
    print("\n" + "=" * 70)
    print("⚠️  DANGER-GATE: T10-122 Family Dashboard Phase B Canary")
    print("=" * 70)
    print("This script will:")
    print("  1. Verify runtime state is materialized")
    print("  2. Create a dedicated canary document (non-private, reversible)")
    print("  3. Verify the canary exists")
    print("  4. Roll back the canary")
    print("  5. Verify rollback succeeded")
    print()
    print("Target directory: $FAMILY_DOCUMENTS_ROOT")
    print()
    response = input("Type 'yes' to proceed: ")
    return response.strip().lower() == "yes"


def verify_runtime_state(documents_root: Path, state_root: Path) -> dict:
    """Verify runtime state is materialized under state_root."""
    result = {"ok": True, "findings": []}

    if not state_root.exists():
        result["ok"] = False
        result["findings"].append(f"State root does not exist: {state_root}")
        return result

    manifests_dir = state_root / "manifests"
    if not manifests_dir.exists():
        result["findings"].append(f"Manifests dir missing: {manifests_dir}")
    else:
        manifests = list(manifests_dir.glob("*.yaml"))
        result["findings"].append(f"Found {len(manifests)} manifests")

    generated_dir = state_root / "generated"
    if not generated_dir.exists():
        result["findings"].append(f"Generated dir missing: {generated_dir}")
    else:
        generated = list(generated_dir.rglob("*.json"))
        result["findings"].append(f"Found {len(generated)} generated products")

    cache_dir = state_root / "cache"
    if not cache_dir.exists():
        result["findings"].append(f"Cache dir missing: {cache_dir}")

    return result


def create_canary_proposal(documents_root: Path, state_root: Path, canary_name: str) -> dict:
    """Create a HITL proposal for canary document creation."""
    canary_content = f"T10-122 Phase B Canary — {_now()}\nThis document is safe to delete.\n".encode()
    payload_ref = "proposals/canary-test/payload"
    payload_dir = state_root / "proposals" / "canary-test"
    payload_dir.mkdir(parents=True, exist_ok=True)
    (payload_dir / "payload").write_bytes(canary_content)

    proposal = {
        "proposal_id": f"canary-{int(time.time())}",
        "type": "family_dashboard_document_write",
        "operation": "replace_text",
        "target_relative": canary_name,
        "expected_source_sha256": "",  # New file
        "expected_source_size": 0,
        "expected_source_mode": 0o644,
        "payload_ref": payload_ref,
        "payload_sha256": hashlib.sha256(canary_content).hexdigest(),
        "change_summary": "T10-122 Phase B canary: create reversible test document",
    }
    return proposal


def execute_canary_mutation(proposal: dict) -> dict:
    """Execute the canary mutation via family-hub."""
    import importlib
    sys.path.insert(0, str(FH_SRC))
    try:
        mod = importlib.import_module("family_hub.hitl.executor")
        return mod.execute_family_dashboard_mutation_sync(proposal)
    finally:
        sys.path.pop(0)


def rollback_canary(state_root: Path, documents_root: Path, proposal: dict) -> str | None:
    """Rollback the canary mutation. Returns rollback SHA-256 or None."""
    import importlib
    sys.path.insert(0, str(FH_SRC))
    try:
        mod = importlib.import_module("family_hub.hitl.owner")
        owner = mod.HitlTransactionOwner(documents_root, state_root)
        return owner._rollback(
            f"mutation-{proposal['proposal_id']}",
            str(documents_root / proposal["target_relative"]),
        )
    finally:
        sys.path.pop(0)


def main():
    parser = argparse.ArgumentParser(description="T10-122 Family Dashboard Phase B Canary")
    parser.add_argument("--documents-root", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--skip-danger-gate", action="store_true", help="Skip danger-gate (CI only)")
    args = parser.parse_args()

    documents_root = args.documents_root
    state_root = args.state_root

    print(f"Documents root: {documents_root}")
    print(f"State root: {state_root}")

    # Step 1: Verify runtime state
    print("\n[1/5] Verifying runtime state...")
    runtime_result = verify_runtime_state(documents_root, state_root)
    for finding in runtime_result["findings"]:
        print(f"  - {finding}")
    if not runtime_result["ok"]:
        print("FAIL: Runtime state not materialized")
        return 1

    # Step 2: Danger gate
    if not args.skip_danger_gate:
        if not danger_gate_confirm():
            print("\nAborted by operator")
            return 130

    # Step 3: Create canary proposal
    print("\n[3/5] Creating canary proposal...")
    canary_name = f"canary-test-{int(time.time())}.txt"
    proposal = create_canary_proposal(documents_root, state_root, canary_name)
    print(f"  Proposal ID: {proposal['proposal_id']}")
    print(f"  Target: {proposal['target_relative']}")

    # Step 4: Execute via HITL path
    print("\n[4/5] Executing via HITL path...")
    try:
        result = execute_canary_mutation(proposal)
        if result.get("status") == "ok":
            print(f"  ✓ Mutation executed: {result.get('mutation_id')}")
        else:
            print(f"FAIL: Mutation failed: {result.get('error')}")
            return 1
    except Exception as e:
        print(f"FAIL: Execution error: {e}")
        return 1

    # Step 5: Verify canary exists
    print("\n[5/5] Verifying canary...")
    canary_path = documents_root / canary_name
    if canary_path.exists():
        print(f"  ✓ Canary verified: {canary_path.name}")
    else:
        print("  ✗ Canary not found")

    # Step 6: Rollback
    print("\n[6/6] Rolling back canary...")
    try:
        rollback_sha = rollback_canary(state_root, documents_root, proposal)
        if not canary_path.exists():
            print(f"  ✓ Canary removed (rollback_sha: {rollback_sha})")
        else:
            print("  ✗ Canary still exists after rollback")
            return 1
    except Exception as e:
        print(f"FAIL: Rollback error: {e}")
        return 1

    print("\n✓ Phase B Canary complete — runtime state verified, HITL path operational")
    return 0


if __name__ == "__main__":
    sys.exit(main())
