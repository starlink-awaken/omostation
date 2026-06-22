"""P44 R3 — 关闭 5 个 REMEDIATE-WF-CONV-* 任务 + drift 修复"""
import sys
from pathlib import Path

sys.path.insert(0, "projects/omo/src")

import yaml  # noqa: E402
from omo.omo_task_schema import validate_task_data  # noqa: E402

REMEDIATIONS = [
    {
        "id": "REMEDIATE-WF-CONV-P0-DISPATCHER",
        "phase_done": "Phase 7",
        "commit_refs": "ecos eb95696 (executor subprocess) + a1933de7 (dispatcher daemon)",
        "evidence": "ecos/workflow/executor.py 全部改 subprocess 调用 swarm CLI / runtime CLI，"
        "不再 try/except import 上层包；66 workflow tests + 780 ecos tests 全过。",
    },
    {
        "id": "REMEDIATE-WF-CONV-P0-CLOSE-METAOS-MCP",
        "phase_done": "Phase 6",
        "commit_refs": "agora 0842d4f (KNOWN_BACKENDS 移除 metaos) + metaos 164b677 (MCP 入口关停)",
        "evidence": "agora mcp_gateway.py KNOWN_BACKENDS 移除 metaos 条目；MCPTOOL-METAOS.yaml / "
        "SVC-METAOS-MCP.yaml 状态置 not_running；agora 启动后 metaos 不自动运行。",
    },
    {
        "id": "REMEDIATE-WF-CONV-P0-EVENTS",
        "phase_done": "Phase 8",
        "commit_refs": "ecos 96234bc (SSE event_listener)",
        "evidence": "bos://ecos/events SSE 端点就绪，event_listener.py 275 行落地；listen_forever "
        "对接实际事件流（Omni-Bus 3 Facade 之一）。",
    },
    {
        "id": "REMEDIATE-WF-CONV-P7-BACKENDS",
        "phase_done": "Phase 7",
        "commit_refs": "ecos eb95696 (backends/ 3 适配器)",
        "evidence": "ecos/workflow/backends/ 3 适配器（symphony/swarm/runtime）全部注册到 "
        "BackendRegistry；backend 路由表与 M1 元元模型一致。",
    },
    {
        "id": "REMEDIATE-WF-CONV-P8-E2E",
        "phase_done": "Phase 9",
        "commit_refs": "ecos eb95696 (e2e tests)",
        "evidence": "E2E 26 个测试全过；白盒全覆盖 16 个测试全过；780 ecos + 196 metaos + 66 workflow "
        "测试套件全绿。",
    },
]


def update_remediation(rec):
    path = Path(f".omo/tasks/remediation/{rec['id']}.yaml")
    task = yaml.safe_load(path.read_text(encoding="utf-8"))

    task["status"] = "done"
    task["resolution_evidence"] = rec["evidence"]
    task["commit_ref"] = rec["commit_refs"]
    task["phase_done"] = rec["phase_done"]
    task["closed_at"] = "2026-06-22T04:30:00Z"
    task["lifecycle_state"] = "closed"
    task["gate_level"] = "none"
    task["assigned_to"] = None
    task["dispatch_id"] = None
    task["run_ref"] = None
    task["approval_ref"] = None
    task["review_ref"] = None
    task.setdefault("knowledge_refs", [])
    task["knowledge_refs"].append(
        "projects/ecos/docs/ARCHITECTURE-REVIEW-workflow-convergence.md"
    )
    task.setdefault("handoff_refs", [])
    task.setdefault("entry_gate", [])
    task["entry_gate"].append("P44-REMEDIATE-WF-CONV-CLOSE")
    task.setdefault(
        "evidence_required",
        ["commit_ref + 实际产物 (see projects/ecos/docs/ARCHITECTURE-REVIEW-workflow-convergence.md)"],
    )
    task.setdefault("test_plan", ["omo governance 100 A+", "ecos tests 全过"])
    task["test_plan"] = list({*task["test_plan"]})

    path.write_text(
        yaml.safe_dump(task, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )
    return task


for rec in REMEDIATIONS:
    try:
        updated = update_remediation(rec)
        print(f"OK {rec['id']} → status={updated['status']}")
    except Exception as e:
        print(f"FAIL {rec['id']}: {e}")

# 关闭 BET-WF-CONVERGENCE-REAL
bet_path = Path(".omo/tasks/planned/BET-WF-CONVERGENCE-REAL.yaml")
bet = yaml.safe_load(bet_path.read_text(encoding="utf-8"))
bet["status"] = "done"
bet["resolution_evidence"] = (
    "Phases 1-9 全部完成: "
    "ecos eb95696 + 96234bc (workflow + executor + SSE event_listener) | "
    "agora 0842d4f (KNOWN_BACKENDS 移除 metaos) | "
    "metaos 164b677 (MCP 入口关停，metaos 通过 ecos/workflow subprocess 路由)。"
)
bet["commit_ref"] = "ecos eb95696+96234bc / agora 0842d4f / metaos 164b677"
bet["closed_at"] = "2026-06-22T04:30:00Z"
bet["lifecycle_state"] = "closed"
bet["gate_level"] = "none"
bet["assigned_to"] = None
bet["dispatch_id"] = None
bet["run_ref"] = None
bet["approval_ref"] = None
bet["review_ref"] = None
bet.setdefault("knowledge_refs", [])
bet["knowledge_refs"].append(
    "projects/ecos/docs/ARCHITECTURE-REVIEW-workflow-convergence.md"
)
bet.setdefault("handoff_refs", [])
bet.setdefault("entry_gate", [])
bet["entry_gate"].append("P44-REMEDIATE-WF-CONV-CLOSE")
bet.setdefault("test_plan", ["omo governance 100 A+"])
bet.setdefault("evidence_required", ["wf-convergence 全部 5 REMEDIATE 已 done"])

bet_path.write_text(
    yaml.safe_dump(bet, allow_unicode=True, sort_keys=False, width=120),
    encoding="utf-8",
)
print(f"OK BET-WF-CONVERGENCE-REAL → status={bet['status']}")
