#!/usr/bin/env python3
"""
织星 MOF — 跨仓本体推理引擎 (mof-derive) v2
============================================
桥接 model-driven (M3 元元模型) + ecos M2 schema + M1 实例节点。

推理类型 (替代原硬编码 M2 类型列表):
  1. 7 阶段覆盖 (STANDARD_STAGES) — 校验 7 阶段是否都有 M1 实例
  2. 4 门禁满足 (STANDARD_GATES) — 校验 4 门禁是否都有 M1 实例
  3. 3 Phase 评估 (PipelinePhase) — 当前 eCOS 处于哪个阶段, M1 覆盖度
  4. 风险推理 — 基于 M2 schema 的 5 类风险
  5. 缺口发现 — M1 节点缺失 / 多余 / 字段漂移

新增 SSOT 桥接 (2026-06-14 收口):
  - model-driven/src/model_driven/mof/m3_extended.py:STANDARD_STAGES
  - model-driven/src/model_driven/mof/m3_extended.py:STANDARD_GATES
  - model-driven/src/model_driven/lifecycle/pipeline.py:PipelinePhase

用法:
    cd projects/ecos
    python3 src/ecos/ssot/tools/mof-derive.py                    # 全量推理
    python3 src/ecos/ssot/tools/mof-derive.py --stages           # 仅 7 阶段覆盖
    python3 src/ecos/ssot/tools/mof-derive.py --gates            # 仅 4 门禁
    python3 src/ecos/ssot/tools/mof-derive.py --phases           # 仅 3 Phase
    python3 src/ecos/ssot/tools/mof-derive.py --impact=ID        # 影响分析
    python3 src/ecos/ssot/tools/mof-derive.py --json             # JSON 输出
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("FATAL: PyYAML not installed. Run: uv add pyyaml", file=sys.stderr)
    sys.exit(2)

# ── 路径 SSOT ──────────────────────────────────────────────
# 工具路径: src/ecos/ssot/tools/mof-derive.py
# 5 层 parent: ~/Workspace/projects/ecos (repo_root)
# 6 层 parent: ~/Workspace (workspace_root)
TOOL_PATH = Path(__file__).resolve()
REPO_ROOT = (
    TOOL_PATH.parent.parent.parent.parent.parent
)  # 5 层 = ~/Workspace/projects/ecos
WORKSPACE_ROOT = (
    TOOL_PATH.parent.parent.parent.parent.parent.parent.parent
)  # 7 层 = ~/Workspace

M2_DIR = REPO_ROOT / "src" / "ecos" / "ssot" / "mof" / "m2"
M1_DIR = REPO_ROOT / "src" / "ecos" / "ssot" / "mof" / "m1"

# model-driven 跨仓路径 (WORKSPACE_ROOT 已是 ~/Workspace)
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


# ── 加载 M2 schema ──────────────────────────────────────────


def load_m2_schemas() -> dict:
    """加载 M2 schema, 返回 {m2_type: schema_dict}"""
    schemas = {}
    if not M2_DIR.exists():
        return schemas
    for f in sorted(M2_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            print(f"⚠️  M2 schema parse fail: {f}: {e}", file=sys.stderr)
            continue
        if not isinstance(data, dict):
            continue
        mt = data.get("m2_type")
        if not mt:
            continue
        # 找 section dict (支持多种命名)
        section = (
            data.get(mt) or data.get(mt[0].lower() + mt[1:]) or data.get(mt.lower())
        )
        if section is None:
            top_other = [
                k for k in data if k not in ("m2_type", "version", "created", "updated")
            ]
            if top_other:
                section = {top_other[0]: None}
        if section:
            schemas[mt] = section
    return schemas


# ── 加载 M1 节点 ──────────────────────────────────────────


def load_m1_nodes() -> list[dict]:
    """加载 M1 实例节点, 返回 [{id, type, properties, ...}, ...]"""
    nodes = []
    if not M1_DIR.exists():
        return nodes
    for d in sorted(M1_DIR.iterdir()):
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.yaml")):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
            except yaml.YAMLError as e:
                print(f"⚠️  M1 parse fail: {f}: {e}", file=sys.stderr)
                continue
            if isinstance(data, dict) and "id" in data:
                data["_file"] = str(f.relative_to(REPO_ROOT))
                nodes.append(data)
    return nodes


# ── 加载 model-driven M3 (动态 import, 失败回退硬编码) ─────


def load_standard_stages() -> list[dict]:
    """从 model-driven/m3_extended.py 加载 7 阶段定义.

    失败回退到硬编码 (与 M3 源保持同步, 单向 SSOT 违规需人工修复).
    """
    fallback = [
        {"id": "STAGE-PLANNING", "order": 0, "stage": "planning", "name": "规划态"},
        {"id": "STAGE-DESIGN", "order": 1, "stage": "design", "name": "设计态"},
        {
            "id": "STAGE-DEVELOPMENT",
            "order": 2,
            "stage": "development",
            "name": "开发态",
        },
        {"id": "STAGE-DEPLOYMENT", "order": 3, "stage": "deployment", "name": "部署态"},
        {"id": "STAGE-RUNTIME", "order": 4, "stage": "runtime", "name": "运行态"},
        {"id": "STAGE-OPERATIONS", "order": 5, "stage": "operations", "name": "运维态"},
        {
            "id": "STAGE-BUSINESS-OPS",
            "order": 6,
            "stage": "business_ops",
            "name": "运营态",
        },
    ]
    if not MODEL_DRIVEN_M3.exists():
        return fallback
    try:
        sys.path.insert(0, str(MODEL_DRIVEN_M3.parent.parent.parent))
        from model_driven.mof.m3_extended import (  # type: ignore[reportMissingImports]
            STANDARD_STAGES,  # type: ignore[import-not-found]
        )

        return [
            {
                "id": s.id,
                "order": s.order,
                "stage": s.stage.value,
                "name": s.name,
                "entry_criteria": list(s.entry_criteria),
                "exit_criteria": list(s.exit_criteria),
                "core_activities": list(s.core_activities),
                "deliverables": list(s.deliverables),
                "stakeholders": list(s.stakeholders),
                "duration_target_days": s.duration_target_days,
            }
            for s in STANDARD_STAGES.values()
        ]
    except Exception as e:  # defensive fallback
        print(f"⚠️  M3 import 失败, 使用 fallback: {e}", file=sys.stderr)
        return fallback


def load_standard_gates() -> list[dict]:
    """从 model-driven/m3_extended.py 加载 4 门禁定义."""
    fallback = [
        {
            "id": "GATE-PLAN-TO-DESIGN",
            "from_stage": "planning",
            "to_stage": "design",
            "name": "规划→设计 门禁",
        },
        {
            "id": "GATE-DESIGN-TO-DEV",
            "from_stage": "design",
            "to_stage": "development",
            "name": "设计→开发 门禁",
        },
        {
            "id": "GATE-DEV-TO-DEPLOY",
            "from_stage": "development",
            "to_stage": "deployment",
            "name": "开发→部署 门禁",
        },
        {
            "id": "GATE-DEPLOY-TO-RUN",
            "from_stage": "deployment",
            "to_stage": "runtime",
            "name": "部署→运行 门禁",
        },
    ]
    if not MODEL_DRIVEN_M3.exists():
        return fallback
    try:
        sys.path.insert(0, str(MODEL_DRIVEN_M3.parent.parent.parent))
        from model_driven.mof.m3_extended import (  # type: ignore[reportMissingImports]
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
    except Exception as e:  # defensive fallback
        print(f"⚠️  M3 import 失败, 使用 fallback: {e}", file=sys.stderr)
        return fallback


def load_pipeline_phases() -> list[dict]:
    """从 model-driven/lifecycle/pipeline.py 加载 3 Phase 宏观流水线."""
    fallback = [
        {
            "id": "PHASE-COLD-START",
            "phase": "cold_start",
            "stages": ["planning", "design"],
            "name": "冷启动",
        },
        {
            "id": "PHASE-EVOLUTION",
            "phase": "evolution",
            "stages": ["development", "deployment"],
            "name": "演进",
        },
        {
            "id": "PHASE-HARDENING",
            "phase": "hardening",
            "stages": ["runtime", "operations", "business_ops"],
            "name": "硬化",
        },
    ]
    if not MODEL_DRIVEN_PIPELINE.exists():
        return fallback
    try:
        sys.path.insert(0, str(MODEL_DRIVEN_PIPELINE.parent.parent.parent))
        from model_driven.lifecycle.pipeline import (  # type: ignore[reportMissingImports]
            PipelinePhase,  # type: ignore[import-not-found]
        )

        return [
            {
                "id": f"PHASE-{p.value.upper().replace('_', '-')}",
                "phase": p.value,
                "stages": [s.value for s in PipelinePhase.get_stages(p)],
                "name": {
                    "cold_start": "冷启动",
                    "evolution": "演进",
                    "hardening": "硬化",
                }.get(p.value, p.value),
            }
            for p in PipelinePhase
        ]
    except Exception as e:  # defensive fallback
        print(f"⚠️  Pipeline import 失败, 使用 fallback: {e}", file=sys.stderr)
        return fallback


# ── 推理 1: 7 阶段覆盖 ──────────────────────────────────────


def derive_stage_coverage(m1_nodes: list[dict], standard_stages: list[dict]) -> dict:
    """7 阶段 vs M1 实例覆盖度, 返回 {covered, missing, extra, m1_by_stage}"""
    m1_by_stage = defaultdict(list)
    extra = []
    for n in m1_nodes:
        if n.get("type") != "Stage":
            continue
        props = n.get("properties") or {}
        stage = props.get("stage", "")
        nid = n.get("id", "?")
        if stage in {s["stage"] for s in standard_stages}:
            m1_by_stage[stage].append(
                {"id": nid, "file": n.get("_file"), "status": n.get("status")}
            )
        else:
            extra.append({"id": nid, "stage": stage, "file": n.get("_file")})

    covered = [s["stage"] for s in standard_stages if s["stage"] in m1_by_stage]
    missing = [s for s in standard_stages if s["stage"] not in m1_by_stage]
    return {
        "total": len(standard_stages),
        "covered": covered,
        "missing": missing,
        "extra": extra,
        "m1_by_stage": dict(m1_by_stage),
        "coverage_pct": round(100.0 * len(covered) / max(len(standard_stages), 1), 1),
    }


# ── 推理 2: 4 门禁覆盖 ──────────────────────────────────────


def derive_gate_coverage(m1_nodes: list[dict], standard_gates: list[dict]) -> dict:
    """4 门禁 vs M1 实例覆盖度, 同时校验 from_stage/to_stage 一致性."""
    m1_by_gate = defaultdict(list)
    inconsistent = []
    extra = []
    {g["id"].replace("GATE-", "").lower() for g in standard_gates}
    for n in m1_nodes:
        if n.get("type") != "Gate":
            continue
        props = n.get("properties") or {}
        nid = n.get("id", "?")
        # 匹配方式: M1 gate id 通常是 GATE-PLAN-TO-DESIGN, 跟标准 id 形似
        m1_key = nid.replace("GATE-", "").lower()
        from_s = props.get("from_stage", "")
        to_s = props.get("to_stage", "")
        # 在 standard_gates 中找匹配
        matched = None
        for sg in standard_gates:
            sg_key = sg["id"].replace("GATE-", "").lower()
            if m1_key == sg_key or (
                from_s == sg["from_stage"] and to_s == sg["to_stage"]
            ):
                matched = sg
                break
        if matched:
            # 校验 from_stage / to_stage 一致
            if from_s != matched["from_stage"] or to_s != matched["to_stage"]:
                inconsistent.append(
                    {
                        "id": nid,
                        "m1": f"{from_s} → {to_s}",
                        "std": f"{matched['from_stage']} → {matched['to_stage']}",
                    }
                )
            m1_by_gate[matched["stage"] if False else matched["id"]].append(
                {"id": nid, "file": n.get("_file")}
            )
        else:
            extra.append(
                {"id": nid, "from": from_s, "to": to_s, "file": n.get("_file")}
            )

    covered_ids = list(m1_by_gate.keys())
    missing = [g for g in standard_gates if g["id"] not in covered_ids]
    return {
        "total": len(standard_gates),
        "covered": covered_ids,
        "missing": missing,
        "extra": extra,
        "inconsistent": inconsistent,
        "m1_by_gate": dict(m1_by_gate),
        "coverage_pct": round(
            100.0 * len(covered_ids) / max(len(standard_gates), 1), 1
        ),
    }


# ── 推理 3: 3 Phase 评估 ───────────────────────────────────


def derive_phase_assessment(
    m1_nodes: list[dict], pipeline_phases: list[dict], gate_cov: dict
) -> dict:
    """3 Phase 评估: 哪一阶段最完整, 哪一阶段最欠缺.

    指标: M1 阶段节点数 + M1 门禁数 + 各 phase 的 completeness
    """
    by_type = Counter(n.get("type", "?") for n in m1_nodes)
    stage_count = by_type.get("Stage", 0)
    gate_count = by_type.get("Gate", 0)

    phase_assessment = []
    for p in pipeline_phases:
        stage_ids = set(p["stages"])
        # 找该 phase 包含的 stage 节点的 m1 状态
        phase_stages = []
        for sid in stage_ids:
            phase_stages.append(sid)
        phase_assessment.append(
            {
                "phase": p["phase"],
                "name": p["name"],
                "stages": stage_ids,
                "stage_count_in_phase": len(stage_ids),
            }
        )

    # 当前 eCOS Phase 判定: 哪个 phase 包含最多的 done 状态 Stage 节点
    done_stages = set()
    for n in m1_nodes:
        if n.get("type") == "Stage" and n.get("status") == "active":
            done_stages.add((n.get("properties") or {}).get("stage", ""))
    current_phase = "unknown"
    for p in pipeline_phases:
        if all(s in done_stages for s in p["stages"]):
            current_phase = p["phase"]
            break

    return {
        "stage_total": stage_count,
        "gate_total": gate_count,
        "current_phase": current_phase,
        "phases": phase_assessment,
    }


# ── 推理 4: 风险 ──────────────────────────────────────────


def derive_risks(
    m1_nodes: list[dict], stage_cov: dict, gate_cov: dict, m2_schemas: dict
) -> list[dict]:
    """5 类风险:
    R1: Stage 缺失 (>0 个 standard stage 无 M1 实例)
    R2: Gate 缺失
    R3: Gate 状态不一致 (from_stage/to_stage 与 standard 不符)
    R4: Stage 多余 (M1 有但 standard 没有)
    R5: M2 type 漂移 (M1 type 不在 M2 schema)
    """
    risks = []
    # R1
    if stage_cov["missing"]:
        risks.append(
            {
                "id": "R1-STAGE-MISSING",
                "severity": "high",
                "detail": f"{len(stage_cov['missing'])} 个 standard stage 缺 M1 实例: {[s['id'] for s in stage_cov['missing']]}",
            }
        )
    # R2
    if gate_cov["missing"]:
        risks.append(
            {
                "id": "R2-GATE-MISSING",
                "severity": "high",
                "detail": f"{len(gate_cov['missing'])} 个 standard gate 缺 M1 实例: {[g['id'] for g in gate_cov['missing']]}",
            }
        )
    # R3
    if gate_cov["inconsistent"]:
        risks.append(
            {
                "id": "R3-GATE-INCONSISTENT",
                "severity": "medium",
                "detail": f"{len(gate_cov['inconsistent'])} 个 M1 gate from_stage/to_stage 与 standard 不符",
                "examples": gate_cov["inconsistent"][:3],
            }
        )
    # R4
    if stage_cov["extra"]:
        risks.append(
            {
                "id": "R4-STAGE-EXTRA",
                "severity": "low",
                "detail": f"{len(stage_cov['extra'])} 个 M1 stage 不在 standard 列表 (可能已废弃)",
                "examples": stage_cov["extra"][:3],
            }
        )
    # R5
    type_aliases = set()
    for mt in m2_schemas:
        type_aliases.add(mt)
        type_aliases.add(mt[0].lower() + mt[1:])
        type_aliases.add(mt.lower())
    drift = [
        (n["id"], n.get("type")) for n in m1_nodes if n.get("type") not in type_aliases
    ]
    if drift:
        risks.append(
            {
                "id": "R5-TYPE-DRIFT",
                "severity": "high",
                "detail": f"{len(drift)} 个 M1 节点 type 不在 M2 schema",
                "examples": drift[:5],
            }
        )
    return risks


# ── 推理 5: 影响分析 ──────────────────────────────────────


def derive_impact(m1_nodes: list[dict], target_id: str) -> dict:
    """推导 target M1 节点的影响范围 (同 layer / 同 domain / 引用同一 m3_parent)."""
    target = None
    for n in m1_nodes:
        if n.get("id") == target_id:
            target = n
            break
    if not target:
        return {"error": f"未找到节点: {target_id}"}

    target_layer = target.get("layer", "")
    target_domain = target.get("domain", "")
    target_props = target.get("properties") or {}
    target_m3 = target_props.get("m3_parent", target.get("m3_parent", ""))

    direct = []
    same_m3 = []
    for n in m1_nodes:
        if n.get("id") == target_id:
            continue
        if n.get("layer") == target_layer or n.get("domain") == target_domain:
            direct.append(n["id"])
        np = n.get("properties") or {}
        if target_m3 and (
            np.get("m3_parent") == target_m3 or n.get("m3_parent") == target_m3
        ):
            same_m3.append(n["id"])

    return {
        "target": target_id,
        "layer": target_layer,
        "domain": target_domain,
        "m3_parent": target_m3,
        "direct_same_layer_or_domain": direct[:20],
        "same_m3_parent": same_m3[:20],
        "direct_count": len(direct),
        "same_m3_count": len(same_m3),
    }


# ── 报告输出 ──────────────────────────────────────────────


def format_report(stage_cov, gate_cov, phase_assess, risks) -> str:
    lines = []
    lines.append("=" * 72)
    lines.append("  织星 MOF — 跨仓本体推理报告 (v2 model-driven 桥接)")
    lines.append("=" * 72)
    lines.append(f"  时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # 7 阶段覆盖
    lines.append("  ── 7 阶段覆盖 (model-driven STANDARD_STAGES) ──")
    lines.append(
        f"     覆盖率: {stage_cov['coverage_pct']}%  ({len(stage_cov['covered'])}/{stage_cov['total']})"
    )
    for sid in [
        s["stage"] for s in stage_cov.get("m1_by_stage", {}).keys() if False
    ] + list(stage_cov["covered"]):
        ms = stage_cov["m1_by_stage"].get(sid, [])
        lines.append(f"     ✓ {sid:18} ({len(ms)} M1 实例)")
    if stage_cov["missing"]:
        lines.append(f"     ✗ 缺失: {[s['id'] for s in stage_cov['missing']]}")
    if stage_cov["extra"]:
        lines.append(f"     ⚠ 多余: {[e['id'] for e in stage_cov['extra']]}")
    lines.append("")

    # 4 门禁覆盖
    lines.append("  ── 4 门禁覆盖 (model-driven STANDARD_GATES) ──")
    lines.append(
        f"     覆盖率: {gate_cov['coverage_pct']}%  ({len(gate_cov['covered'])}/{gate_cov['total']})"
    )
    for gid in gate_cov["covered"]:
        mg = gate_cov["m1_by_gate"].get(gid, [])
        lines.append(f"     ✓ {gid:24} ({len(mg)} M1 实例)")
    if gate_cov["missing"]:
        lines.append(f"     ✗ 缺失: {[g['id'] for g in gate_cov['missing']]}")
    if gate_cov["inconsistent"]:
        lines.append(f"     ⚠ 不一致: {[i['id'] for i in gate_cov['inconsistent']]}")
    if gate_cov["extra"]:
        lines.append(f"     ⚠ 多余: {[e['id'] for e in gate_cov['extra']]}")
    lines.append("")

    # 3 Phase 评估
    lines.append("  ── 3 Phase 评估 (model-driven PipelinePhase) ──")
    lines.append(f"     当前 eCOS Phase: {phase_assess['current_phase']}")
    lines.append(
        f"     Stage 实例总数: {phase_assess['stage_total']}  |  Gate 实例总数: {phase_assess['gate_total']}"
    )
    for p in phase_assess["phases"]:
        lines.append(
            f"     📍 {p['phase']:12} ({p['name']}) 含 {p['stage_count_in_phase']} stages: {p['stages']}"
        )
    lines.append("")

    # 风险
    lines.append(f"  ── 风险推理 ({len(risks)} 项) ──")
    if risks:
        for r in risks:
            icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(r["severity"], "⚪")
            lines.append(f"  {icon} [{r['id']}] {r['detail']}")
    else:
        lines.append("  ✅ 未发现风险")
    lines.append("")

    lines.append("=" * 72)
    return "\n".join(lines)


# ── main ──────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="MOF 跨仓本体推理引擎 (model-driven 桥接)"
    )
    parser.add_argument("--stages", action="store_true", help="仅 7 阶段覆盖")
    parser.add_argument("--gates", action="store_true", help="仅 4 门禁")
    parser.add_argument("--phases", action="store_true", help="仅 3 Phase")
    parser.add_argument("--risks", action="store_true", help="仅风险")
    parser.add_argument("--impact", type=str, help="影响分析 (target M1 id)")
    parser.add_argument(
        "--json", dest="json_output", action="store_true", help="JSON 输出"
    )
    parser.add_argument(
        "--strict", action="store_true", help="有 high 风险时退出码非 0"
    )
    parser.add_argument(
        "--gac-check",
        action="store_true",
        help="派生后附 GaC M2 drift 检查 (调 bin/gac-mof-validate.py, ADR-0106 机制7 ecos↔GaC 集成)",
    )
    args = parser.parse_args()

    # 加载 SSOT
    m1_nodes = load_m1_nodes()
    m2_schemas = load_m2_schemas()
    standard_stages = load_standard_stages()
    standard_gates = load_standard_gates()
    pipeline_phases = load_pipeline_phases()

    # 影响分析模式
    if args.impact:
        impact = derive_impact(m1_nodes, args.impact)
        if args.json_output:
            print(json.dumps(impact, ensure_ascii=False, indent=2))
        else:
            if "error" in impact:
                print(f"❌ {impact['error']}")
            else:
                print(f"🎯 影响分析: {impact['target']}")
                print(f"   Layer: {impact['layer']}  |  Domain: {impact['domain']}")
                print(f"   m3_parent: {impact['m3_parent']}")
                print(f"   同 layer/domain: {impact['direct_count']} 个")
                print(f"   同 m3_parent:   {impact['same_m3_count']} 个")
                if impact["same_m3_parent"]:
                    print(f"   示例: {impact['same_m3_parent'][:5]}")
        return

    # 推理
    stage_cov = derive_stage_coverage(m1_nodes, standard_stages)
    gate_cov = derive_gate_coverage(m1_nodes, standard_gates)
    phase_assess = derive_phase_assessment(m1_nodes, pipeline_phases, gate_cov)
    risks = derive_risks(m1_nodes, stage_cov, gate_cov, m2_schemas)

    if args.json_output:
        print(
            json.dumps(
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "stage_coverage": stage_cov,
                    "gate_coverage": gate_cov,
                    "phase_assessment": phase_assess,
                    "risks": risks,
                    "ok": not any(r["severity"] == "high" for r in risks),
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
    else:
        # 分区域输出 (--stages / --gates / --phases / --risks 单项模式)
        if args.stages:
            print(f"=== 7 阶段覆盖: {stage_cov['coverage_pct']}% ===")
            print(f"covered: {stage_cov['covered']}")
            print(f"missing: {[s['id'] for s in stage_cov['missing']]}")
            print(f"extra:   {[e['id'] for e in stage_cov['extra']]}")
        elif args.gates:
            print(f"=== 4 门禁覆盖: {gate_cov['coverage_pct']}% ===")
            print(f"covered: {gate_cov['covered']}")
            print(f"missing: {[g['id'] for g in gate_cov['missing']]}")
            print(f"inconsistent: {[i['id'] for i in gate_cov['inconsistent']]}")
            print(f"extra:   {[e['id'] for e in gate_cov['extra']]}")
        elif args.phases:
            print("=== 3 Phase 评估 ===")
            print(f"current_phase: {phase_assess['current_phase']}")
            for p in phase_assess["phases"]:
                print(f"  {p['phase']:12} {p['stages']}")
        elif args.risks:
            for r in risks:
                icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                    r["severity"], "⚪"
                )
                print(f"  {icon} [{r['id']}] {r['detail']}")
        else:
            print(format_report(stage_cov, gate_cov, phase_assess, risks))

    # GaC M2 drift 检查 (ecos mof-derive ↔ GaC 机制7 集成, ADR-0106 第3项)
    if args.gac_check:
        import subprocess as _sp
        from pathlib import Path as _Path

        workspace = (
            _Path(__file__).resolve().parents[6]
        )  # tools→ssot→ecos→src→projects→workspace
        gac_tool = workspace / "bin" / "gac-mof-validate.py"
        if gac_tool.exists():
            print("\n=== GaC M2 drift (gac-mof-validate, ecos↔GaC 集成) ===")
            _r = _sp.run(
                ["python3", str(gac_tool)],
                capture_output=True,
                text=True,
                cwd=str(workspace),
            )
            print((_r.stdout or _r.stderr or "(无输出)")[-600:])
        else:
            print(f"\n⚠️ gac-mof-validate 未找到: {gac_tool}")

    if args.strict and any(r["severity"] == "high" for r in risks):
        sys.exit(1)


if __name__ == "__main__":
    main()
