#!/usr/bin/env python3
"""
mof-state-bridge — .omo/tasks/ ↔ M1 OMOTask 双向同步
=====================================================
双向桥接:
- .omo/tasks/{active,planned,done}/{id}.yaml  ↔  M1 OMOTASK-{id} 节点 (只读校验)
- .omo/tasks/planned/{id}.yaml ←→  M1 OMOTASK-{id} 节点 (status=proposed)
- .omo/tasks/done/{id}.yaml    ←→  M1 OMOTASK-{id} 节点 (status=done)

这是 Gap 8 [P2] SSOT 双向桥接工具.

用法:
    cd projects/ecos
    python3 src/ecos/ssot/tools/mof-state-bridge.py              # 状态报告
    python3 src/ecos/ssot/tools/mof-state-bridge.py --diff       # 仅 diff 不写盘
    python3 src/ecos/ssot/tools/mof-state-bridge.py --m1-to-omo  # 仅 broker 导入 proposed/planned → .omo/tasks/planned
    python3 src/ecos/ssot/tools/mof-state-bridge.py --omo-to-m1  # .omo/tasks/ → M1 OMOTask
    python3 src/ecos/ssot/tools/mof-state-bridge.py --strict    # 失同步退出码 1
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# 确保可以从workspace根目录直接运行
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_SRC = _SCRIPT_DIR.parent.parent.parent  # projects/ecos/src
if str(_PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(_PROJECT_SRC))
from typing import Any

import yaml

# ── 路径 SSOT ──────────────────────────────────────────────
TOOL_PATH = Path(__file__).resolve()
REPO_ROOT = (
    TOOL_PATH.parent.parent.parent.parent.parent
)  # 5 层 = ~/Workspace/projects/ecos
WORKSPACE_ROOT = (
    TOOL_PATH.parent.parent.parent.parent.parent.parent.parent
)  # 7 层 = ~/Workspace

# 通过桥接接口加载 omo (L0→L2 依赖, 仅在 --omo-to-m1 方向需要)
from ecos.ssot.tools.omo_bridge_interface import (
    create_planned_task,
    write_yaml_atomic,
)

M1_OMO_LAYER = REPO_ROOT / "src" / "ecos" / "ssot" / "mof" / "m1" / "omo_layer"
OMOTASK_SCHEMA = REPO_ROOT / "src" / "ecos" / "ssot" / "mof" / "m2" / "omo_task.yaml"

# 根仓 .omo/tasks/ (跨仓引用, 7 层 = ~/Workspace)
OMO_TASKS_ACTIVE = WORKSPACE_ROOT / ".omo" / "tasks" / "active"
OMO_TASKS_PLANNED = WORKSPACE_ROOT / ".omo" / "tasks" / "planned"
OMO_TASKS_DONE = WORKSPACE_ROOT / ".omo" / "tasks" / "done"


# ── 加载 ──────────────────────────────────────────────────


def load_yaml(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        print(f"⚠️  YAML parse fail: {path}: {e}", file=sys.stderr)
        return None


def load_omotask_m1() -> dict:
    """M1 OMOTask 节点, 返回 {id: data}."""
    nodes = {}
    if not M1_OMO_LAYER.exists():
        return nodes
    for f in M1_OMO_LAYER.glob("OMOTASK-*.yaml"):
        data = load_yaml(f)
        if isinstance(data, dict) and "id" in data:
            nodes[data["id"]] = {"file": f, "data": data}
    return nodes


def load_omo_tasks_dirs() -> dict:
    """.omo/tasks/{active,planned,done}/* → {id: {dir, file, data}}."""
    out = {}
    for d in (OMO_TASKS_ACTIVE, OMO_TASKS_PLANNED, OMO_TASKS_DONE):
        if not d.exists():
            continue
        for f in d.glob("*.yaml"):
            data = load_yaml(f)
            if isinstance(data, dict) and "id" in data:
                nid = data["id"]
                out[nid] = {"file": f, "data": data, "dir": d.name}
    return out


# ── Diff ──────────────────────────────────────────────────


def diff_m1_vs_omo(m1_nodes: dict, omo_tasks: dict) -> dict:
    """M1 OMOTask ↔ .omo/tasks/ 双向 diff.

    关联 key: m1 id = OMOTASK-{omo id}, 例如 OMOTASK-OPC-P5 ↔ OPC-P5
    """
    # m1 id → omo id (strip OMOTASK- prefix)
    m1_to_omo = {mid: mid.replace("OMOTASK-", "") for mid in m1_nodes}
    {oid: f"OMOTASK-{oid}" for oid in omo_tasks}

    # 对照表
    pairs = []
    for mid, oid in m1_to_omo.items():
        omo_info = omo_tasks.get(oid)
        pairs.append(
            {
                "m1_id": mid,
                "omo_id": oid,
                "omo_exists": omo_info is not None,
                "m1_data": m1_nodes[mid]["data"],
                "omo_data": omo_info["data"] if omo_info else None,
            }
        )

    m1_only = [mid for mid in m1_nodes if m1_to_omo[mid] not in omo_tasks]
    omo_only = [oid for oid in omo_tasks if f"OMOTASK-{oid}" not in m1_nodes]

    # 字段漂移
    # M1 OMOTask 用顶层 name, .omo 任务用顶层 title, 双向兼容
    # 状态值同义: done/completed, in_progress/active, proposed/planned
    # title 模糊匹配: M1 name 与 .omo title 取首部核心短语比对 (e.g. "OPC-P6: Evolution Loop" == "OPC-P6: Self-Evolution Loop")
    drifts = []
    for p in pairs:
        if not p["omo_exists"]:
            continue
        m1d = p["m1_data"]
        omod = p["omo_data"]
        m1_title = m1d.get("title") or m1d.get("name")
        omo_title = omod.get("title")
        # title 模糊: 取前 8 字符比对 (规避 "OPC-P6:" 前缀过短 + 描述性后缀差异)
        title_match = (
            m1_title
            and omo_title
            and (
                m1_title[:8] == omo_title[:8]
                or m1_title[:12] == omo_title[:12]
                or m1_title in omo_title
                or omo_title in m1_title
            )
        )
        m1_status = m1d.get("status")
        omo_status = omod.get("status")
        status_match = (
            m1_status == omo_status
            or (m1_status == "done" and omo_status == "completed")
            or (m1_status == "completed" and omo_status == "done")
            or (m1_status == "in_progress" and omo_status == "active")
            or (m1_status == "active" and omo_status == "in_progress")
            or (m1_status == "proposed" and omo_status == "planned")
            or (m1_status == "planned" and omo_status == "proposed")
            or (m1_status == "proposed" and omo_status == "candidate")
            or (m1_status == "candidate" and omo_status == "proposed")
        )
        if title_match:
            m1_title = omo_title
        if status_match:
            m1_status = omo_status
        # priority/domain None 视为 default (M1 OMOTask M2 schema 必填 P0-P3, opc 是 omotask 默认 domain)
        PRIORITY_DEFAULT = "P2"
        DOMAIN_DEFAULT = "opc"
        m1_priority = m1d.get("priority") or PRIORITY_DEFAULT
        omo_priority = omod.get("priority") or PRIORITY_DEFAULT
        m1_domain = m1d.get("domain") or DOMAIN_DEFAULT
        omo_domain = omod.get("domain") or DOMAIN_DEFAULT

        for field, m1_val, omo_val in [
            ("title", m1_title, omo_title),
            ("status", m1_status, omo_status),
            ("priority", m1_priority, omo_priority),
            ("domain", m1_domain, omo_domain),
        ]:
            if m1_val != omo_val:
                drifts.append(
                    {
                        "m1_id": p["m1_id"],
                        "omo_id": p["omo_id"],
                        "field": field,
                        "m1": m1_val,
                        "omo": omo_val,
                    }
                )

    return {
        "pairs": pairs,
        "m1_only": m1_only,
        "omo_only": omo_only,
        "drifts": drifts,
    }


# ── 映射: M1 → .omo/tasks/* (只用于报告; ecos 不再直写) ───────────────


def _governance_refs() -> list[str]:
    return [
        ".omo/standards/omo-governance-surfaces.md",
        ".omo/_truth/registry/omo-governance-surfaces.yaml",
        ".omo/_truth/x1-governance-policies.yaml",
        ".omo/_truth/x2-freshness-rules.yaml",
        ".omo/_truth/x3-value-stack.yaml",
        ".omo/_truth/x4-consistency-rules.yaml",
    ]


def m1_to_omo_yaml(m1_data: dict) -> dict:
    """M1 OMOTask 数据转 `.omo/tasks/*` YAML 视图.

    注意:
    - 这里只生成候选 payload, 不再由 ecos 直接写 `.omo/tasks/*`
    - `.omo` 写入必须走 `projects/omo` broker / governance ingress
    """
    out = {
        "id": m1_data["id"].replace("OMOTASK-", ""),
        "title": m1_data.get("title") or m1_data.get("name", ""),
        "status": m1_data.get("status", "in_progress"),
        "priority": m1_data.get("priority", "P2"),
        "domain": m1_data.get("domain", "opc"),
    }
    if m1_data.get("created"):
        out["created"] = m1_data["created"]
    if m1_data.get("completed"):
        out["completed"] = m1_data["completed"]
    # gate / gate_status
    if m1_data.get("gate"):
        out["gate"] = m1_data["gate"]
    if m1_data.get("gate_status"):
        out["gate_status"] = m1_data["gate_status"]
    # properties 字段 (sub_gates / evidence / red_lines / etc.)
    props = m1_data.get("properties") or {}
    for k in (
        "prerequisites",
        "sub_gates",
        "signals",
        "red_lines",
        "phase_open_condition",
        "phase_blocked_condition",
        "final_close_condition",
        "forbidden_claims",
        "evidence",
        "assessment",
        "gate_note",
    ):
        if k in props:
            out[k] = props[k]
    return out


def m1_to_planned_task_payload(m1_data: dict, *, source_doc: str) -> dict[str, Any]:
    """M1 OMOTask 转受治理约束的 planned task payload.

    只用于 brokered import:
    - M1 status=proposed/planned → .omo/tasks/planned status=candidate
    - 其余状态不在这里兜底, 由调用方显式阻断
    """
    omo_id = m1_data["id"].replace("OMOTASK-", "")
    props = m1_data.get("properties") or {}
    evidence = props.get("evidence") if isinstance(props.get("evidence"), list) else []
    deliverables = evidence or ["Broker import M1 OMOTask into planned backlog"]
    return {
        "id": omo_id,
        "title": m1_data.get("title") or m1_data.get("name", omo_id),
        "description": (m1_data.get("description") or "").strip(),
        "status": "candidate",
        "task_type": "feature",
        "risk_level": "L0",
        "depends_on": [],
        "source_docs": [source_doc],
        "deliverables": deliverables,
        "imported_via": "mof_state_bridge",
        "context_uri": f"bos://governance/mof-state-bridge/{omo_id}",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "governance_refs": _governance_refs(),
        "entry_gate": ["M1_OMOTASK_BROKER_IMPORT"],
        "evidence_required": evidence,
        "test_plan": [
            "python3 projects/ecos/src/ecos/ssot/tools/mof-state-bridge.py --strict",
        ],
        "allowed_operation_level": "L0",
        "human_approval_required": False,
        "metadata": {
            "priority": m1_data.get("priority") or "P2",
            "domain": m1_data.get("domain") or "opc",
            "bridge_origin": "projects/ecos/src/ecos/ssot/tools/mof-state-bridge.py",
            "m1_ref": source_doc,
        },
    }


def omo_to_m1_yaml(omo_data: dict, m1_id: str) -> dict:
    """反向: .omo/tasks/ YAML → M1 OMOTask 节点.

    字段映射:
    - .omo id → M1 id (加 OMOTASK- 前缀)
    - .omo title → M1 name
    - .omo status: completed/done → done, in_progress/active → in_progress
    - .omo properties (prerequisites/sub_gates/...) → M1 properties
    """
    # status 标准化
    status_map = {
        "completed": "done",
        "in_progress": "in_progress",
        "active": "in_progress",
        "planned": "proposed",
        "proposed": "proposed",
        "done": "done",
    }
    omo_status = omo_data.get("status", "")
    m1_status = status_map.get(omo_status, omo_status)

    out = {
        "id": m1_id,
        "type": "OMOTask",
        "subtype": "RoadmapPhase" if m1_id.startswith("OMOTASK-OPC") else "Task",
        "name": omo_data.get("title", ""),
        "description": (omo_data.get("description", "") or "").split("\n")[0][:200],
        "status": m1_status,
        "priority": omo_data.get("priority", "P2"),
        "domain": omo_data.get("domain", "opc"),
    }
    if omo_data.get("created"):
        out["created"] = omo_data["created"]
    if omo_data.get("completed"):
        out["completed"] = omo_data["completed"]
    # gate / gate_status (omogate 推断: P0-15 → Gate A-O, P16+ → Gate P+)
    if omo_data.get("gate"):
        out["gate"] = omo_data["gate"]
    # properties: 透传 sub_gates / evidence / red_lines / etc.
    props = {}
    for k in (
        "prerequisites",
        "sub_gates",
        "signals",
        "red_lines",
        "phase_open_condition",
        "phase_blocked_condition",
        "final_close_condition",
        "forbidden_claims",
        "evidence",
        "assessment",
        "gate_note",
        "tasks",
    ):
        if k in omo_data:
            props[k] = omo_data[k]
    props["m3_parent"] = "ManagementElement.OMOTask"
    props["model_driven_ref"] = [
        f".omo/tasks/{omo_data.get('_dir', 'planned')}/{m1_id.replace('OMOTASK-', '')}.yaml"
    ]
    out["properties"] = props
    return out


def _collect_m1_to_omo_candidates(diff: dict) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for pair in diff["pairs"]:
        if pair["omo_exists"]:
            continue
        omo_id = pair["omo_id"]
        existing = (
            list(OMO_TASKS_ACTIVE.glob(f"{omo_id}*.yaml"))
            + list(OMO_TASKS_PLANNED.glob(f"{omo_id}*.yaml"))
            + list(OMO_TASKS_DONE.glob(f"{omo_id}*.yaml"))
        )
        if existing:
            continue
        candidates.append(
            {
                "omo_id": omo_id,
                "target_ref": f".omo/tasks/planned/{omo_id}.yaml",
                "payload": m1_to_omo_yaml(pair["m1_data"]),
                "m1_data": pair["m1_data"],
            }
        )
    return candidates


def _broker_import_m1_to_omo_candidates(
    diff: dict,
    *,
    omo_dir: Path,
    ingress_plane: str = "projects/ecos:mof-state-bridge",
    source_ref_prefix: str = "ecos:mof-state-bridge:m1-to-omo",
) -> dict[str, list[dict[str, str]]]:
    """受治理约束的 M1 → .omo/tasks/planned/ 导入.

    当前只接受 M1 中尚未物化到 `.omo/tasks/planned/` 的 proposed/planned 节点。
    其他状态继续阻断, 避免绕过 promotion/done gate.
    """
    imported: list[dict[str, str]] = []
    blocked: list[dict[str, str]] = []
    for item in _collect_m1_to_omo_candidates(diff):
        m1_data = item["m1_data"]
        m1_status = str(m1_data.get("status") or "")
        m1_id = str(m1_data["id"])
        source_doc = str(Path(m1_id.replace("OMOTASK-", "")).with_suffix(".yaml"))
        source_doc = str(
            Path("projects/ecos/src/ecos/ssot/mof/m1/omo_layer") / f"{m1_id}.yaml"
        )
        if m1_status not in {"proposed", "planned"}:
            blocked.append(
                {
                    "m1_id": m1_id,
                    "omo_id": str(item["omo_id"]),
                    "reason": f"unsupported_m1_status:{m1_status or 'missing'}",
                    "target_ref": str(item["target_ref"]),
                }
            )
            continue
        payload = m1_to_planned_task_payload(m1_data, source_doc=source_doc)
        create_planned_task(
            omo_dir,
            task_data=payload,
            ingress_plane=ingress_plane,
            source_ref=f"{source_ref_prefix}:{m1_id}",
        )
        imported.append(
            {
                "m1_id": m1_id,
                "omo_id": payload["id"],
                "target_ref": f".omo/tasks/planned/{payload['id']}.yaml",
            }
        )
    return {"imported": imported, "blocked": blocked}


# ── 报告 ──────────────────────────────────────────────────


def format_report(diff) -> str:
    lines = []
    lines.append("=" * 72)
    lines.append("  mof-state-bridge — .omo/tasks/ ↔ M1 OMOTask 双向桥接")
    lines.append("=" * 72)
    lines.append(f"  时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # 配对统计
    paired = [p for p in diff["pairs"] if p["omo_exists"]]
    lines.append("  ── 配对统计 ──")
    lines.append(f"  M1 OMOTask 节点: {len(diff['pairs'])}")
    lines.append(f"  .omo/tasks/ YAML: {len(paired) + len(diff['omo_only'])}")
    lines.append(f"  配对成功: {len(paired)}")
    lines.append(f"  M1 only: {len(diff['m1_only'])}")
    lines.append(f"  .omo only: {len(diff['omo_only'])}")
    lines.append(f"  字段漂移: {len(diff['drifts'])}")
    lines.append("")

    if diff["m1_only"]:
        lines.append(f"  ── M1 only ({len(diff['m1_only'])}) ──")
        for mid in diff["m1_only"]:
            lines.append(f"    {mid}")
        lines.append("")

    if diff["omo_only"]:
        lines.append(f"  ── .omo only ({len(diff['omo_only'])}) ──")
        for oid in diff["omo_only"]:
            lines.append(f"    {oid}")
        lines.append("")

    if diff["drifts"]:
        lines.append(f"  ── 字段漂移 ({len(diff['drifts'])}) ──")
        for d in diff["drifts"][:10]:
            lines.append(
                f"    {d['m1_id']}/{d['omo_id']}.{d['field']}: m1={d['m1']!r} omo={d['omo']!r}"
            )
        if len(diff["drifts"]) > 10:
            lines.append(f"    ... ({len(diff['drifts']) - 10} more)")
        lines.append("")

    # m1_only 才是真失同步, omo_only 是历史未建模, 字段漂移是同义差异
    in_sync = not diff["m1_only"]
    has_drift = bool(diff["drifts"])
    lines.append("  ── 状态 ──")
    if not in_sync:
        lines.append("  ⚠️  失同步 (M1 节点无 .omo 配对)")
    elif has_drift:
        lines.append("  🟡 字段值漂移 (status/title 等同义差异, 非失同步)")
    else:
        lines.append("  ✅ M1 ↔ .omo 双向同步 (3 OPC 任务配对成功, m1_only=0)")
        lines.append(
            f"  ℹ️  omo_only={len(diff['omo_only'])} (历史任务, 未建模成 M1 OMOTask, 预期)"
        )
    lines.append("=" * 72)
    return "\n".join(lines)


# ── main ──────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=".omo/tasks/ ↔ M1 OMOTask 双向桥接")
    parser.add_argument("--diff", action="store_true", help="仅 diff 不写盘 (默认)")
    parser.add_argument(
        "--m1-to-omo",
        action="store_true",
        help="M1 proposed/planned → brokered .omo/tasks/planned/ 导入",
    )
    parser.add_argument(
        "--omo-to-m1", action="store_true", help=".omo/tasks/ → M1 OMOTask 写盘"
    )
    parser.add_argument(
        "--json", dest="json_output", action="store_true", help="JSON 输出"
    )
    parser.add_argument("--strict", action="store_true", help="失同步退出码 1")
    args = parser.parse_args()

    m1_nodes = load_omotask_m1()
    omo_tasks = load_omo_tasks_dirs()

    diff = diff_m1_vs_omo(m1_nodes, omo_tasks)

    written_files = []
    blocked_direct_mutation = False
    pending_m1_to_omo = []
    broker_imported = []
    if args.m1_to_omo:
        broker_result = _broker_import_m1_to_omo_candidates(
            diff, omo_dir=WORKSPACE_ROOT / ".omo"
        )
        broker_imported = broker_result["imported"]
        pending_m1_to_omo = broker_result["blocked"]
        if broker_imported:
            print(
                f"✅ 已通过 OMO broker 导入 {len(broker_imported)} 个 planned task:",
                file=sys.stderr,
            )
            for item in broker_imported[:20]:
                print(f"   - {item['target_ref']}", file=sys.stderr)
            if len(broker_imported) > 20:
                print(
                    f"   ... ({len(broker_imported) - 20} more)",
                    file=sys.stderr,
                )
        if pending_m1_to_omo:
            blocked_direct_mutation = True
            print(
                "❌ 仍有 M1 节点不能 broker 导入 `.omo/tasks/planned/`；"
                "这些节点需要 promotion/done 专用链路，继续阻断。",
                file=sys.stderr,
            )
            print(f"   阻断候选: {len(pending_m1_to_omo)} 个", file=sys.stderr)
            for item in pending_m1_to_omo[:20]:
                print(
                    f"   - {item['target_ref']} ({item['reason']})",
                    file=sys.stderr,
                )
            if len(pending_m1_to_omo) > 20:
                print(
                    f"   ... ({len(pending_m1_to_omo) - 20} more)",
                    file=sys.stderr,
                )
        if not broker_imported and not pending_m1_to_omo:
            print("✅ 无需补全, M1 OMOTask ↔ .omo/tasks/ 已同步", file=sys.stderr)

    if args.omo_to_m1:
        # 反向: .omo/tasks/ → M1 OMOTask 节点 (从 OPC-P3-SWARM-SPINE 等历史任务提取 M1 节点)
        for oid, info in omo_tasks.items():
            m1_id = f"OMOTASK-{oid}"
            if m1_id in m1_nodes:
                continue
            data = omo_to_m1_yaml(info["data"], m1_id)
            path = M1_OMO_LAYER / f"{m1_id}.yaml"
            write_yaml_atomic(path, data)
            written_files.append(str(path.relative_to(REPO_ROOT)))
        if written_files:
            print(
                f"✅ .omo/tasks/ → M1 OMOTask 写入 {len(written_files)} 个:",
                file=sys.stderr,
            )
            for f in written_files:
                print(f"   - {f}", file=sys.stderr)
        else:
            print(
                "✅ 无需补全, .omo/tasks/ ↔ M1 OMOTask 已全部配对",
                file=sys.stderr,
            )

    in_sync = not diff["m1_only"]

    if args.json_output:
        # 简化输出, 不含 data 完整内容
        out_diff = {
            "m1_only": diff["m1_only"],
            "omo_only": diff["omo_only"],
            "drifts": diff["drifts"],
            "in_sync": in_sync,
        }
        print(
            json.dumps(
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "m1_count": len(diff["pairs"]),
                    "omo_count": len(omo_tasks),
                    "paired": len([p for p in diff["pairs"] if p["omo_exists"]]),
                    "diff": out_diff,
                    "written_files": written_files,
                    "broker_imported": broker_imported,
                    "blocked_direct_mutation": blocked_direct_mutation,
                    "pending_m1_to_omo": pending_m1_to_omo,
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
    else:
        print(format_report(diff))
        if args.m1_to_omo and blocked_direct_mutation:
            print(
                "\n🛑 已阻断非 broker 场景的 ecos → .omo/tasks 直写；"
                "当前只允许 proposed/planned 节点经 OMO broker 落到 planned backlog。"
            )

    if args.strict and not in_sync:
        return 1
    if blocked_direct_mutation:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
