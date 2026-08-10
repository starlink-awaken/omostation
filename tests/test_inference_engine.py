import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))
from inference_engine import run_inference


def test_transitivity_detection():
    derived = {"constraints": [
        {"id": "X1-C01", "name": "protocol-registered", "dimension": "X1", "severity": "high"},
        {"id": "X4-C14", "name": "ssot-pointer-drift", "dimension": "X4", "severity": "critical"},
    ]}
    ontology = {"derivation_rules": {"DR-01": {"kind": "transitive", "on": "constraint"}}}
    findings = run_inference(derived, ontology)
    assert isinstance(findings, list)
    assert all("rule" in f for f in findings)


def test_critical_dimension_needs_guard():
    derived = {"constraints": [
        {"id": "X4-C14", "name": "ssot-pointer-drift", "dimension": "X4", "severity": "critical"},
    ]}
    ontology = {"derivation_rules": {"DR-01": {"kind": "transitive", "on": "constraint"}}}
    findings = run_inference(derived, ontology)
    assert any(f["rule"] == "DR-01" for f in findings)


def test_no_findings_healthy():
    derived = {"constraints": [
        {"id": "X1-C01", "name": "protocol-registered", "dimension": "X1", "severity": "high"},
        {"id": "X4-C01", "name": "domain-registered", "dimension": "X4", "severity": "high"},
        {"id": "X4-C14", "name": "ssot-pointer-drift", "dimension": "X4", "severity": "critical"},
    ]}
    ontology = {"derivation_rules": {"DR-01": {"kind": "transitive", "on": "constraint"}}}
    assert run_inference(derived, ontology) == []
