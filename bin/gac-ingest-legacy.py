#!/usr/bin/env python3
"""gac-ingest-legacy — 收敛 X1-X4 原有规则到 GaC indexed 层 (统一收敛, 消除多套并行).

把 .omo/_truth/x{1,2,4}-*.yaml 的 policy/rule 纳管为 GaC indexed 条目.
GaC 成为全域规则索引层 (统一执行入口 + drift 检测), 原有规则保留为富语义 SSOT.

收敛 SSOT 边界 (核心):
  native  → GaC 是 SSOT (规则定义 + 执行都在 GaC)
  indexed → 原有源是策略 SSOT (policy_id + scope + evidence 富语义),
            GaC 是执行索引 (source_ref + executor 路由, 不复制内容)

重叠识别 (消除两套并行):
  X1-OMO-DIRECT-MUTATION-GATE ≈ CR-L2-DIRECT-IO → indexed 加 relates_to 指向 native 执行入口

用法:
  python3 bin/gac-ingest-legacy.py              # dry-run 打印 indexed 条目
  python3 bin/gac-ingest-legacy.py --write      # append indexed 到 governance-checks.yaml
  python3 bin/gac-ingest-legacy.py --json       # JSON 输出 (机器消费)

退出码: 0 = 成功, 1 = 已全部 ingest (无新条目)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[1]
REGISTRY = WORKSPACE / ".omo" / "_truth" / "registry" / "governance-checks.yaml"

# X1-X4 源 (x3 是 domains/principles 非规则, 跳过; GaC native CR-X3-DEBT-TIER 已覆盖)
LEGACY_SOURCES = [
    {
        "file": ".omo/_truth/x1-governance-policies.yaml",
        "sections": ["policies"],
        "id_key": "policy_id",
        "dimension": "X1",
        "layer": "meta",
    },
    {
        "file": ".omo/_truth/x2-freshness-rules.yaml",
        "sections": ["rules"],
        "id_key": "rule_id",
        "dimension": "X2",
        "layer": "meta",
    },
    {
        "file": ".omo/_truth/x4-consistency-rules.yaml",
        "sections": ["rules"],
        "id_key": "rule_id",
        "dimension": "X4",
        "layer": "meta",
    },
    # L0 MOF 模型约束 (代码级, MOF 派生; dimension 从每条读)
    # constraints (X1-C01 等协议约束) + trigger_constraints (CR-TRIGGER-01 等触发约束)
    {
        "file": "projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml",
        "sections": [
            "constraints", "protocol_registry", "trigger_constraints",
            "opc_cadence_constraints", "mof_schema_validate_constraints",
            "c2g_v3_constraints", "c2g_v4_constraints", "omni_bus_constraints",
            "debt_constraints", "governance_closure_constraints",
        ],
        "id_key": "id",
        "dimension": None,  # 从 item.dimension 动态读 (L0 跨 X1-X4)
        "layer": "L0",
    },
]

# 重叠识别: X1-X4 规则 → GaC native 执行入口 (同一件事, indexed 指向 native)
# 原 policy 保留为策略定义 (富语义), native 是机器执行入口
# gap3 闭环: 扩展重叠识别 (surfaces/drift/commit-loop 语义重叠)
OVERLAP_MAP = {
    "X1-OMO-DIRECT-MUTATION-GATE-20260617": "CR-L2-DIRECT-IO",
    "X1-OMO-GOVERNANCE-SURFACES-20260616": "CR-L2-SURFACES-INTEGRITY",
    "X2-FRESH-OMO-GOVERNANCE-SURFACES": "CR-L2-SURFACES-INTEGRITY",
    "X4-CONS-OMO-GOVERNANCE-SURFACES": "CR-L2-SURFACES-INTEGRITY",
    "X4-CONS-DRIFT-VS-GOVERNANCE": "CR-X2-GAC-DRIFT",
    "X2-FRESH-ADR-DRIFT": "CR-X2-GAC-DRIFT",
}


def load_yaml_last_doc(path: Path) -> dict:
    """读多文档 YAML 取最后非 None 文档 (strip frontmatter)."""
    docs = [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]
    return docs[-1] if docs else {}


def load_legacy_rules() -> list[dict]:
    """从 X1-X4 + L0 源提取规则 (多 section + 动态 dimension)."""
    rules: list[dict] = []
    for src in LEGACY_SOURCES:
        path = WORKSPACE / src["file"]
        if not path.exists():
            continue
        data = load_yaml_last_doc(path)
        for section in src["sections"]:
            items = data.get(section, []) or []
            for item in items:
                rid = item.get(src["id_key"])
                if not rid:
                    continue
                # dimension: src 默认 or 从 item 读 (L0 动态)
                dim = src["dimension"] or item.get("dimension", "X4")
                rules.append(
                    {
                        "id": rid,
                        "source_ref": f"{src['file']}::{section}",
                        "dimension": dim,
                        "layer": src["layer"],
                        "title": item.get("title", item.get("description", ""))[:80],
                        "enforcement": item.get("enforcement", item.get("type", "required")),
                    }
                )
    return rules


def check_drift() -> dict:
    """动态收敛核心: 检测源规则 vs GaC indexed 差异.

    missing = 源有 GaC 没 (需 ingest 纳管)
    ghost   = GaC 有 源没 (源已删除, 需清理 indexed)
    ok      = 源与 GaC indexed 同步 (动态闭环达成)
    """
    legacy = load_legacy_rules()
    legacy_ids = {r["id"] for r in legacy}
    gac_data = load_yaml_last_doc(REGISTRY)
    gac_rules = gac_data.get("gac", {}).get("rules", [])
    indexed_ids = {r["id"] for r in gac_rules if r.get("source_type") == "indexed"}
    missing = sorted(legacy_ids - indexed_ids)
    ghost = sorted(indexed_ids - legacy_ids)
    return {
        "legacy_count": len(legacy_ids),
        "indexed_count": len(indexed_ids),
        "missing": missing,
        "ghost": ghost,
        "ok": not missing and not ghost,
    }


def update_relates() -> int:
    """gap3 回填: 补已有 indexed 规则的 relates_to (OVERLAP_MAP 扩展后回填).

    对每条 OVERLAP_MAP 中的 indexed, 若 GaC 已 ingest 但缺 relates_to, 插入.
    保留 frontmatter + 注释 (文本精确插入, 非 YAML dump).
    """
    import re

    content = REGISTRY.read_text(encoding="utf-8")
    updated = 0
    for indexed_id, native_id in OVERLAP_MAP.items():
        id_pat = re.compile(rf"(    - id: {re.escape(indexed_id)}\n)")
        m = id_pat.search(content)
        if not m:
            continue
        block_start = m.end()
        rest = content[block_start:]
        block_end_rel = re.search(r"\n    - id:|\n  [a-z][a-z_]*:", rest)
        block_end = block_start + (block_end_rel.start() if block_end_rel else len(rest))
        block = content[m.start():block_end]
        if "relates_to" in block:
            continue  # 已有 relates_to 跳过
        sr_match = re.search(r"(      source_ref: [^\n]+\n)", block)
        if not sr_match:
            continue
        insert_pos = m.start() + sr_match.end()
        insert_line = f'      relates_to: "{native_id}"\n'
        content = content[:insert_pos] + insert_line + content[insert_pos:]
        updated += 1
    if updated:
        REGISTRY.write_text(content, encoding="utf-8")
    return updated


def build_indexed_entry(rule: dict) -> dict:
    """为一条 legacy 规则生成 GaC indexed 条目 (不复制富语义, 只放执行路由)."""
    entry = {
        "id": rule["id"],
        "source_type": "indexed",
        "source_ref": rule["source_ref"],
        "dimension": rule["dimension"],
        "layer": rule["layer"],
        "check_type": "legacy_index",
        "executor": ["omo_audit", "ci_gate"],
        "enforcement": rule["enforcement"],
        "lifecycle": "active",
        "version": "1.0.0",
        "created_at": "2026-06-27",
        "adr": "ADR-0106",
    }
    if rule["id"] in OVERLAP_MAP:
        entry["relates_to"] = OVERLAP_MAP[rule["id"]]
    return entry


def existing_rule_ids() -> set[str]:
    """读 governance-checks.yaml 现有 gac.rules id (避免重复 ingest)."""
    data = load_yaml_last_doc(REGISTRY)
    return {r.get("id") for r in data.get("gac", {}).get("rules", []) if r.get("id")}


def entry_to_yaml(entry: dict) -> str:
    """indexed 条目 → YAML 文本 (2 空格缩进, 与 gac.rules 段对齐)."""
    lines = [f"    - id: {entry['id']}"]
    for k, v in entry.items():
        if k == "id":
            continue
        if isinstance(v, list):
            lines.append(f"      {k}: {v}")
        else:
            lines.append(f'      {k}: "{v}"' if isinstance(v, str) and needs_quote(v) else f"      {k}: {v}")
    return "\n".join(lines)


def needs_quote(val: str) -> bool:
    """判断字符串是否需要引号 (含特殊字符)."""
    return any(c in val for c in ":#{}[]&,*?|-<>=!%@`") and not val.startswith("[")


def append_to_registry(new_entries: list[dict]) -> int:
    """把 indexed 条目 append 到 governance-checks.yaml::gac.rules 段末尾.

    定位 '  drift:' (gac.rules 段后的下一个 key), 在其前插入 indexed 条目.
    保留 frontmatter + 其他注释.
    """
    if not new_entries:
        return 0
    content = REGISTRY.read_text(encoding="utf-8")
    # 定位 gac 段内的 drift:/lifecycle: (rules 段后的下一个 key)
    marker = "\n  drift:"
    if marker not in content:
        marker = "\n  lifecycle:"
    if marker not in content:
        print("❌ 未找到 gac.rules 段尾标记 (drift/lifecycle), 不写", file=sys.stderr)
        return 0
    # 构建 indexed 段文本
    header = "\n    # ── indexed: 收敛 X1-X4 原有规则 (source_type=indexed, 原真是策略 SSOT) ──\n"
    block = header + "\n".join(entry_to_yaml(e) for e in new_entries) + "\n"
    # 在 marker 前插入
    new_content = content.replace(marker, block + marker, 1)
    REGISTRY.write_text(new_content, encoding="utf-8")
    return len(new_entries)


def main() -> int:
    parser = argparse.ArgumentParser(description="收敛 X1-X4 + L0 原有规则到 GaC indexed 层 (动态)")
    parser.add_argument("--write", action="store_true", help="append indexed 到 governance-checks.yaml")
    parser.add_argument("--check", action="store_true", help="drift 检测 (源 vs GaC indexed 差异, 动态收敛核心)")
    parser.add_argument("--update-relates", action="store_true", help="补已有 indexed 的 relates_to (gap3 回填)")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    # --update-relates: gap3 回填已有 indexed 的 relates_to (OVERLAP_MAP 扩展后)
    if args.update_relates:
        n = update_relates()
        print(f"✅ 回填 {n} 条 indexed 的 relates_to (OVERLAP_MAP)")
        if n:
            print("   验证: python3 bin/gac-validate.py --gate")
        return 0

    # --check: 动态 drift 检测 (源 vs GaC indexed)
    if args.check:
        drift = check_drift()
        if args.json:
            print(json.dumps(drift, ensure_ascii=False, indent=2))
            return 0 if drift["ok"] else 1
        print(f"═══ Legacy drift 检测 (动态收敛) ═══")
        print(f"  源规则: {drift['legacy_count']} | GaC indexed: {drift['indexed_count']}")
        if drift["missing"]:
            print(f"  ⚠️  源有 GaC 没 ({len(drift['missing'])}): {drift['missing'][:5]}")
        if drift["ghost"]:
            print(f"  ⚠️  GaC 有 源没 ({len(drift['ghost'])}): {drift['ghost'][:5]}")
        if drift["ok"]:
            print("  ✅ 无 drift (源与 GaC indexed 同步)")
        else:
            print("  → 修复: python3 bin/gac-ingest-legacy.py --write")
        return 0 if drift["ok"] else 1

    legacy = load_legacy_rules()
    native_ids = existing_rule_ids()
    entries = [build_indexed_entry(r) for r in legacy]
    new_entries = [e for e in entries if e["id"] not in native_ids]

    if args.json:
        print(
            json.dumps(
                {
                    "legacy_total": len(legacy),
                    "new_indexed": len(new_entries),
                    "already_in_gac": len(legacy) - len(new_entries),
                    "entries": new_entries,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print(f"═══ X1-X4 收敛到 GaC indexed ═══")
    print(f"  legacy 规则: {len(legacy)} 条 (x1:7 + x2:13 + x4:5)")
    print(f"  新 indexed:  {len(new_entries)} 条")
    print(f"  已在 GaC:    {len(legacy) - len(new_entries)} 条")
    print()
    for e in new_entries:
        rel = f"  → relates_to: {e['relates_to']}" if "relates_to" in e else ""
        print(f"  [{e['dimension']}/{e['layer']}] {e['id']}{rel}")
        print(f"    source: {e['source_ref']}")

    if args.write:
        if not new_entries:
            print("\n✅ 无新条目, 已全部 ingest")
            return 1
        n = append_to_registry(new_entries)
        print(f"\n✅ 已 append {n} 条 indexed 到 governance-checks.yaml::gac.rules")
        print("   验证: python3 bin/gac-validate.py --gate")
    else:
        print("\n(dry-run, 加 --write 执行 append)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
