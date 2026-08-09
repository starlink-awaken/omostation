#!/usr/bin/env python3
"""onto_reconcile.py — ontology 补全（bootstrap 候选 → ontology 缺口对比）

依据 .omo/_knowledge/patterns/doc-l0-mof-mapping-governance.md Wave 2 收尾:
对比 OntoEKG bootstrap 提取的候选概念与 m2_ontology 现有概念，
产出缺口清单 + 并入建议（generalize 到 M3 父类型）。

用法:
    python3 bin/ssot/onto_reconcile.py
"""

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CANDIDATES = ROOT / "projects" / "ecos" / ".omo" / "_derived" / "onto-bootstrap-candidates.yaml"
ONTOLOGY = ROOT / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "ontology.yaml"


def _existing_concept_names(existing: dict) -> set[str]:
    """提取 ontology 现有概念名（equivalences 左右 + generalizations 子类）。"""
    names = set()
    for e in existing.get("equivalences", []):
        if isinstance(e, dict):
            names.add(str(e.get("left", "")).lower())
            names.add(str(e.get("right", "")).lower())
        elif isinstance(e, (list, tuple)) and len(e) >= 1:
            names.add(str(e[0]).lower())
    for g in existing.get("generalizations", []):
        if isinstance(g, dict):
            names.add(str(g.get("child", "")).lower())
        elif isinstance(g, (list, tuple)) and len(g) >= 1:
            names.add(str(g[0]).lower())
    return names


def missing_concepts(candidates: list[dict], existing: dict) -> list[str]:
    """候选概念中 ontology 未覆盖的（按 count 降序）。"""
    known = _existing_concept_names(existing)
    missing = []
    for c in sorted(candidates, key=lambda x: -x.get("count", 0)):
        name = c.get("name", "").lower()
        if name and name not in known:
            missing.append(c["name"])
    return missing


def suggestions(missing: list[str]) -> list[dict]:
    """缺口 → 并入建议（generalize 到 ConstraintL0 / Specification）。"""
    return [{"concept": name, "action": "generalize",
             "target": "ConstraintL0",
             "note": f"新增 M2 概念 {name}（generalize 到 ConstraintL0）"}
            for name in missing]


def reconcile(candidates: list[dict], existing: dict) -> str:
    """构建补全报告。"""
    missing = missing_concepts(candidates, existing)
    lines = ["# Ontology 补全报告", ""]
    lines.append(f"候选概念: {len(candidates)} 个")
    lines.append(f"ontology 现有: {len(_existing_concept_names(existing))} 个")
    lines.append(f"缺口: {len(missing)} 个")
    lines.append("")
    for s in suggestions(missing):
        lines.append(f"- {s['concept']} → {s['action']} to {s['target']} ({s['note']})")
    if not missing:
        lines.append("✅ ontology 已覆盖全部候选概念")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="JSON 输出缺口清单")
    args = ap.parse_args()
    if not CANDIDATES.exists():
        print("[WARN] 候选概念未生成，先跑: python3 bin/ssot/onto_ekg_bootstrap.py --emit",
              file=sys.stderr)
        return 1
    candidates = yaml.safe_load(CANDIDATES.read_text(encoding="utf-8")) or []
    existing = yaml.safe_load(ONTOLOGY.read_text(encoding="utf-8")).get("m2_ontology", {})
    if args.json:
        import json

        print(json.dumps(missing_concepts(candidates, existing), ensure_ascii=False, indent=1))
        return 0
    print(reconcile(candidates, existing))
    return 1 if missing_concepts(candidates, existing) else 0


if __name__ == "__main__":
    raise SystemExit(main())
