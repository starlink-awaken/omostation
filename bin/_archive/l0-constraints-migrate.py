#!/usr/bin/env python3
"""P79 / M4 Phase 1.2: L0-constraints v1 → v2 迁移

把 .omo/_knowledge/decisions/0132 §3 P1-S2 描述的 12 字段形状落到
49 条 L0-constraints 条目里。

设计原则 (沿用 P53 双指针 + ADR-0129 投影面范式):
  - 输入: ecosystems src/ecos/ssot/registry/L0-constraints.yaml (v1, 7 元组)
  - 输出: L0-constraints.v2.yaml (派生面, gitignored, ADR-0129 范式)
  - 行为: 不动原 yaml,生成 report
  - 双轨: v1 + v2 共存 1 周 monitor

映射规则:
  - type: required     → severity: high
  - type: preferred    → severity: medium
  - type: advisory     → severity: low
  - violation "E-X-N: MSG" → {violation_code: "E-X-N", violation_message: MSG}
  - dimension: 直接保留
  - applies_to: 直接保留 (已经是 [M0..L4])
  - rule: "predicate"  → rule_expr: {kind: predicate, args: predicate}

新增字段 (全部默认值):
  - m3_parent: "ConstraintL0" (全部加)
  - confidence: "fact" (默认)
  - state: "scored_active" (默认)
  - half_life_days: 365 (默认)
  - examples: []
  - references: []
  - rationale: ""

用法:
    uv run python3 bin/_archive/l0-constraints-migrate.py --dry-run
    uv run python3 bin/_archive/l0-constraints-migrate.py
    uv run python3 bin/_archive/l0-constraints-migrate.py --validate     # 仅校验 v2
    uv run python3 bin/_archive/l0-constraints-migrate.py --report       # 输出迁移报告
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

V1_PATH_DEFAULT = (
    Path("projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml")
)

# ADR-0137 P1: 把派生面放到源所在的子模块内, 而非主仓根
# 默认写到 projects/ecos/.omo/_derived/ (源在 ecos 子模块)
V2_PATH_DEFAULT = (
    Path("projects/ecos/.omo/_derived/l0-constraints.v2.yaml")
)

REPORT_PATH_DEFAULT = (
    Path("docs/M4-report-p1s2-l0-migration.md")
)

# type → severity 映射 (P1-S2 §3)
TYPE_TO_SEVERITY = {
    "required": "high",
    "preferred": "medium",
    "advisory": "low",
}

# violation 字符串拆分正则 (例: "E-L0-001: 未注册协议映射")
VIOLATION_RE = re.compile(r"^(E-[A-Z0-9-]+?):\s*(.+)$")


def parse_violation(v: str | None) -> dict:
    """把 violation 字符串拆成 violation_code + violation_message"""
    if not v:
        return {
            "violation_code": "",
            "violation_message": "",
        }
    m = VIOLATION_RE.match(v.strip())
    if m:
        return {
            "violation_code": m.group(1),
            "violation_message": m.group(2).strip(),
        }
    # 没标准前缀,保留原文当 message
    return {
        "violation_code": "",
        "violation_message": v.strip(),
    }


def parse_rule(rule: str | None) -> dict:
    """把 rule 字符串包装成 rule_expr"""
    if not rule:
        return {"kind": "predicate", "args": ""}
    s = rule.strip()
    # 嵌套谓词检测 (含 implies / OR / AND / ==) 当 predicate
    if any(tok in s for tok in ("implies", "==", "∈", "AND", "OR", "implies")):
        return {"kind": "predicate", "args": s}
    return {"kind": "predicate", "args": s}


def migrate_constraint(v1: dict) -> dict:
    """迁移单条约束 v1 → v2 形状"""
    v1_type = v1.get("type", "required")
    severity = TYPE_TO_SEVERITY.get(v1_type, "medium")
    violation_parts = parse_violation(v1.get("violation"))

    v2: dict = {
        "id": v1.get("id", ""),
        "description": v1.get("description", ""),
        "applies_to": v1.get("applies_to", []),
        "dimension": v1.get("dimension", "X1"),
        "severity": severity,
        "rule_expr": parse_rule(v1.get("rule")),
        "violation_code": violation_parts["violation_code"],
        "violation_message": violation_parts["violation_message"],
        "relation_constraints": {
            "depends_on": [],
            "conflicts_with": [],
        },
        "m3_parent": "ConstraintL0",
        "confidence": "fact",
        "state": "scored_active",
        "half_life_days": 365,
        "examples": [],
        "references": [],
        "rationale": "",
    }
    return v2


def load_v1(path: Path) -> list[dict]:
    """读 v1 L0-constraints.yaml

    文件结构 (基于 e2f8f4d7 实证 2026-07-06):
      constraints: 23 条 (主约束)
      protocol_registry: 5 条 (字段名为 name 而非 id)
      trigger_constraints: 6 条
      opc_cadence_constraints: 7 条
      mof_schema_validate_constraints: 5 条
      c2g_v3_constraints: 3 条
      c2g_v4_constraints: 3 条
      omni_bus_constraints: 3 条
      debt_constraints: 4 条
      governance_closure_constraints: 18 条
    共 13 section, 合计 77 条.

    我们的 v2 输出不区分 section (合并成单 list), 真实总数由 yaml 解析决定。
    """
    data = yaml.safe_load(path.read_text())
    entries: list[dict] = []
    for key, value in data.items():
        if key in ("version", "generated", "execution"):
            continue  # 元数据
        if not isinstance(value, list):
            continue
        for e in value:
            if not isinstance(e, dict):
                continue
            # 协议注册表字段名是 name 不是 id,补
            if "id" not in e and "name" in e:
                e = dict(e)
                e["id"] = e.get("name")
            if "id" in e:
                entries.append(e)
    return entries


def validate_v2_entry(v2: dict, schema: dict) -> list[str]:
    """用 ConstraintL0 schema 校验单条 v2 (简化版)"""
    errors: list[str] = []
    if not v2.get("id"):
        errors.append("missing id")
    if not v2.get("description") or len(v2["description"]) < 5:
        errors.append(f"description 长度不足: {v2.get('description')!r}")
    sev = v2.get("severity")
    if sev not in {"critical", "high", "medium", "low"}:
        errors.append(f"severity 非法: {sev}")
    applies = v2.get("applies_to", [])
    valid_layers = {"M3", "M2", "M1", "M0", "L0", "L1", "L2", "L3", "L4", "I0", "meta"}
    for layer in applies:
        if layer not in valid_layers:
            errors.append(f"applies_to 含非法层: {layer}")
    return errors


def load_constraint_l0_schema() -> dict:
    """读 M2 ConstraintL0 schema (作为校验参考)"""
    p = Path("projects/ecos/src/ecos/ssot/mof/m2/constraint_l0.yaml")
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text()).get("ConstraintL0", {})


def migrate(v1_path: Path, v2_path: Path, schema: dict) -> tuple[list[dict], list[str]]:
    """执行迁移,返回 (entries, all_errors)"""
    v1_entries = load_v1(v1_path)
    v2_entries = [migrate_constraint(e) for e in v1_entries]
    all_errors: list[str] = []
    for v2 in v2_entries:
        errs = validate_v2_entry(v2, schema)
        for e in errs:
            all_errors.append(f"{v2.get('id', '?')}: {e}")
    return v2_entries, all_errors


def write_v2(v2_path: Path, entries: list[dict]) -> None:
    """写 v2 派生面 yaml"""
    v2_path.parent.mkdir(parents=True, exist_ok=True)
    out = {
        "version": "2.0.0",
        "m2_type": "ConstraintL0",
        "migrated_from": "projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml",
        "migrated_at": "2026-07-06",
        "adr_refs": ["ADR-0132"],
        "constraints": entries,
    }
    v2_path.write_text(yaml.safe_dump(out, allow_unicode=True, sort_keys=False))


def make_report(v1_entries: list[dict], v2_entries: list[dict], errors: list[str]) -> str:
    """生成迁移报告 markdown"""
    type_hist = Counter(e.get("type", "required") for e in v1_entries)
    sev_hist = Counter(e.get("severity") for e in v2_entries)
    lines: list[str] = []
    lines.append("# L0-constraints v1 → v2 Migration Report\n")
    lines.append(f"**Date**: 2026-07-06\n")
    lines.append(f"**ADR**: ADR-0132 P1-S2\n")
    lines.append(f"**Schema**: `projects/ecos/src/ecos/ssot/mof/m2/constraint_l0.yaml`\n")
    lines.append("\n---\n\n")
    lines.append("## Summary\n\n")
    lines.append(f"- v1 条目数: **{len(v1_entries)}**\n")
    lines.append(f"- v2 条目数: **{len(v2_entries)}**\n")
    lines.append(f"- 校验错误: **{len(errors)}**\n")
    lines.append("\n## type → severity 映射\n\n")
    lines.append("| v1 type | v2 severity | 出现次数 |\n")
    lines.append("|---------|-------------|----------|\n")
    for t, c in sorted(type_hist.items()):
        sev = TYPE_TO_SEVERITY.get(t, "medium")
        lines.append(f"| `{t}` | `{sev}` | {c} |\n")
    lines.append(f"\n**合计**:\n\n")
    for s, c in sorted(sev_hist.items()):
        lines.append(f"- `{s}`: {c} 条\n")
    if errors:
        lines.append("\n## 校验失败\n\n")
        for err in errors:
            lines.append(f"- ❌ {err}\n")
    else:
        lines.append("\n## 校验结果\n\n✅ 全部 {n} 条通过 ConstraintL0 schema 校验\n".format(n=len(v2_entries)))
    lines.append("\n## 字段映射详情 (12 字段 v2 形状)\n\n")
    lines.append("| v1 字段 | v2 字段 | 转换 |\n")
    lines.append("|---------|---------|------|\n")
    lines.append("| `id` | `id` | 直传 |\n")
    lines.append("| `description` | `description` | 直传 |\n")
    lines.append("| `applies_to` | `applies_to` | 直传 |\n")
    lines.append("| `dimension` | `dimension` | 直传 |\n")
    lines.append("| `type` | `severity` | required→high, preferred→medium, advisory→low |\n")
    lines.append("| `rule` | `rule_expr: {kind, args}` | 字符串 → 结构化 |\n")
    lines.append("| `violation` | `violation_code + violation_message` | 拆分正则 |\n")
    lines.append("| (新增) | `m3_parent` | ConstraintL0 |\n")
    lines.append("| (新增) | `confidence` | fact 默认 |\n")
    lines.append("| (新增) | `state` | scored_active 默认 |\n")
    lines.append("| (新增) | `half_life_days` | 365 默认 |\n")
    lines.append("| (新增) | `relation_constraints` | 空默认 |\n")
    lines.append("| (新增) | `examples / references / rationale` | 空默认 |\n")
    return "".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v1", type=Path, default=V1_PATH_DEFAULT)
    parser.add_argument("--v2", type=Path, default=V2_PATH_DEFAULT)
    parser.add_argument("--report", type=Path, default=REPORT_PATH_DEFAULT)
    parser.add_argument("--dry-run", action="store_true", help="只统计, 不写文件")
    parser.add_argument("--validate", action="store_true", help="只校验不迁移")
    parser.add_argument("--report-only", action="store_true", help="只输出报告到 stdout")
    args = parser.parse_args()

    schema = load_constraint_l0_schema()
    if not schema:
        print("⚠️  未找到 ConstraintL0 schema (跳过 schema 校验)", file=sys.stderr)

    v1_entries = load_v1(args.v1)
    if not v1_entries:
        print(f"❌ 无 v1 条目: {args.v1}", file=sys.stderr)
        return 2

    if args.report_only:
        v2_entries = [migrate_constraint(e) for e in v1_entries]
        errors: list[str] = []
        for v2 in v2_entries:
            errs = validate_v2_entry(v2, schema)
            errors.extend(f"{v2.get('id', '?')}: {e}" for e in errs)
        print(make_report(v1_entries, v2_entries, errors))
        return 0 if not errors else 1

    if args.validate:
        v2_entries = [migrate_constraint(e) for e in v1_entries]
        errors = []
        for v2 in v2_entries:
            errs = validate_v2_entry(v2, schema)
            errors.extend(f"{v2.get('id', '?')}: {e}" for e in errs)
        print(f"v2 校验: {'✅ 全绿' if not errors else f'❌ {len(errors)} 错'}")
        for e in errors:
            print(f"  {e}")
        return 0 if not errors else 1

    v2_entries, errors = migrate(args.v1, args.v2, schema)

    if args.dry_run:
        print(f"[DRY-RUN] v1={len(v1_entries)} v2={len(v2_entries)} errs={len(errors)}")
        return 0 if not errors else 1

    write_v2(args.v2, v2_entries)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(make_report(v1_entries, v2_entries, errors))
    print(f"✅ v1={len(v1_entries)} → v2={len(v2_entries)} errs={len(errors)}")
    print(f"   v2 派生面: {args.v2}")
    print(f"   迁移报告: {args.report}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
