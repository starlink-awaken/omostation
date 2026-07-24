#!/usr/bin/env python3
"""
mof-bridge-sync — model-driven ↔ M1 增量同步工具
================================================
读取 model-driven/mof/m3_extended.py:STANDARD_STAGES/STANDARD_GATES
对照 projects/ecos/src/ecos/ssot/mof/m1/lifecycle/ 目录
输出 (1) 缺失节点 (2) 多余节点 (3) 字段漂移 (4) 增量补全 dry-run / 写盘

匹配策略:
- Stage 按 stage key (planning/design/...) 匹配, 不依赖 id 命名 (容忍 _ vs -)
- Gate 按 (from_stage, to_stage) transition 匹配

这是 B.3 mof-bridge-sync.py (Gap 6 [P1] 双向同步工具).

用法:
    cd projects/ecos
    python3 src/ecos/ssot/tools/mof-bridge-sync.py            # 状态报告
    python3 src/ecos/ssot/tools/mof-bridge-sync.py --diff     # 仅 diff 不写盘 (默认)
    python3 src/ecos/ssot/tools/mof-bridge-sync.py --sync     # 实际补全 M1
    python3 src/ecos/ssot/tools/mof-bridge-sync.py --sync --strict
    python3 src/ecos/ssot/tools/mof-bridge-sync.py --json     # JSON 输出
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

M1_LIFECYCLE_DIR = REPO_ROOT / "src" / "ecos" / "ssot" / "mof" / "m1" / "lifecycle"
M1_DIR = REPO_ROOT / "src" / "ecos" / "ssot" / "mof" / "m1"

MODEL_DRIVEN_M3 = (
    WORKSPACE_ROOT
    / "projects"
    / "model-driven"
    / "src"
    / "model_driven"
    / "mof"
    / "m3_extended.py"
)
MODEL_DRIVEN_PIPELINE = (
    WORKSPACE_ROOT
    / "projects"
    / "model-driven"
    / "src"
    / "model_driven"
    / "lifecycle"
    / "pipeline.py"
)


# ── 加载 model-driven SSOT ─────────────────────────────────


def load_standard_stages() -> list[dict]:
    """读 model-driven STANDARD_STAGES 完整字段."""
    if not MODEL_DRIVEN_M3.exists():
        print(f"FATAL: model-driven M3 源不存在: {MODEL_DRIVEN_M3}", file=sys.stderr)
        sys.exit(2)
    sys.path.insert(0, str(MODEL_DRIVEN_M3.parent.parent.parent))
    from model_driven.mof.m3_extended import (
        STANDARD_STAGES,  # type: ignore[import-not-found]
    )

    return [
        {
            "id": s.id,
            "name": s.name,
            "stage": s.stage.value,
            "order": s.order,
            "description": s.description,
            "entry_criteria": list(s.entry_criteria),
            "exit_criteria": list(s.exit_criteria),
            "core_activities": list(s.core_activities),
            "deliverables": list(s.deliverables),
            "stakeholders": list(s.stakeholders),
            "duration_target_days": s.duration_target_days,
        }
        for s in STANDARD_STAGES.values()
    ]


def load_standard_gates() -> list[dict]:
    if not MODEL_DRIVEN_M3.exists():
        sys.exit(2)
    sys.path.insert(0, str(MODEL_DRIVEN_M3.parent.parent.parent))
    from model_driven.mof.m3_extended import (
        STANDARD_GATES,  # type: ignore[import-not-found]
    )

    return [
        {
            "id": g.id,
            "name": g.name,
            "from_stage": g.from_stage.value,
            "to_stage": g.to_stage.value,
            "checks": list(g.checks),
            "required_approvals": list(g.required_approvals),
            "auto_pass": g.auto_pass,
        }
        for g in STANDARD_GATES
    ]


# ── 加载 M1 lifecycle/ ─────────────────────────────────────


def load_m1_lifecycle_nodes() -> dict:
    """读 M1 lifecycle/ 全部节点, 返回 {id: {file, data, kind}}."""
    nodes = {}
    if not M1_LIFECYCLE_DIR.exists():
        return nodes
    for f in sorted(M1_LIFECYCLE_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict) or "id" not in data:
            continue
        nid = data["id"]
        kind = "Stage" if "STAGE-" in nid else "Gate" if "GATE-" in nid else "Unknown"
        nodes[nid] = {"file": f, "data": data, "kind": kind}
    return nodes


# ── Diff ──────────────────────────────────────────────────


def diff_stages(std_stages: list[dict], m1_nodes: dict) -> dict:
    """7 阶段 diff. 按 stage key (planning/design/...) 匹配, 不依赖 id 命名."""
    std_by_stage = {s["stage"]: s for s in std_stages}
    m1_stages = [(nid, n) for nid, n in m1_nodes.items() if n["kind"] == "Stage"]
    m1_by_stage = {}
    for nid, n in m1_stages:
        m1_stage_key = (n["data"].get("properties") or {}).get("stage", "")
        if m1_stage_key:
            m1_by_stage[m1_stage_key] = (nid, n)

    missing = [
        s for stage_key, s in std_by_stage.items() if stage_key not in m1_by_stage
    ]
    extra = [
        (nid, n)
        for stage_key, (nid, n) in m1_by_stage.items()
        if stage_key not in std_by_stage
    ]
    drifts = []
    for stage_key, std in std_by_stage.items():
        if stage_key in m1_by_stage:
            nid, m1_info = m1_by_stage[stage_key]
            m1 = m1_info["data"]
            m1_props = m1.get("properties") or {}
            drift_fields = []
            # name 顶层, order 在 properties
            for field, source in (("name", m1), ("order", m1_props)):
                std_val = std.get(field)
                m1_val = source.get(field)
                if std_val != m1_val:
                    drift_fields.append({"field": field, "std": std_val, "m1": m1_val})
            if drift_fields:
                drifts.append({"id": nid, "stage": stage_key, "drift": drift_fields})
    return {
        "missing": missing,
        "extra": [
            {
                "id": eid,
                "file": str(info["file"].relative_to(REPO_ROOT)),
                "stage": (info["data"].get("properties") or {}).get("stage"),
            }
            for eid, info in extra
        ],
        "drift": drifts,
    }


def diff_gates(std_gates: list[dict], m1_nodes: dict) -> dict:
    """4 门禁 diff. 按 (from_stage, to_stage) 匹配, 不依赖 id 命名."""
    std_by_transition = {(g["from_stage"], g["to_stage"]): g for g in std_gates}
    m1_gates = [(nid, n) for nid, n in m1_nodes.items() if n["kind"] == "Gate"]
    m1_by_transition = {}
    for nid, n in m1_gates:
        props = n["data"].get("properties") or {}
        from_s = props.get("from_stage", "")
        to_s = props.get("to_stage", "")
        if from_s and to_s:
            m1_by_transition[(from_s, to_s)] = (nid, n)

    missing = [
        g for trans, g in std_by_transition.items() if trans not in m1_by_transition
    ]
    extra = [
        (nid, n)
        for trans, (nid, n) in m1_by_transition.items()
        if trans not in std_by_transition
    ]
    drifts = []
    for trans, std in std_by_transition.items():
        if trans in m1_by_transition:
            nid, m1_info = m1_by_transition[trans]
            m1 = m1_info["data"]
            m1_props = m1.get("properties") or {}
            drift_fields = []
            for field in ("name",):
                std_val = std.get(field)
                m1_val = m1.get(field)
                if std_val != m1_val:
                    drift_fields.append({"field": field, "std": std_val, "m1": m1_val})
            std_checks_count = len(std.get("checks", []))
            m1_checks_count = len(m1_props.get("checks", []))
            if std_checks_count != m1_checks_count:
                drift_fields.append(
                    {
                        "field": "checks_count",
                        "std": std_checks_count,
                        "m1": m1_checks_count,
                    }
                )
            if drift_fields:
                drifts.append(
                    {
                        "id": nid,
                        "transition": f"{trans[0]}→{trans[1]}",
                        "drift": drift_fields,
                    }
                )
    return {
        "missing": missing,
        "extra": [
            {"id": eid, "file": str(info["file"].relative_to(REPO_ROOT))}
            for eid, info in extra
        ],
        "drift": drifts,
    }


# ── 写盘: 补全 M1 节点 ─────────────────────────────────────


def stage_to_m1_yaml(std_stage: dict) -> str:
    """生成 STAGE-* M1 YAML 完整内容."""
    header = f"""id: "{std_stage["id"]}"
