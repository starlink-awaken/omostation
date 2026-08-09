#!/usr/bin/env python3
"""owl_adapter.py — L0 约束 → OWL 适配层（Wave 3）

依据 .omo/_knowledge/patterns/doc-l0-mof-mapping-governance.md Wave 3:
把 L0 约束 rule_expr 序列化为 OWL（OWL-DL 子集），为 HermiT/Pellet
标准化推理铺路。

用法:
    python3 bin/ssot/owl_adapter.py --emit
"""

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DERIVED = ROOT / "projects" / "ecos" / ".omo" / "_derived" / "l0-constraints.v2.yaml"
OWL_OUT = ROOT / "projects" / "ecos" / ".omo" / "_derived" / "l0-constraints.owl"

OWL_HEADER = """<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:owl="http://www.w3.org/2002/07/owl#"
         xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#">
  <owl:Ontology rdf:about="https://omostation.internal/mof/l0"/>
"""


def constraint_to_owl_class(constraint: dict) -> str:
    """单条约束 → OWL Class 声明（Class + SubClassOf）。"""
    cid = constraint.get("id", "C-UNKNOWN")
    name = constraint.get("name", cid).replace("-", "_").replace(".", "_")
    return (
        f'  <owl:Class rdf:about="#{cid}">\n'
        f'    <rdfs:label>{name}</rdfs:label>\n'
        f'    <rdfs:comment>{constraint.get("description", "")}</rdfs:comment>\n'
        f'  </owl:Class>\n'
        f'  <owl:Class rdf:about="#ConstraintL0"/>\n'
        f'  <rdfs:subClassOf rdf:resource="#ConstraintL0"/>'
        if False else
        f'  <owl:Class rdf:about="#{cid}">\n'
        f'    <rdfs:label>{name}</rdfs:label>\n'
        f'    <rdfs:comment>{constraint.get("description", "")}</rdfs:comment>\n'
        f'    <rdfs:subClassOf rdf:resource="#ConstraintL0"/>\n'
        f'  </owl:Class>'
    )


def build_owl_ontology(constraints: list[dict]) -> str:
    """约束列表 → 完整 OWL 文档。"""
    parts = [OWL_HEADER]
    for c in constraints:
        parts.append(constraint_to_owl_class(c))
    parts.append("</rdf:RDF>")
    return "\n".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--emit", action="store_true", help="写出 OWL 文件")
    args = ap.parse_args()
    if not DERIVED.exists():
        print(f"[WARN] 派生面未生成，先跑: cd projects/ecos && uv run python3 bin/gen-l0-constraints.py",
              file=sys.stderr)
        return 1
    derived = yaml.safe_load(DERIVED.read_text(encoding="utf-8"))
    constraints = derived.get("constraints", [])
    owl = build_owl_ontology(constraints)
    if args.emit:
        OWL_OUT.parent.mkdir(parents=True, exist_ok=True)
        OWL_OUT.write_text(owl, encoding="utf-8")
        print(f"[OK] OWL 已写出 → {OWL_OUT}（{len(constraints)} 条约束）")
        return 0
    print(owl)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
