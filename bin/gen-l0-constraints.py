#!/usr/bin/env python3
"""gen-l0-constraints.py — 从 L0 源重新生成 L0 派生面 (自动更新闭环)

依据 .omo/_knowledge/patterns/doc-l0-mof-mapping-governance.md 长期轨道:
L0 派生生成器从 bin/_archive/l0-constraints-migrate.py 复活为正式工具.

输入:  projects/ecos/src/ecos/l0/constraints.yaml (v3 源, 28 constraints + registries)
输出:  projects/ecos/.omo/_derived/l0-constraints.v2.yaml (v2 派生面, 77 条)

映射逻辑 (复用原 migrate_constraint, 12 字段 v2 形状):
  id/description/applies_to/dimension 直传
  type→severity: required→high, preferred→medium, advisory→low
  rule→rule_expr: {kind, args} 结构化
  violation→violation_code + violation_message 拆分
  新增: m3_parent=ConstraintL0, confidence=fact, state=scored_active,
        half_life_days=365, relation_constraints=[], examples/references/rationale

用法:
    python3 projects/ecos/bin/gen-l0-constraints.py           # 生成
    python3 projects/ecos/bin/gen-l0-constraints.py --dry-run # 只统计
    python3 projects/ecos/bin/gen-l0-constraints.py --validate # 只校验

退出码: 0=通过, 1=校验失败, 2=源缺失
"""

import argparse
import re
import sys
from pathlib import Path

ECOS_ROOT = Path(__file__).resolve().parents[1]
V3_SOURCE = ECOS_ROOT / "src" / "ecos" / "l0" / "constraints.yaml"
V1_REGISTRY = ECOS_ROOT / "src" / "ecos" / "ssot" / "registry" / "L0-constraints.yaml"
V2_DERIVED = ECOS_ROOT / ".omo" / "_derived" / "l0-constraints.v2.yaml"
M2_SCHEMA = ECOS_ROOT / "src" / "ecos" / "ssot" / "mof" / "m2" / "constraint_l0.yaml"

TYPE_TO_SEVERITY = {"required": "high", "preferred": "medium", "advisory": "low"}


def load_v3(path: Path) -> list[dict]:
    """从 v3 源加载全部约束条目 (constraints + domain_registry + protocol_registry)."""
    import yaml

    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return []
    entries: list[dict] = []
    for section in ("constraints", "domain_registry", "protocol_registry"):
        for item in data.get(section, []) or []:
            if isinstance(item, dict) and item.get("id"):
                entries.append(item)
    return entries


def load_v1_registry(path: Path) -> list[dict]:
    """从 v1 registry 加载全部约束条目 (constraints + 各 *_constraints section).

    v1 registry 含 58 条 CR-* 约束 (governance 系), 是现有 77 条派生面的主要来源.
    """
    import yaml

    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return []
    entries: list[dict] = []
    for key, val in data.items():
        if not key.endswith("constraints"):
            continue
        if not isinstance(val, list):
            continue
        for item in val:
            if isinstance(item, dict) and item.get("id"):
                entries.append(item)
    return entries


def migrate_constraint(v1: dict) -> dict:
    """v3 条目 → v2 派生条目 (12 字段形状, 复用原 migrate_constraint 逻辑)."""
    rule = v1.get("rule", "")
    rule_expr = (
        {"kind": "expr", "args": [rule]} if isinstance(rule, str) and rule else {}
    )

    violation = v1.get("violation", "")
    vio_code = "E-L0-000"
    vio_msg = violation
    if isinstance(violation, str):
        m = re.match(r"^([A-Z0-9-]+):\s*(.+)$", violation.strip())
        if m:
            vio_code, vio_msg = m.group(1), m.group(2)

    v2 = {
        "id": v1.get("id"),
        "description": v1.get("description", ""),
        "applies_to": v1.get("applies_to") or ["L0"],
        "dimension": v1.get("dimension", "X1"),
        "severity": TYPE_TO_SEVERITY.get(v1.get("type", "required"), "medium"),
        "rule_expr": rule_expr,
        "violation_code": vio_code,
        "violation_message": vio_msg,
        "m3_parent": "ConstraintL0",
        "confidence": "fact",
        "state": "scored_active",
        "half_life_days": 365,
        "relation_constraints": [],
    }
    for opt in ("examples", "references", "rationale"):
        if v1.get(opt):
            v2[opt] = v1[opt]
    return v2


