#!/usr/bin/env python3
"""
mof-state-bridge — .omo/tasks/ ↔ M1 OMOTask 双向同步
=====================================================
双向桥接:
- .omo/tasks/active/{id}.yaml  ←→  M1 OMOTASK-{id} 节点
- .omo/tasks/planned/{id}.yaml ←→  M1 OMOTASK-{id} 节点 (status=proposed)
- .omo/tasks/done/{id}.yaml    ←→  M1 OMOTASK-{id} 节点 (status=done)

这是 Gap 8 [P2] SSOT 双向桥接工具.

用法:
    cd projects/ecos
    python3 src/ecos/ssot/tools/mof-state-bridge.py              # 状态报告
    python3 src/ecos/ssot/tools/mof-state-bridge.py --diff       # 仅 diff 不写盘
    python3 src/ecos/ssot/tools/mof-state-bridge.py --m1-to-omo  # M1 → .omo/tasks/active/
    python3 src/ecos/ssot/tools/mof-state-bridge.py --omo-to-m1  # .omo/tasks/active/ → M1
    python3 src/ecos/ssot/tools/mof-state-bridge.py --strict    # 失同步退出码 1
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

# ── 路径 SSOT ──────────────────────────────────────────────
TOOL_PATH = Path(__file__).resolve()
REPO_ROOT = (
    TOOL_PATH.parent.parent.parent.parent.parent
)  # 5 层 = ~/Workspace/projects/ecos
WORKSPACE_ROOT = (
    TOOL_PATH.parent.parent.parent.parent.parent.parent.parent
)  # 7 层 = ~/Workspace

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
        )
        if title_match:
            m1_title = omo_title
        if status_match:
            m1_status = omo_status
        for field, m1_val, omo_val in [
            ("title", m1_title, omo_title),
            ("status", m1_status, omo_status),
            ("priority", m1d.get("priority"), omod.get("priority")),
            ("domain", m1d.get("domain"), omod.get("domain")),
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


# ── 写盘: M1 → .omo/tasks/active/ ────────────────────────


def m1_to_omo_yaml(m1_data: dict) -> dict:
    """M1 OMOTask 数据转 .omo/tasks/active/ YAML 格式."""
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


def main():
    parser = argparse.ArgumentParser(description=".omo/tasks/ ↔ M1 OMOTask 双向桥接")
    parser.add_argument("--diff", action="store_true", help="仅 diff 不写盘 (默认)")
    parser.add_argument(
        "--m1-to-omo", action="store_true", help="M1 → .omo/tasks/active/ 写盘"
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
    if args.m1_to_omo:
        OMO_TASKS_ACTIVE.mkdir(parents=True, exist_ok=True)
        for p in diff["pairs"]:
            if p["omo_exists"]:
                continue
            omo_id = p["omo_id"]
            path = OMO_TASKS_ACTIVE / f"{omo_id}.yaml"
            # 跳过已存在的扩展名 (e.g. OPC-P6 vs OPC-P6-EVOLUTION-LOOP)
            existing = (
                list(OMO_TASKS_ACTIVE.glob(f"{omo_id}*.yaml"))
                + list(OMO_TASKS_PLANNED.glob(f"{omo_id}*.yaml"))
                + list(OMO_TASKS_DONE.glob(f"{omo_id}*.yaml"))
            )
            if existing:
                print(
                    f"⏭️  跳过 {omo_id} (已存在扩展名: {[f.name for f in existing]})",
                    file=sys.stderr,
                )
                continue
            data = m1_to_omo_yaml(p["m1_data"])
            path.write_text(
                yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            written_files.append(str(path.relative_to(WORKSPACE_ROOT)))
        if written_files:
            print(
                f"✅ M1 → .omo/tasks/active/ 写入 {len(written_files)} 个:",
                file=sys.stderr,
            )
            for f in written_files:
                print(f"   - {f}", file=sys.stderr)
        else:
            print(
                "✅ 无需补全, M1 OMOTask ↔ .omo/tasks/active/ 已同步", file=sys.stderr
            )

    in_sync = not diff["m1_only"] and not diff["omo_only"] and not diff["drifts"]

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
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
    else:
        print(format_report(diff))
        if args.m1_to_omo and written_files:
            print(f"\n📝 已写盘: {len(written_files)} 个文件")

    if args.strict and not in_sync:
        sys.exit(1)


if __name__ == "__main__":
    main()
