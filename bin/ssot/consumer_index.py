#!/usr/bin/env python3
"""consumer-index.py — 约束 → 抽象族/规则反向索引生成器

依据 .omo/_knowledge/patterns/doc-l0-mof-mapping-governance.md §2.3 的 16 抽象族映射,
为每条 L0 派生约束生成"谁引用它"的反向索引（抽象族 + 关联 gac 规则前缀）。

输入:  projects/ecos/.omo/_derived/l0-constraints.v2.yaml (派生约束)
输出:  projects/ecos/.omo/_derived/consumer-index.yaml (约束 id → [族, 规则前缀])

用法:
    python3 bin/ssot/consumer-index.py
"""

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DERIVED = ROOT / "projects" / "ecos" / ".omo" / "_derived" / "l0-constraints.v2.yaml"
OUT = ROOT / "projects" / "ecos" / ".omo" / "_derived" / "consumer-index.yaml"

# 16 抽象族 → (L0 维度, 关联 gac 规则前缀列表)
FAMILIES_MAP = {
    "分层边界": ("X1", ["CR-LAYER", "CR-BOUNDARY", "CR-HARDCODED"]),
    "跨仓契约": ("X1", ["CR-CROSS", "CR-INTERFACE", "CR-CONTRACT"]),
    "提交纪律": ("X1", ["CR-COMMIT", "CR-CHANGELANE", "CR-PR", "CR-REVIEW"]),
    "SSOT/漂移": ("X4", ["CR-SSOT", "CR-DRIFT", "CR-SYNC", "CR-POINTER", "CR-SUBMODULE"]),
    "元治理": ("X4", ["CR-META", "CR-RULE", "CR-EXECUTOR", "CR-GATE", "CR-BOOTSTRAP"]),
    "基线/证据": ("X4", ["CR-BASELINE", "CR-EVIDENCE", "CR-AUDIT", "CR-CLAIM"]),
    "流程/Agent": ("X3", ["CR-P74", "CR-P76", "CR-P77", "CR-P79", "CR-WORKFLOW", "CR-AGENT"]),
    "债务/交付": ("X3", ["CR-DEBT", "CR-REDLINE", "CR-CADENCE", "CR-DELIVERY"]),
    "健康度/可观测": ("X2", ["CR-HEALTH", "CR-SCORE", "CR-METRIC", "CR-UPTIME"]),
    "代码卫生": ("X2", ["CR-GOD", "CR-ORPHAN", "CR-DEAD", "CR-MODULE"]),
    "安全": ("QG", ["CR-SEC", "CR-PERMISSION", "CR-SECRET", "CR-CREDENTIAL"]),
    "文档/ADR": ("X3", ["CR-DOC", "CR-FRONTMATTER", "CR-FRESHNESS", "CR-ADR"]),
    "MCP工具": ("X1", ["CR-MCPTOOL", "CR-MCP"]),
    "索引/注册表": ("X2", ["CR-INDEX", "CR-REGISTRY", "CR-INVENTORY"]),
    "环境/端口": ("X1", ["CR-PORT", "CR-ENV-VAR"]),
    "BOS 域": ("X5", ["CR-BOS", "CR-URI"]),
}


def consumer_index(derived: dict, families_map: dict | None = None) -> dict[str, list[str]]:
    """约束 id → [抽象族, 关联 gac 规则前缀] 反向索引。

    支持两种 families_map 结构:
    - 显式映射: {fam: {"constraints": [...], "rules": [...]}} — 直接声明约束归属
    - 匹配模式: {fam: (dim, [prefixes])} — 按 dimension/name 自动匹配
    """
    fm = families_map or FAMILIES_MAP
    idx: dict[str, list[str]] = {}
    explicit = any(isinstance(s, dict) and "constraints" in s for s in fm.values())
    if explicit:
        for fam, spec in fm.items():
            rules = spec.get("rules", [])
            for cid in spec.get("constraints", []):
                idx.setdefault(cid, [])
                if fam not in idx[cid]:
                    idx[cid].append(fam)
                for p in rules:
                    if p not in idx[cid]:
                        idx[cid].append(p)
        return idx
    for c in derived.get("constraints", []):
        cid = c.get("id")
        if not cid:
            continue
        dim = c.get("dimension", "?")
        name = c.get("name", "")
        consumers: list[str] = []
        for fam, (fam_dim, prefixes) in fm.items():
            if dim == fam_dim:
                consumers.append(fam)
            for p in prefixes:
                if p.lower() in name.lower():
                    consumers.append(p)
        if consumers:
            seen = set()
            dedup = [c for c in consumers if not (c in seen or seen.add(c))]
            idx[cid] = dedup
    return idx


def main() -> int:
    if not DERIVED.exists():
        print(f"[FAIL] 派生约束缺失: {DERIVED}", file=sys.stderr)
        return 1
    derived = yaml.safe_load(DERIVED.read_text(encoding="utf-8"))
    idx = consumer_index(derived)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(yaml.safe_dump(idx, allow_unicode=True, sort_keys=True))
    print(f"[OK] consumer index: {len(idx)} constraints indexed → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
