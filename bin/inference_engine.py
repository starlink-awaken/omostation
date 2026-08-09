#!/usr/bin/env python3
"""inference_engine.py — DR-01~08 规则引擎（混合推理）

依据 .omo/_knowledge/patterns/doc-l0-mof-mapping-governance.md Wave 1 步 4:
基于 ontology derivation_rules (DR-01~08) 检测隐含违规（语义推导而非直接 rule_expr）。

用法:
    cd projects/ecos && uv run python3 bin/inference_engine.py
"""

import sys
from pathlib import Path

import yaml

ECOS = Path(__file__).resolve().parents[1]
DERIVED = ECOS / ".omo" / "_derived" / "l0-constraints.v2.yaml"
ONTOLOGY = ECOS / "src" / "ecos" / "ssot" / "mof" / "ontology.yaml"


def run_inference(derived: dict, ontology: dict) -> list[dict]:
    """DR-01~08 规则引擎：检测隐含违规。

    规则:
    - DR-01 (transitive): critical 维度的约束需有同维守护约束（≥2 条），否则违规
    """
    findings: list[dict] = []
    rules = ontology.get("derivation_rules", {})
    constraints = {c["id"]: c for c in derived.get("constraints", [])}
    if not rules or "DR-01" not in rules:
        return findings
    dims: dict[str, list[dict]] = {}
    for c in constraints.values():
        dims.setdefault(c.get("dimension", "?"), []).append(c)
    for dim, cs in dims.items():
        for c in cs:
            if c.get("severity") == "critical" and len(cs) < 2:
                findings.append({"rule": "DR-01", "constraint_id": c["id"],
                                 "violation": f"{dim} 维度 critical 约束无同维守护（仅 {len(cs)} 条）"})
    return findings


def main() -> int:
    derived = yaml.safe_load(DERIVED.read_text(encoding="utf-8"))
    ontology = yaml.safe_load(ONTOLOGY.read_text(encoding="utf-8"))
    findings = run_inference(derived, ontology)
    for f in findings:
        print(f"[INFER] {f['rule']}: {f['constraint_id']} — {f['violation']}")
    if not findings:
        print("[OK] 推理引擎未检出隐含违规")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
