import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from owl_adapter import constraint_to_owl_class, build_owl_ontology


def test_constraint_to_owl_class():
    constraint = {"id": "X1-C04", "name": "cross-repo-contract-registered",
                  "dimension": "X1", "severity": "high",
                  "rule_expr": {"kind": "expr", "args": ["cross_repo.contract_registered == true"]}}
    owl = constraint_to_owl_class(constraint)
    assert "X1-C04" in owl
    assert "subClassOf" in owl


def test_build_owl_ontology_includes_header():
    constraints = [
        {"id": "X1-C04", "name": "cross-repo-contract", "dimension": "X1",
         "severity": "high", "rule_expr": {"kind": "expr", "args": ["a == true"]}},
    ]
    owl = build_owl_ontology(constraints)
    assert owl.startswith("<?xml") or "owl:Ontology" in owl
    assert "X1-C04" in owl


def test_build_owl_ontology_empty():
    owl = build_owl_ontology([])
    assert "owl:Ontology" in owl
