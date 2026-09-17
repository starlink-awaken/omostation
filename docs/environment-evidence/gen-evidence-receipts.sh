#!/usr/bin/env bash
# gen-evidence-receipts.sh — generate digest-bound receipts for A1-A9 + RF0.
#
# All JSON is emitted by Python's json serializer so gate output containing
# quotes or braces cannot create malformed receipts (the A4 regression).
# Default output remains the governance evidence plane; set
# EVIDENCE_OUTPUT_DIR to refresh the tracked documentation snapshot in a
# managed worktree.

set -euo pipefail

WS_ROOT="$(git rev-parse --show-toplevel)"
OUTPUT_DIR="${EVIDENCE_OUTPUT_DIR:-$WS_ROOT/.omo/_delivery/environment-evidence}"
mkdir -p "$OUTPUT_DIR"

python3 - "$WS_ROOT" "$OUTPUT_DIR" <<'PY'
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ws_root = Path(sys.argv[1]).resolve()
output_dir = Path(sys.argv[2]).resolve()
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
gate_health_path = output_dir / "_gate-health.json"
panorama_path = output_dir / "_panorama-gates.json"
gate_health_source = os.environ.get("GATE_HEALTH_INPUT")
panorama_source = os.environ.get("PANORAMA_GATES_INPUT")


def run_json(command: list[str], fallback) -> object:
    result = subprocess.run(command, cwd=ws_root, capture_output=True, text=True)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return fallback


if gate_health_source:
    gate_health = json.loads(Path(gate_health_source).read_text(encoding="utf-8"))
else:
    gate_health = run_json(
        [sys.executable, "bin/gac/gate-health-check.py", "--json"],
        {"all_ok": False, "error": "gate-health-check failed"},
    )
if panorama_source:
    panorama_gates = json.loads(Path(panorama_source).read_text(encoding="utf-8"))
else:
    panorama_gates = run_json(
        [sys.executable, "bin/panorama/panorama-collect.py", "--gates"],
        [],
    )

gate_health_path.write_text(
    json.dumps(gate_health, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
panorama_path.write_text(
    json.dumps(panorama_gates, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)

gate_digest = "sha256:" + hashlib.sha256(gate_health_path.read_bytes()).hexdigest()
panorama_by_id = {gate.get("id"): gate for gate in panorama_gates if gate.get("id")}

exit_criteria = {
    "A1": "workflow_admission_satisfied;pasw_branch_compliance;git_push_drift_zero",
    "A2": "resident_cell_pool_alive;host_memory_pressure_normal;workspace_lock_clean",
    "A3": "governance_python_managed;harness_section_compliance;mo_consistency_pass",
    "A4": "scheduler_drift_zero;launchd_loaded_count_consistent;cron_orphans_zero",
    "A5": "submodule_fresh_within_7d;reference_alignment_pass;launchd_keepalive_active",
    "A6": "orca_r0_live_no_state_drift;r0_evidence_digest_signed;readonly_admission_test_pass",
    "A7": "multica_as0_alive_no_drift;digest_chain_consistent;readonly_admission_test_pass",
    "A8": "oma_external_transaction_schema_signed;durable_queue_persistence_verified;as0_to_a8_replay_match",
    "A9": "asd_dashboard_live;cockpit_observatory_aligned;live_evidence_refresh_within_5min",
    "RF0": "ruflo_readonly_collaboration_live;no_second_queue_created;cross_agent_dependency_zero",
}
owners = {
    "A1": "governance-agent",
    "A2": "omo-runtime-team",
    "A3": "governance-team",
    "A4": "scheduler-agent",
    "A5": "infra-team",
    "A6": "orca-team",
    "A7": "multica-team",
    "A8": "omo-runtime-team",
    "A9": "observability-team",
    "RF0": "ruflo-team",
}
not_admitted_legal_states = "NOT_ADMITTED 合法 (A6/A7/RF0 设计如此, 非缺陷)"
unlock_conditions = {
    "A6": "T10-149 完成 R0 验收测试 + signoff",
    "A7": "T10-150 完成 AS0 验收测试 + signoff",
    "RF0": "side-effect-free 观察保持, 不建第二队列",
}

receipts_path = output_dir / "receipts.jsonl"
with receipts_path.open("w", encoding="utf-8") as receipts:
    for gate_id in ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "RF0"):
        projection = panorama_by_id.get(gate_id, {})
        verdict = projection.get("verdict", "UNKNOWN")
        status = "proven" if verdict == "PASS" else "missing"
        receipt = {
            "gate_id": gate_id,
            "status": status,
            "verdict": verdict,
            "detail": projection.get("detail", ""),
            "owner": owners[gate_id],
            "exit_criteria": exit_criteria[gate_id],
            "refresh_time": now,
            "sha256_digest": gate_digest,
            "source_receipt": "receipt://.omo/_delivery/environment-evidence/_gate-health.json",
            "not_admitted_legal_states": not_admitted_legal_states,
            "unlock_conditions": unlock_conditions,
            "live": projection.get("live", False),
            "depends_on": projection.get("depends_on", []),
        }
        receipt_path = output_dir / f"{gate_id}.json"
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        receipts.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")
        print(f"OK {gate_id}: {status} ({verdict})")

print(f"Receipts: {receipts_path}")
PY
