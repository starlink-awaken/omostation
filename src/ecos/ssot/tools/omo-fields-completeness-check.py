#!/usr/bin/env python3
"""
omo-fields-completeness-check — OMOTask 字段完整性校验
====================================================
校验所有 OMOTask M1 节点 (src/ecos/ssot/mof/m1/omo_layer/OMOTASK-*.yaml) 字段完整性,
按 OMOTask M2 schema (omo_task.yaml) optionalProperties 规则:

- prerequisites (前置任务): 强烈推荐 (业务关联)
- sub_gates (子 Gate): RoadmapPhase (subtype=RoadmapPhase) 必填 ≥3
- signals (持续信号): 推荐
- red_lines (红线): 推荐
- evidence (证据): gate_status=passed 必填 ≥1
- phase_open_condition (阶段开启条件): RoadmapPhase 推荐
- phase_blocked_condition (阶段阻塞条件): 推荐
- final_close_condition (最终关闭条件): 推荐
- forbidden_claims (禁止声明): 推荐
- assessment (验收评估): 推荐
- gate_note (Gate 备注): 推荐

按 subtype 分级校验:
- RoadmapPhase (OPC-): 严格校验 (P0-P7 路线图)
- Task (其他): 基础校验 (required + sub_gates ≥1 或 tasks ≥1)

用法:
    cd projects/ecos
    python3 src/ecos/ssot/tools/omo-fields-completeness-check.py            # 完整报告
    python3 src/ecos/ssot/tools/omo-fields-completeness-check.py --strict  # 失完整退出码 1
    python3 src/ecos/ssot/tools/omo-fields-completeness-check.py --json    # JSON 输出
    python3 src/ecos/ssot/tools/omo-fields-completeness-check.py --subtype RoadmapPhase  # 仅某 subtype
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

# ── 路径 SSOT ──────────────────────────────────────────────
TOOL_PATH = Path(__file__).resolve()
REPO_ROOT = TOOL_PATH.parent.parent.parent.parent.parent  # 5 层

M1_OMO_LAYER = REPO_ROOT / "src" / "ecos" / "ssot" / "mof" / "m1" / "omo_layer"

# OMOTask M2 schema optionalProperties 完整字段
OMOTASK_OPTIONAL_FIELDS = [
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
]

# RoadmapPhase 严格必填 (P0-P7 OPC 路线图)
ROADMAP_REQUIRED = [
    "prerequisites",
    "sub_gates",
    "red_lines",
    "phase_open_condition",
    "phase_blocked_condition",
    "final_close_condition",
    "forbidden_claims",
    "evidence",
    "assessment",
]


# ── 加载 ──────────────────────────────────────────────────


def load_omotask_m1() -> list[dict]:
    """加载 M1 OMOTASK-* 节点."""
    nodes = []
    if not M1_OMO_LAYER.exists():
        return nodes
    for f in sorted(M1_OMO_LAYER.glob("OMOTASK-*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if isinstance(data, dict) and "id" in data:
            data["_file"] = str(f.relative_to(REPO_ROOT))
            nodes.append(data)
    return nodes


# ── 校验 ──────────────────────────────────────────────────


def check_node(node: dict) -> dict:
    """校验单个 OMOTask 节点字段完整性."""
    issues = []
    nid = node.get("id", "?")
    subtype = node.get("subtype", "Task")
    status = node.get("status", "unknown")
    gate_status = node.get("gate_status", "")
    properties = node.get("properties") or {}

    # 1. 必填 (顶层)
    for f in ("id", "type", "status"):
        if not node.get(f):
            issues.append({"field": f, "level": "error", "msg": f"缺失必填字段 {f}"})

    # 2. status 必是 OMOTask M2 schema stateMachine 合法值
    valid_statuses = {
        "proposed",
        "in_progress",
        "review",
        "done",
        "blocked",
        "archived",
    }
    if status not in valid_statuses:
        issues.append(
            {
                "field": "status",
                "level": "error",
                "msg": f"status={status!r} 不在 OMOTask stateMachine {valid_statuses}",
            }
        )

    # 3. type 必是 OMOTask
    if node.get("type") != "OMOTask":
        issues.append(
            {
                "field": "type",
                "level": "error",
                "msg": f"type={node.get('type')!r}, 必为 OMOTask",
            }
        )

    # 4. gate_status=passed implies evidence>=1 (M2 validationRules 硬约束)
    if gate_status == "passed":
        ev = properties.get("evidence")
        if not ev or not isinstance(ev, list) or len(ev) < 1:
            issues.append(
                {
                    "field": "evidence",
                    "level": "error",
                    "msg": "gate_status=passed 必填 ≥1 evidence (M2 validationRules 硬约束)",
                }
            )

    # 5. sub_gates / tasks 必填 ≥1 (业务节点)
    sub = properties.get("sub_gates")
    tasks = properties.get("tasks")
    if not sub and not tasks:
        issues.append(
            {
                "field": "sub_gates",
                "level": "warning",
                "msg": "sub_gates/tasks 都缺, 业务可追溯性 0",
            }
        )
    elif sub and isinstance(sub, list) and len(sub) < 3 and subtype == "RoadmapPhase":
        issues.append(
            {
                "field": "sub_gates",
                "level": "warning",
                "msg": f"sub_gates count = {len(sub)} (RoadmapPhase 推荐 ≥3)",
            }
        )

    # 6. RoadmapPhase 严格必填
    if subtype == "RoadmapPhase":
        for f in ROADMAP_REQUIRED:
            if f not in properties or not properties[f]:
                issues.append(
                    {
                        "field": f,
                        "level": "warning",
                        "msg": f"RoadmapPhase 推荐字段 {f} 缺失",
                    }
                )

    # 7. signals 推荐 (持续信号)
    if not properties.get("signals"):
        issues.append(
            {
                "field": "signals",
                "level": "info",
                "msg": "signals 缺失 (持续信号, 治理闭环推荐)",
            }
        )

    # 8. m3_parent 反向追溯
    if not properties.get("m3_parent"):
        issues.append(
            {
                "field": "m3_parent",
                "level": "info",
                "msg": "m3_parent 缺失 (反向追溯 model-driven, AGENTS.md 铁律 2)",
            }
        )

    return {
        "id": nid,
        "subtype": subtype,
        "status": status,
        "gate_status": gate_status,
        "issue_count": len(issues),
        "error_count": sum(1 for i in issues if i["level"] == "error"),
        "warning_count": sum(1 for i in issues if i["level"] == "warning"),
        "info_count": sum(1 for i in issues if i["level"] == "info"),
        "issues": issues,
    }


# ── 报告 ──────────────────────────────────────────────────


def format_report(checks: list[dict]) -> str:
    lines = []
    lines.append("=" * 72)
    lines.append("  omo-fields-completeness-check — OMOTask 字段完整性校验")
    lines.append("=" * 72)
    lines.append(f"  时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    total = len(checks)
    by_subtype = Counter(c["subtype"] for c in checks)
    by_status = Counter(c["status"] for c in checks)
    error_count = sum(c["error_count"] for c in checks)
    warning_count = sum(c["warning_count"] for c in checks)
    info_count = sum(c["info_count"] for c in checks)
    full_count = sum(1 for c in checks if c["issue_count"] == 0)

    lines.append("  ── 统计 ──")
    lines.append(f"  节点总数: {total}")
    lines.append(
        f"  完全完整 (0 issue): {full_count} ({full_count * 100 / max(total, 1):.1f}%)"
    )
    lines.append(
        f"  error: {error_count} | warning: {warning_count} | info: {info_count}"
    )
    lines.append("")
    lines.append(f"  按 subtype: {dict(by_subtype)}")
    lines.append(f"  按 status: {dict(by_status)}")
    lines.append("")

    # 按字段 issue 排行
    field_counter = Counter()
    for c in checks:
        for i in c["issues"]:
            field_counter[(i["field"], i["level"])] += 1
    if field_counter:
        lines.append("  ── 字段 issue 排行 (TOP 10) ──")
        for (field, level), count in field_counter.most_common(10):
            lines.append(f"    {field:30} {level:8} {count}x")
        lines.append("")

    # 不完整节点
    incomplete = [c for c in checks if c["issue_count"] > 0]
    if incomplete:
        lines.append(f"  ── 不完整节点 ({len(incomplete)}) ──")
        for c in incomplete[:20]:
            err = c["error_count"]
            warn = c["warning_count"]
            info = c["info_count"]
            lines.append(f"    {c['id']:50} err={err} warn={warn} info={info}")
        if len(incomplete) > 20:
            lines.append(f"    ... ({len(incomplete) - 20} more)")
        lines.append("")

    # 状态判定
    if error_count == 0 and warning_count == 0:
        lines.append("  ── 状态 ──")
        lines.append("  ✅ 全部节点字段完整 (0 error + 0 warning)")
    elif error_count == 0:
        lines.append("  ── 状态 ──")
        lines.append(
            f"  🟡 字段完整, 仅 info/warning 缺失 (error=0, warning={warning_count})"
        )
    else:
        lines.append("  ── 状态 ──")
        lines.append(
            f"  ⚠️  {error_count} 个 error (gate_status=passed 缺 evidence 等硬约束违反)"
        )

    lines.append("=" * 72)
    return "\n".join(lines)


# ── main ──────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="OMOTask 字段完整性校验")
    parser.add_argument("--strict", action="store_true", help="有 error 时退出码 1")
    parser.add_argument(
        "--json", dest="json_output", action="store_true", help="JSON 输出"
    )
    parser.add_argument("--subtype", help="仅校验某 subtype (e.g. RoadmapPhase)")
    args = parser.parse_args()

    nodes = load_omotask_m1()
    if args.subtype:
        nodes = [n for n in nodes if n.get("subtype") == args.subtype]

    checks = [check_node(n) for n in nodes]

    if args.json_output:
        print(
            json.dumps(
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "total": len(checks),
                    "full_count": sum(1 for c in checks if c["issue_count"] == 0),
                    "error_count": sum(c["error_count"] for c in checks),
                    "warning_count": sum(c["warning_count"] for c in checks),
                    "info_count": sum(c["info_count"] for c in checks),
                    "checks": checks,
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
    else:
        print(format_report(checks))

    if args.strict:
        error_count = sum(c["error_count"] for c in checks)
        if error_count > 0:
            sys.exit(1)


if __name__ == "__main__":
    main()