def validate_v2_entry(v2: dict, schema: dict | None) -> list[str]:
    """校验 v2 条目 (必填字段 + 维度值域)."""
    errs: list[str] = []
    for key in (
        "id",
        "description",
        "dimension",
        "severity",
        "violation_code",
        "m3_parent",
    ):
        if not v2.get(key):
            errs.append(f"缺 {key}")
    valid_dims = ("X1", "X2", "X3", "X4", "X5", "X6", "X7", "QG")
    if v2.get("dimension") and v2["dimension"] not in valid_dims:
        errs.append(f"dimension={v2['dimension']} 不在 {valid_dims}")
    if v2.get("m3_parent") != "ConstraintL0":
        errs.append(f"m3_parent={v2.get('m3_parent')} != ConstraintL0")
    if not v2.get("applies_to"):
        errs.append("缺 applies_to")
    return errs


def write_v2(v2_path: Path, entries: list[dict]) -> None:
    """写 v2 派生面 yaml (保持 12 字段 + 元信息)."""
    import yaml

    v2_path.parent.mkdir(parents=True, exist_ok=True)
    out = {
        "version": "2.0.0",
        "m2_type": "ConstraintL0",
        "migrated_from": "projects/ecos/src/ecos/l0/constraints.yaml",
        "generated_by": "projects/ecos/bin/gen-l0-constraints.py",
        "adr_refs": ["ADR-0132"],
        "constraints": entries,
    }
    v2_path.write_text(yaml.safe_dump(out, allow_unicode=True, sort_keys=False))


def validate_entries(entries: list[dict], schema: dict | None) -> list[str]:
    errors: list[str] = []
    for v2 in entries:
        errs = validate_v2_entry(v2, schema)
        errors.extend(f"{v2.get('id', '?')}: {e}" for e in errs)
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="只统计不写文件")
    ap.add_argument("--validate", action="store_true", help="只校验不生成")
    args = ap.parse_args()

    entries = load_v1_registry(V1_REGISTRY) + load_v3(V3_SOURCE)
    # 按 id 去重 (v3 后写覆盖 v1, v3 优先)
    seen: dict[str, dict] = {}
    for e in entries:
        seen[e.get("id")] = e
    entries = list(seen.values())
    if not entries:
        print(f"❌ 源无约束条目: {V3_SOURCE} / {V1_REGISTRY}", file=sys.stderr)
        return 2

    schema = None
    if M2_SCHEMA.exists():
        try:
            import yaml

            schema = yaml.safe_load(M2_SCHEMA.read_text(encoding="utf-8"))
        except (yaml.YAMLError, OSError):
            schema = None

    v2_entries = [migrate_constraint(e) for e in entries]
    errors = validate_entries(v2_entries, schema)

    if args.validate:
        for e in errors:
            print(f"[FAIL] {e}", file=sys.stderr)
        print(
            f"[{'FAIL' if errors else 'OK'}] {len(v2_entries)} 条校验, {len(errors)} 错误"
        )
        return 1 if errors else 0

    if args.dry_run:
        print(f"[DRY-RUN] 源: {V3_SOURCE}")
        print(f"[DRY-RUN] 将生成 {len(v2_entries)} 条 → {V2_DERIVED}")
        sev = {}
        for v2 in v2_entries:
            sev[v2["severity"]] = sev.get(v2["severity"], 0) + 1
        print(f"[DRY-RUN] severity 分布: {sev}")
        return 1 if errors else 0

    write_v2(V2_DERIVED, v2_entries)
    print(f"[OK] 生成 {len(v2_entries)} 条 → {V2_DERIVED}")
    if errors:
        for e in errors:
            print(f"[WARN] {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
