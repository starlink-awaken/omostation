#!/usr/bin/env python3
"""GaC MOF 元模型校验 (ADR-0106, 机制 7, 规则用 GacRule M2 type 约束).

机制 7 完整: gac 规则 (CR-*) 由 GacRule M2 type 元模型约束 (非 gac-validate 硬编码).
读 ecos m2/gac_rule.yaml (GacRule fields) + 校验 gac.rules 符合 M2.

价值: 规则结构改 M2 type (一处), 本工具自动校验 (声明式, DRY).
对标 gac-validate.py (硬编码 REQUIRED_FIELDS + enum) vs 本工具 (M2 type 驱动).

用法:
  python3 bin/gac-mof-validate.py          # M2 校验, exit 0=符合, 1=违反
  python3 bin/gac-mof-validate.py --report  # 详细 (含 M2 fields)
  python3 bin/gac-mof-validate.py --json    # JSON (cron/仪表盘)

CI 可移植: Path(__file__).resolve().parents[1].
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
M2 = (
    WORKSPACE
    / "projects"
    / "ecos"
    / "src"
    / "ecos"
    / "ssot"
    / "mof"
    / "m2"
    / "gac_rule.yaml"
)
REGISTRY = WORKSPACE / ".omo" / "_truth" / "registry" / "governance-checks.yaml"


def load_m2_fields() -> dict:
    """读 GacRule M2 type fields (元模型 schema 源).

    Phase 4A: 支持 requiredProperties + optionalProperties (mof-schema-validate.py 兼容格式).
    旧格式 fields (带 required: true/false) 仍兼容.
    """
    import yaml

    if not M2.exists():
        return {}
    docs = [d for d in yaml.safe_load_all(M2.read_text(encoding="utf-8")) if d]
    if not docs:
        return {}
    gac_rule = docs[-1].get("GacRule", {})

    # 新格式: requiredProperties + optionalProperties (mof-schema-validate.py 兼容)
    req = gac_rule.get("requiredProperties", {})
    opt = gac_rule.get("optionalProperties", {})
    if req or opt:
        # 合并, requiredProperties 的字段标记 required=true
        merged = {}
        for fname, fspec in req.items():
            merged[fname] = {**fspec, "required": True}
        for fname, fspec in opt.items():
            merged[fname] = {**fspec, "required": False}
        return merged

    # 旧格式: fields (带 required: true/false)
    return gac_rule.get("fields", {})


def load_rules() -> list[dict]:
    """读 gac.rules (CR-* 实例)."""
    import yaml

    if not REGISTRY.exists():
        return []
    docs = [d for d in yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")) if d]
    if not docs:
        return []
    return docs[-1].get("gac", {}).get("rules", [])


def validate_rule_m2(rule: dict, m2_fields: dict, idx: int) -> list[str]:
    """校验单条规则符合 GacRule M2 type. 返回 errors 列表."""
    errors: list[str] = []
    rid = rule.get("id", f"<rule#{idx}>")

    for fname, fspec in m2_fields.items():
        required = fspec.get("required", False)
        val = rule.get(fname)

        if required and (val is None or val == "" or val == []):
            errors.append(f"{rid}: 缺必填字段 '{fname}' (GacRule M2)")
            continue
        if val is None:
            continue

        # type 校验 (enum / list / string+pattern)
        ftype = fspec.get("type", "string")
        if ftype == "enum" and val not in fspec.get("values", []):
            errors.append(f"{rid}: {fname} '{val}' 不在 M2 enum {fspec.get('values')}")
        elif ftype == "list":
            item_values = fspec.get("item_values")
            if item_values and isinstance(val, list):
                for v in val:
                    if v not in item_values:
                        errors.append(
                            f"{rid}: {fname} item '{v}' 不在 M2 item_values {item_values}"
                        )
        elif ftype == "string":
            pattern = fspec.get("pattern")
            if pattern and not re.match(pattern, str(val)):
                errors.append(f"{rid}: {fname} '{val}' 不匹配 M2 pattern {pattern}")

    return errors


def main() -> int:
    args = sys.argv[1:]
    report_mode = "--report" in args
    json_mode = "--json" in args

    m2_fields = load_m2_fields()
    rules = load_rules()

    if not m2_fields:
        msg = "GacRule M2 fields 加载失败 (m2/gac_rule.yaml)"
        if json_mode:
            print(json.dumps({"ok": False, "error": msg}))
        else:
            print(f"❌ {msg}")
        return 1
    if not rules:
        msg = "gac.rules 为空"
        if json_mode:
            print(json.dumps({"ok": False, "error": msg}))
        else:
            print(f"❌ {msg}")
        return 1

    errors: list[str] = []
    for i, rule in enumerate(rules):
        errors.extend(validate_rule_m2(rule, m2_fields, i))

    ok = not errors

    if json_mode:
        print(
            json.dumps(
                {
                    "ok": ok,
                    "mechanism": 7,
                    "m2_type": "GacRule",
                    "m2_fields": len(m2_fields),
                    "rules": len(rules),
                    "errors": errors,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if ok else 1

    print("=== GaC MOF 元模型校验 (机制7, GacRule M2 约束) ===")
    print(f"M2 fields: {len(m2_fields)} | 规则数: {len(rules)}")

    if errors:
        print(f"\n❌ {len(errors)} M2 违反:")
        for e in errors:
            print(f"  - {e}")
    else:
        print(f"✅ 所有 {len(rules)} 规则符合 GacRule M2 type (机制 7 约束生效)")

    if report_mode:
        print("\nM2 fields 详情:")
        for fname, fspec in m2_fields.items():
            req = "必填" if fspec.get("required") else "可选"
            ftype = fspec.get("type", "?")
            print(f"  - {fname} ({ftype}, {req})")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