type: "Stage"
subtype: "StandardStage"
name: "{std_stage["name"]}"
description: "{std_stage["description"]} — 7 阶段标准生命周期第 {std_stage["order"] + 1} 阶段"
status: "active"
domain: "meta"
layer: "L0"
created: "{datetime.now(timezone.utc).strftime("%Y-%m-%d")}"
version: "1.0.0"
properties:
  order: {std_stage["order"]}
  stage: "{std_stage["stage"]}"
  m3_parent: "LifecycleElement.Stage"
  model_driven_ref:
    - "projects/model-driven/src/model_driven/mof/m3_extended.py:STANDARD_STAGES[{std_stage["stage"]}]"
  entry_criteria:
"""
    for c in std_stage.get("entry_criteria", []):
        header += f'    - "{c}"\n'
    header += "  exit_criteria:\n"
    for c in std_stage.get("exit_criteria", []):
        header += f'    - "{c}"\n'
    header += "  core_activities:\n"
    for c in std_stage.get("core_activities", []):
        header += f'    - "{c}"\n'
    header += "  deliverables:\n"
    for c in std_stage.get("deliverables", []):
        header += f'    - "{c}"\n'
    header += "  stakeholders:\n"
    for c in std_stage.get("stakeholders", []):
        header += f'    - "{c}"\n'
    header += f"  duration_target_days: {std_stage['duration_target_days']}\n"
    header += 'source: "model-driven/mof/m3_extended.py:STANDARD_STAGES"\n'
    return header


def gate_to_m1_yaml(std_gate: dict) -> str:
    """生成 GATE-* M1 YAML 完整内容."""
    header = f"""id: "{std_gate["id"]}"
