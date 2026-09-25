#!/usr/bin/env python3
"""规则接线覆盖率清单 (rule wiring inventory) — 让"声明了规则但没人执行"可见.

背景 (2026-09-21 实证, 今天主题的最大规模实例):
  追查 17 项 debt item 的 `gate_level` 用了契约外的 `P0/P1/P2` (契约与 omo
  `GATE_ORDER` 都是 {gate,watchlist,none}, 非法值 → rank=99 → **severity 最高
  的债务在 review queue 里反而最后被看到**) 时发现:

    - 契约文档 `.omo/standards/debt-gate-level-enum.md` 声明了值域 ✓
    - `projects/omo/src/omo/omo_debt_review_queue.py:13` 实现了 `GATE_ORDER` ✓
    - L0 注册表声明了 `CR-DEBT-GATE-ENUM-01` ✓
    - 但**没有任何执行器引用它** —— 文档 §4 自己写着"实现位置: 待补" ✗

  ⇒ 违规数据能存在 3 个月 (06-18 定契约 → 09-21 才发现), 根因是**唯一该执行
  它的守卫从未接线**。

本工具做**清单**而非门禁 —— 并且必须说清它的**已知假阳边界**:

  三个规则注册表使用**互不相同的 id 词汇**:
    - `.omo/_truth/registry/governance-checks.yaml`  → `CR-X4-HEALTH-SSOT` 等 86 条
    - `projects/ecos/.../L0-constraints.yaml`        → `CR-SFOP-05` 等 77 条 (子模块)
    - `bin/gac/check-l0-constraints.py` 实际实现      → `X2-C05` / `CR-OMO-SURFACE-01` 等
  实测: `check-l0-constraints.py` 对 governance-checks 的 86 个 id **零引用** ——
  它用自己的命名。所以"某 id 在可执行语料里查不到"**有两种可能**:
    (a) 真未接线 (如 CR-DEBT-GATE-ENUM-01)
    (b) 已实现但**换了名字** (别名)
  在没有 id 映射表之前, 本工具**无法区分** (a) 与 (b), 因此:
    - 只输出**候选清单**, 不判 fail
    - 退出码恒 0 (除非 --strict 用于巡检提醒)

  要把它变成真门禁, 前置工作是**建立 id 别名映射** (逐条人工确认), 那是
  owner 的语义决策, 不是本工具能自动做的。

用法:
    python3 bin/gac/check-rule-wiring-coverage.py [--json] [--strict]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
GOV_CHECKS = _ROOT / ".omo" / "_truth" / "registry" / "governance-checks.yaml"
L0_SUBMODULE = _ROOT / "projects" / "ecos" / "src" / "ecos" / "ssot" / "registry" / "L0-constraints.yaml"
ALIAS_MAP = _ROOT / "bin" / "gac" / "registry-alias-map.yaml"

# 可执行语料: 真正的执行体所在处 (不含注册表自身, 否则自引用会全绿)
EXEC_CORPUS_GLOBS = [
    "bin/**/*.py",
    "bin/**/*.sh",
    ".githooks/*",
    ".github/workflows/*.yml",
]
EXEC_MANIFEST = _ROOT / ".omo" / "_truth" / "registry" / "hook-manifest.yaml"

_ID_RE = re.compile(r"^CR-[A-Z0-9-]+$|^X[1-4]-C\d{2}$|^CS-\d+$")

# governance-checks has 4 entries using lowercase hyphen form (x1-audit-chain etc.)
# while 86 use CR-* form. The regex above matches only CR-*, so we add
# lowercase xN-name as a valid id form for both _rule_ids extraction AND
# _implemented_ids corpus scan.
_ID_RE_LOWER = re.compile(r"^[xX][1-4]-[a-z][a-z0-9-]+$")


def _load_alias_map() -> dict[str, set[str]]:
    """Load alias map → {canonical_id: {aliases including self}}.

    Used by inventory() to detect "implemented but renamed" IDs.
    """
    if not ALIAS_MAP.is_file():
        return {}
    try:
        import yaml
        with ALIAS_MAP.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:
        return {}
    out: dict[str, set[str]] = {}
    for entry in data.get("aliases", []) or []:
        canon = str(entry.get("canonical", "")).strip()
        if not canon:
            continue
        aliases = {canon}
        for a in entry.get("aliases", []) or []:
            aliases.add(str(a).strip())
        out[canon] = aliases
    return out


def _resolve_via_alias(rule_id: str, alias_map: dict[str, set[str]]) -> str | None:
    """Return canonical id if rule_id matches any alias (case-insensitive)."""
    rule_lower = rule_id.lower()
    for canon, aliases in alias_map.items():
        if rule_id in aliases or canon == rule_id:
            return canon
        lowered = {a.lower() for a in aliases}
        if rule_lower in lowered:
            return canon
    return None


def _exec_corpus() -> str:
    parts = []
    for pat in EXEC_CORPUS_GLOBS:
        for f in _ROOT.glob(pat):
            if not f.is_file():
                continue
            if "_archive" in f.parts or "_registry" in f.parts:
                continue
            try:
                parts.append(f.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                continue
    if EXEC_MANIFEST.is_file():
        parts.append(EXEC_MANIFEST.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


def _rule_ids(path: Path) -> list[str]:
    if not path.is_file():
        return []
    try:
        import yaml
        docs = [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8", errors="ignore"))
                if isinstance(d, dict)]
    except Exception:
        return []
    ids: list[str] = []

    def walk(o):
        if isinstance(o, dict):
            v = o.get("id")
            if isinstance(v, str) and (_ID_RE.match(v) or _ID_RE_LOWER.match(v)):
                ids.append(v)
            for x in o.values():
                walk(x)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    for d in docs:
        walk(d)
    return ids


def _implemented_ids(corpus: str) -> list[str]:
    """执行体里出现的规则 id (含别名形态 X2-C05 等)."""
    found = sorted({m.group(0) for m in re.finditer(
        r"\b(?:CR-[A-Z0-9][A-Z0-9-]{2,}|X[1-4]-C\d{2}|CS-\d{2})\b", corpus)})
    return found


def inventory() -> dict:
    corpus = _exec_corpus()
    gov = _rule_ids(GOV_CHECKS)
    l0 = _rule_ids(L0_SUBMODULE)
    l0_available = bool(l0)
    alias_map = _load_alias_map()

    # An ID is "wired" if:
    #   (a) its string form appears literally in the corpus, OR
    #   (b) any alias of it appears in the corpus (alias map cross-walk)
    def is_wired(rule_id: str) -> bool:
        if rule_id in corpus:
            return True
        canon = _resolve_via_alias(rule_id, alias_map)
        if not canon:
            return False
        aliases = alias_map[canon]
        return any(a in corpus for a in aliases)

    def unreferenced(ids):
        return [i for i in ids if not is_wired(i)]

    gov_un = unreferenced(gov)
    l0_un = unreferenced(l0)
    impl = _implemented_ids(corpus)

    # also: IDs implemented but not declared (alias-resolved count)
    declared_all = set(gov) | set(l0)
    impl_resolved = []
    for iid in impl:
        if iid in declared_all:
            continue
        canon = _resolve_via_alias(iid, alias_map)
        if canon and canon in declared_all:
            impl_resolved.append({"id": iid, "canonical": canon})

    return {
        "sources": {
            "governance-checks": {
                "declared": len(gov),
                "unreferenced": len(gov_un),
                "alias_map_loaded": bool(alias_map),
                "alias_map_size": len(alias_map),
            },
            "L0-constraints(submodule)": {
                "declared": len(l0), "unreferenced": len(l0_un),
                "available": l0_available,
                "note": None if l0_available else
                "子模块未初始化 → 该源跳过 (CI 里有); 本地不得据此判全貌",
            },
        },
        "executed_ids_in_corpus": len(impl),
        "candidates_unwired": {
            "governance-checks": gov_un,
            "L0-constraints": l0_un,
        },
        "implemented_via_alias": impl_resolved,
        "caveat": (
            "无法区分『真未接线』与『已实现但换了名字』—— 三个注册表 id 词汇互异, "
            "且 check-l0-constraints.py 对 governance-checks 的 id 零引用 (用自己的 "
            "X2-C05 等命名)。建立 id 别名映射是前置的人工工作, 在此之前本清单"
            "**不作为门禁**。"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--top", type=int, default=20, help="最多列出多少候选 (默认 20)")
    ap.add_argument("--strict", action="store_true",
                    help="存在未接线候选 → exit 1 (仅巡检提醒; 因含假阳, 勿接入门禁)")
    args = ap.parse_args(argv)

    inv = inventory()
    if args.json:
        print(json.dumps(inv, ensure_ascii=False, indent=1))
        total_un = (inv["sources"]["governance-checks"]["unreferenced"]
                    + inv["sources"]["L0-constraints(submodule)"]["unreferenced"])
        return 1 if (args.strict and total_un) else 0

    s = inv["sources"]
    print("规则接线覆盖率清单 (报告型, **非门禁**)")
    print(f"  执行体语料里出现的规则 id: {inv['executed_ids_in_corpus']} 个")
    print(f"  governance-checks:  声明 {s['governance-checks']['declared']} / "
          f"未引用候选 {s['governance-checks']['unreferenced']}")
    l0s = s["L0-constraints(submodule)"]
    if l0s["available"]:
        print(f"  L0-constraints(子仓): 声明 {l0s['declared']} / 未引用候选 {l0s['unreferenced']}")
    else:
        print(f"  L0-constraints(子仓): {l0s['note']}")
    cand = inv["candidates_unwired"]["governance-checks"]
    if cand:
        print(f"\n  候选 (governance-checks, 前 {args.top}):")
        for i in cand[:args.top]:
            print(f"    ? {i}")
        if len(cand) > args.top:
            print(f"    … 另 {len(cand) - args.top} 个")
    print(f"\n  ⚠️ 已知假阳边界: {inv['caveat']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
