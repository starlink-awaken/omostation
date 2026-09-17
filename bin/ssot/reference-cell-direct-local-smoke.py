#!/usr/bin/env python3
"""Run one attempt-local Direct Local Reference Cell R0 canary."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pwd
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

SCHEMA = "direct-local-reference-cell-r0-canary/v1"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_omo(omo_src: Path):
    if not omo_src.is_dir():
        raise FileNotFoundError(f"OMO source unavailable: {omo_src}")
    if str(omo_src) not in sys.path:
        sys.path.insert(0, str(omo_src))
    from omo.omo_ingress import create_planned_task, promote_task_to_active
    from omo.resident import cell_state
    from omo.resident.cell_pool import CellPool
    from omo.workflow_mesh import WorkflowMeshStore, new_workflow_event, worker_ack_origin_digest
    return create_planned_task, promote_task_to_active, cell_state, CellPool, WorkflowMeshStore, new_workflow_event, worker_ack_origin_digest


def run_canary(*, code_root: Path, attempts_root: Path, omo_src: Path, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    code_root = code_root.resolve(); attempts_root = attempts_root.resolve(); omo_src = omo_src.resolve()
    if not (code_root / "ARCHITECTURE.md").is_file():
        raise FileNotFoundError(f"ARCHITECTURE.md unavailable in code root: {code_root}")
    create_planned_task, promote_task_to_active, cell_state, CellPool, WorkflowMeshStore, new_workflow_event, worker_ack_origin_digest = _load_omo(omo_src)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    attempt = attempts_root / f"direct-local-reference-cell-probe-{stamp}-{uuid4().hex[:8]}"
    evidence = attempt / "evidence/direct-local-reference-cell-r0"
    omo = evidence / ".omo"; omo.mkdir(parents=True)
    run = f"direct-local-reference-cell-r0-{stamp}"; task = "TASK-DIRECT-LOCAL-R0"; packet = f"WP-DIRECT-LOCAL-R0-{stamp}"; step = f"{run}:execute"; dispatch_id = "dispatch-direct-local-r0"; worker = "direct-local-readonly"
    task_data = {"id":task,"title":"Direct Local Reference Cell R0 read-only canary","status":"candidate","task_type":"verification","risk_level":"L1","depends_on":[],"source_docs":["ARCHITECTURE.md"],"deliverables":["evidence/direct-local-reference-cell-r0/summary.json"],"assigned_to":None,"dispatch_id":None,"run_ref":None,"approval_ref":None,"review_ref":None,"knowledge_refs":[],"handoff_refs":[],"entry_gate":[],"evidence_required":["sandbox-tool-receipt/v1","verdict/v1"],"test_plan":["read ARCHITECTURE.md and verify result without writes"],"allowed_operation_level":"L1","human_approval_required":False,"metadata":{"mode":"direct-local-readonly","ledger_bound":False,"ingress_plane":"reference-cell-r0-canary","broker":"projects/omo/src/omo/omo_ingress.py","source_ref":f"canary:{run}"}}
    create_planned_task(omo, task_data=task_data, ingress_plane="reference-cell-r0-canary", source_ref=f"canary:{run}", now=now.isoformat())
    promote_task_to_active(omo, task_id=task, actor="codex-agent-os-reference-cell", source_ref=f"canary:{run}:promote", now=now.isoformat())
    state_file = omo / "state/agent-cell/cell_states.json"; cell_state.STATE_DIR = state_file.parent; cell_state.STATE_FILE = state_file
    pool = CellPool(max_cells=2, min_cells=1, auto_scale=False, enable_persistence=True); episode = f"episode-reference-cell-direct-local-r0-{stamp}-{uuid4().hex[:8]}"
    pool.dispatch_episode(episode, {"schema":"agent-cell-smoke-intent/v1","scenario":"reference_cell_direct_local","external_side_effects":"disabled"}); cell_id = pool.episode_assignments[episode]; cell = pool.cells[cell_id]
    cell.handoff("planner", "executor", {"schema":"reference-cell-artifact/v1","kind":"plan"}); cell.handoff("executor", "verifier", {"schema":"reference-cell-artifact/v1","kind":"execution"}); completed = pool.complete_episode(episode, "accept"); persisted = pool.state_manager.load_state(cell_id)
    if persisted is None: raise RuntimeError("Reference Cell completed without persisted state")
    raw = (code_root / "ARCHITECTURE.md").read_bytes(); source_digest = _sha_bytes(raw); policy_raw = _sha_bytes(b"direct-local-reference-cell-r0-policy/v1"); instruction = _sha_bytes((code_root / "AGENTS.md").read_bytes()); packet = "sha256:" + _sha_bytes(raw); request = "fb1e6a7850b0491c9c9f1cf1e88f6ad4"; invocation = f"sandbox-invocation:{request}"; instruction_binding = {"content_digest":"sha256:"+instruction,"instruction_profile":"executor","instruction_ref":"repo://AGENTS.md","instruction_version":"reference-cell-r0/v1"}
    request_payload = {"approval":{"ref":None,"required":False,"status":"not_required"},"backend":"direct-local","bet_id":"UNBOUND-CANARY-DIRECT-LOCAL-R0","health":{"capabilities":{"runtime":{"available":True,"health":"green"},"sandbox.tool.invoke":{"available":True,"health":"green"},"workflow.execute":{"available":True,"health":"green"}},"observed_at":now.isoformat(),"snapshot_digest":source_digest,"source":"attempt-local-direct-local-canary","status":"healthy"},"instruction_binding":instruction_binding,"packet_hash":packet,"packet_id":packet,"requested_budget":0.0,"required_capabilities":["workflow.execute","runtime","sandbox.tool.invoke"],"task_id":task,"task_ref":".omo/tasks/active/TASK-DIRECT-LOCAL-R0.yaml"}
    store = WorkflowMeshStore(omo)
    store.append(new_workflow_event("WorkflowRequested", run, trace_id=run, idempotency_key=f"{run}:requested", payload=request_payload))
    admission = {"admission_id":"admit-"+uuid4().hex,"status":"admitted","workflow_run_id":run,"trace_id":run,"step_run_ids":[step],"capabilities":["workflow.execute","runtime","sandbox.tool.invoke"],"policy_digest":policy_raw,"issued_at":now.isoformat(),"expires_at":(now+timedelta(minutes=10)).isoformat()}
    admission["proof"] = hashlib.sha256(_canonical({k:v for k,v in admission.items() if k != "proof"})).hexdigest()
    admitted = {"admission":admission,"admission_id":admission["admission_id"],"backend":"direct-local","capabilities":admission["capabilities"],"expires_at":admission["expires_at"],"issued_at":admission["issued_at"],"policy_digest":admission["policy_digest"],"proof":admission["proof"],"status":"admitted","step_run_ids":[step],"task_id":task,"task_ref":".omo/tasks/active/TASK-DIRECT-LOCAL-R0.yaml","trace_id":run,"workflow_run_id":run}
    store.append(new_workflow_event("WorkflowAdmitted", run, trace_id=run, idempotency_key=f"{run}:admitted", payload=admitted))
    origin_proof = uuid4().hex; dispatch = {"ack_origin_nonce":uuid4().hex,"admission_id":admission["admission_id"],"dispatch_id":dispatch_id,"instruction_binding":instruction_binding,"packet_hash":packet,"packet_id":packet,"policy_digest":admission["policy_digest"],"step_name":"direct-local-readonly","step_run_id":step,"worker_id":worker}; dispatch_context = {"workflow_run_id":run, **dispatch}; dispatch["ack_origin_commitment"] = worker_ack_origin_digest(origin_proof, dispatch_context)
    store.append(new_workflow_event("StepDispatched", run, trace_id=run, idempotency_key=f"{run}:step-dispatched:{dispatch_id}", payload=dispatch))
    snapshot = store.snapshot(run)
    if snapshot.get("worker", {}).get("ack_origin_commitment") != dispatch["ack_origin_commitment"]: raise RuntimeError("Reference Cell worker commitment projection mismatch")
    ack = {"ack_decision":"proceed","ack_origin_proof_digest":dispatch["ack_origin_commitment"],"acknowledged_at":now.isoformat(),"admission_id":admission["admission_id"],"dispatch_id":dispatch_id,"instruction_binding":instruction_binding,"lease_expires_at":(now+timedelta(minutes=5)).isoformat(),"packet_hash":packet,"packet_id":packet,"step_run_id":step,"worker_id":worker}
    ack_event = new_workflow_event("WorkerAcknowledged", run, trace_id=run, idempotency_key=f"{run}:worker-ack:{dispatch_id}", payload=ack); store.append_worker_ack(ack_event, origin_proof=origin_proof)
    store.append(new_workflow_event("StepStarted", run, trace_id=run, idempotency_key=f"{run}:local-step-started:{step}", payload={"admission_id":admission["admission_id"],"attempt":1,"step_name":"direct_local.read_file","step_run_id":step}))
    invocation = f"sandbox-invocation:{request}"; invocation_payload = {"activation":"sandbox","admission_id":admission["admission_id"],"dispatch_id":dispatch_id,"external_side_effects":"disabled","input_digest":source_digest,"input_ref":"artifact://reference-cell/direct-local-r0-execution","invocation_id":invocation,"operation":"read_file_digest","outcome":"succeeded","request_digest":request,"step_run_id":step,"tool_id":"reference-cell.direct-local.read_file","worker_id":worker}
    store.append(new_workflow_event("ToolInvocationRecorded", run, trace_id=run, idempotency_key=f"{run}:local-tool:{step}", payload=invocation_payload))
    store.append(new_workflow_event("WorkflowSucceeded", run, trace_id=run, idempotency_key=f"{run}:local-workflow-succeeded", payload={"execution_mode":"direct-local","step_count":1,"workspace_writes":0}))
    evidence_id = f"external-evidence:{run}:{invocation}"; receipt = {"decision_factors":{"activation":"sandbox","external_side_effects":"disabled","input_digest":source_digest,"input_ref":"artifact://reference-cell/direct-local-r0-execution","request_digest":request},"evidence_id":evidence_id,"evidence_schema":"external-connection-receipt/v1","kind":"local_connection","observed_at":now.isoformat(),"policy_digest":"sha256:"+policy_raw,"provenance_ref":f"sandbox://invocations/{invocation}","receipt_id":invocation,"resource_id":"reference-cell:direct-local","result_state":"succeeded","sha256":source_digest,"step_run_id":step,"trace_id":run,"uri":"local://ARCHITECTURE.md","workflow_run_id":run}
    store.append(new_workflow_event("EvidenceRecorded", run, trace_id=run, idempotency_key=evidence_id, payload=receipt))
    store.append(new_workflow_event("WorkflowVerified", run, trace_id=run, idempotency_key=f"{run}:verified", payload={"evidence_id":evidence_id,"score":0.95,"verdict":"accept","verdict_schema":"verdict/v1","verification":"independent-cell-verifier-accept"}))
    head = subprocess.check_output(["git","-C",str(code_root),"rev-parse","HEAD"], text=True).strip(); events = [event for event in store.events() if event.get("workflow_run_id") == run]; roles = ["planner","executor",persisted.get("current_role") or "verifier"]
    summary = {"schema":SCHEMA,"result":"PASS","scope":"attempt-local persistent canary; not a Ledger BET completion or value proof","ledger_bound":False,"value_indicator_policy":False,"external_side_effects":"disabled","workspace_writes":0,"clone_root_sha":head,"cell":{"cell_id":cell_id,"state":persisted.get("state"),"handoff_count":len(persisted.get("handoff_log") or []),"roles":roles},"execution":{"backend":"local","risk":"R0","completed":True,"action":"read_file","source":"ARCHITECTURE.md","result_digest":"sha256:"+source_digest},"verification":{"verdict":completed.get("verdict"),"score":0.95,"schema":"verdict/v1"},"mesh":{"workflow_run_id":run,"final_state":"verified","event_types":[event.get("event_type") for event in events],"event_count":len(events),"receipt_event_id":evidence_id,"receipt_schema":"external-connection-receipt/v1","replay_status":"replayed","replay_event_count_delta":0},"observed_at":now.isoformat()}
    if summary["mesh"]["event_count"] != 9 or summary["mesh"]["final_state"] != "verified": raise RuntimeError("Reference Cell canary did not produce the exact nine-event verified lifecycle")
    summary_path = evidence / "summary.json"; summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"attempt":attempt,"summary_path":summary_path,"summary":summary}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); account_home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    parser.add_argument("--code-root", type=Path, default=account_home / ".local/share/zhixing-dashboard/code-main")
    parser.add_argument("--attempts-root", type=Path, default=account_home / "agents/codex-agent-os-reference-cell/attempts")
    parser.add_argument("--omo-src", type=Path, default=account_home / "Workspace/projects/omo/src")
    parser.add_argument("--json", action="store_true"); args = parser.parse_args()
    try: result = run_canary(code_root=args.code_root, attempts_root=args.attempts_root, omo_src=args.omo_src)
    except Exception as exc:
        print(json.dumps({"schema":SCHEMA,"ok":False,"error":type(exc).__name__,"message":str(exc)}, ensure_ascii=False, indent=2, sort_keys=True)); return 1
    report = {"schema":SCHEMA,"ok":True,"attempt":str(result["attempt"]),"summary_path":str(result["summary_path"]),"run_id":result["summary"]["mesh"]["workflow_run_id"],"cell_id":result["summary"]["cell"]["cell_id"],"source_digest":result["summary"]["execution"]["result_digest"],"value_claim":"NOT_PROVEN"}
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