type: "Gate"
subtype: "StandardGate"
name: "{std_gate["name"]}"
description: "{std_gate["name"]} — model-driven STANDARD_GATES 标准门禁"
status: "active"
domain: "meta"
layer: "L0"
created: "{datetime.now(timezone.utc).strftime("%Y-%m-%d")}"
version: "1.0.0"
properties:
  m3_parent: "LifecycleElement.Gate"
  model_driven_ref:
    - "projects/model-driven/src/model_driven/mof/m3_extended.py:STANDARD_GATES[{std_gate["id"]}]"
  from_stage: "{std_gate["from_stage"]}"
  to_stage: "{std_gate["to_stage"]}"
  checks:
"""
    for c in std_gate.get("checks", []):
        cn = c.get("name", "")
        ct = c.get("type", "document")
        cr = c.get("required", False)
        cth = c.get("threshold", "")
        line = f'    - name: "{cn}"\n      type: {ct}\n'
        if cth != "":
            line += f"      threshold: {cth}\n"
        elif cr:
            line += "      required: true\n"
        header += line
    if std_gate.get("required_approvals"):
        header += "  required_approvals:\n"
        for a in std_gate["required_approvals"]:
            header += f'    - "{a}"\n'
    if std_gate.get("auto_pass"):
        header += "  auto_pass: true\n"
    header += 'source: "model-driven/mof/m3_extended.py:STANDARD_GATES"\n'
    return header


# ── 报告 ─────────────────────────────────────────────────


def format_report(stage_diff, gate_diff) -> str:
    lines = []
    lines.append("=" * 72)
    lines.append("  mof-bridge-sync — model-driven ↔ M1 双向同步报告")
    lines.append("=" * 72)
    lines.append(f"  时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    lines.append("  ── Stage diff (按 stage key 匹配) ──")
    if stage_diff["missing"]:
        lines.append(
            f"  🔴 缺失 ({len(stage_diff['missing'])}): {[s['stage'] for s in stage_diff['missing']]}"
        )
    if stage_diff["extra"]:
        lines.append(
            f"  🟡 多余 ({len(stage_diff['extra'])}): {[e['id'] for e in stage_diff['extra']]}"
        )
    if stage_diff["drift"]:
        lines.append(f"  🟡 漂移 ({len(stage_diff['drift'])}):")
        for d in stage_diff["drift"]:
            lines.append(
                f"     {d['id']} (stage={d['stage']}): {[(x['field'], x['std'], x['m1']) for x in d['drift']]}"
            )
    if not (stage_diff["missing"] or stage_diff["extra"] or stage_diff["drift"]):
        lines.append("  ✅ Stage 完美同步")
    lines.append("")

    lines.append("  ── Gate diff (按 transition 匹配) ──")
    if gate_diff["missing"]:
        lines.append(
            f"  🔴 缺失 ({len(gate_diff['missing'])}): {[f'{g["from_stage"]}→{g["to_stage"]}' for g in gate_diff['missing']]}"
        )
    if gate_diff["extra"]:
        lines.append(
            f"  🟡 多余 ({len(gate_diff['extra'])}): {[e['id'] for e in gate_diff['extra']]}"
        )
    if gate_diff["drift"]:
        lines.append(f"  🟡 漂移 ({len(gate_diff['drift'])}):")
        for d in gate_diff["drift"]:
            lines.append(
                f"     {d['id']} ({d['transition']}): {[(x['field'], x['std'], x['m1']) for x in d['drift']]}"
            )
    if not (gate_diff["missing"] or gate_diff["extra"] or gate_diff["drift"]):
        lines.append("  ✅ Gate 完美同步")
    lines.append("")

    lines.append("=" * 72)
    return "\n".join(lines)


# ── main ──────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="model-driven ↔ M1 增量同步")
    parser.add_argument("--diff", action="store_true", help="仅 diff 不写盘 (默认)")
    parser.add_argument("--sync", action="store_true", help="实际写盘补全 M1 节点")
    parser.add_argument(
        "--json", dest="json_output", action="store_true", help="JSON 输出"
    )
    parser.add_argument("--strict", action="store_true", help="有缺失时退出码非 0")
    args = parser.parse_args()

    std_stages = load_standard_stages()
    std_gates = load_standard_gates()
    m1_nodes = load_m1_lifecycle_nodes()

    stage_diff = diff_stages(std_stages, m1_nodes)
    gate_diff = diff_gates(std_gates, m1_nodes)

    written_files = []
    if args.sync:
        M1_LIFECYCLE_DIR.mkdir(parents=True, exist_ok=True)
        for s in stage_diff["missing"]:
            # 用 stage key 转大写做文件名 (e.g. planning → STAGE-PLANNING)
            std_id = f"STAGE-{s['stage'].upper()}"
            path = M1_LIFECYCLE_DIR / f"{std_id}.yaml"
            # 构造 std-like dict for YAML gen
            std_like = {"id": std_id, **s}
            path.write_text(stage_to_m1_yaml(std_like), encoding="utf-8")
            written_files.append(str(path.relative_to(REPO_ROOT)))
        for g in gate_diff["missing"]:
            std_id = f"GATE-{g['from_stage'].upper()}-TO-{g['to_stage'].upper()}"
            path = M1_LIFECYCLE_DIR / f"{std_id}.yaml"
            std_like = {"id": std_id, **g}
            path.write_text(gate_to_m1_yaml(std_like), encoding="utf-8")
            written_files.append(str(path.relative_to(REPO_ROOT)))
        if written_files:
            print(f"✅ 写入 {len(written_files)} 个新 M1 节点:", file=sys.stderr)
            for f in written_files:
                print(f"   - {f}", file=sys.stderr)
        else:
            print("✅ 无需补全, M1 lifecycle/ 已与 model-driven 同步", file=sys.stderr)

    in_sync = not (
        stage_diff["missing"]
        or stage_diff["extra"]
        or stage_diff["drift"]
        or gate_diff["missing"]
        or gate_diff["extra"]
        or gate_diff["drift"]
    )

    if args.json_output:
        print(
            json.dumps(
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "stage_diff": stage_diff,
                    "gate_diff": gate_diff,
                    "written_files": written_files,
                    "in_sync": in_sync,
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
    else:
        print(format_report(stage_diff, gate_diff))
        if args.sync and written_files:
            print(f"\n📝 已写盘: {len(written_files)} 个文件")

    if args.strict and (stage_diff["missing"] or gate_diff["missing"]):
        sys.exit(1)


if __name__ == "__main__":
    main()
