"""Tests for RuleReasoner — 规则推导引擎"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from ontoderive.reasoners.reasoner import RuleReasoner
from ontoderive.reasoners.reasoner_utils import default_rules


def test_default_rules_loaded():
    r = RuleReasoner()
    assert len(r.rules) >= 5
    assert default_rules()[0].name == "numeric_comparison"


def test_derive_empty_inputs():
    r = RuleReasoner()
    results = r.derive({}, {})
    assert isinstance(results, list)
    assert r.state == "done"


def test_derive_numeric_comparison():
    r = RuleReasoner()
    facts = {"D-F1": {"desc": "人数", "value": "500"}, "D-F2": {"desc": "人数", "value": "100"}}
    results = r.derive(facts, {})
    types = [res["type"] for res in results]
    assert "numeric_comparison" in types


def test_missing_reference_detected():
    r = RuleReasoner()
    infs = {"INF-L1": {"text": "test", "derives_from": ["D-F999"]}}
    results = r.derive({}, infs)
    types = [res["type"] for res in results]
    assert "missing_reference" in types


def test_shared_premise_detected():
    r = RuleReasoner()
    infs = {
        "INF-A": {"text": "test", "derives_from": ["D-F1", "D-F2", "D-F3"]},
        "INF-B": {"text": "test", "derives_from": ["D-F1", "D-F2", "D-F4"]},
    }
    results = r.derive({}, infs)
    types = [res["type"] for res in results]
    assert "shared_premise" in types


def test_coverage_analysis():
    r = RuleReasoner()
    facts = {"D-F1": {}, "D-F2": {}, "D-F3": {}}
    infs = {"INF-L1": {"text": "test", "derives_from": ["D-F1"]}}
    results = r.derive(facts, infs)
    types = [res["type"] for res in results]
    assert "coverage" in types


def test_threshold_alert():
    r = RuleReasoner()
    facts = {"D-F1": {"desc": "测试覆盖率", "value": "30"}}
    results = r.derive(facts, {})
    types = [res["type"] for res in results]
    assert "threshold_alert" in types


def test_chain_break_detected():
    r = RuleReasoner()
    infs = {"INF-L2": {"text": "test", "derives_from": ["INF-L1"]}}
    results = r.derive({}, infs)
    types = [res["type"] for res in results]
    assert "chain_break" in types


def test_influence_analysis():
    r = RuleReasoner()
    infs = {
        "INF-L1": {"text": "test", "derives_from": ["D-F1"]},
        "INF-L2": {"text": "test", "derives_from": ["D-F1"]},
        "INF-L3": {"text": "test", "derives_from": ["D-F1"]},
    }
    results = r.derive({}, infs)
    types = [res["type"] for res in results]
    assert "influence_analysis" in types


def test_redundancy_check():
    r = RuleReasoner()
    infs = {
        "INF-A": {"text": "test", "derives_from": ["D-F1", "D-F2", "D-F3"]},
        "INF-B": {"text": "test", "derives_from": ["D-F1", "D-F2", "D-F3"]},
    }
    results = r.derive({}, infs)
    types = [res["type"] for res in results]
    assert "redundancy_warning" in types


def test_evidence_gap():
    r = RuleReasoner()
    infs = {"INF-L1": {"text": "test", "derives_from": ["D-F1"]}}
    results = r.derive({}, infs)
    types = [res["type"] for res in results]
    assert "evidence_gap" in types


def test_consistency_analysis():
    r = RuleReasoner()
    infs = {
        "INF-A": {"text": "confidence: high\n结论: 测试\n", "derives_from": []},
        "INF-B": {"text": "confidence: high\n结论: 测试\n", "derives_from": []},
        "INF-C": {"text": "confidence: high\n结论: 测试\n", "derives_from": []},
    }
    results = r.derive({}, infs)
    types = [res["type"] for res in results]
    assert "consistency_warning" in types
