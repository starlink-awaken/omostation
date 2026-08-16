"""
测试贝叶斯层
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from ontoderive.theories.bayesian import BayesianLayer


def test_scan_facts(z_park_path):
    bl = BayesianLayer(z_park_path)
    facts = bl.scan_facts()
    assert len(facts) >= 2
    assert "D-F1" in facts
    assert facts["D-F1"]["confidence"] == 0.95


def test_scan_inferences(z_park_path):
    bl = BayesianLayer(z_park_path)
    inferences = bl.scan_inferences()
    assert len(inferences) >= 1


def test_propagate_all(z_park_path):
    bl = BayesianLayer(z_park_path)
    facts, inferences = bl.propagate_all()
    assert len(facts) >= 2
    assert len(inferences) >= 1
    for inf in inferences.values():
        assert 0 < inf["propagated_confidence"] < 1


def test_confidence_in_range(z_park_path):
    bl = BayesianLayer(z_park_path)
    facts, inferences = bl.propagate_all()
    for fid, info in facts.items():
        assert 0 < info["confidence"] <= 1, f"{fid} 置信度越界"
    for name, info in inferences.items():
        assert 0 < info["propagated_confidence"] <= 1, f"{name} 置信度越界"


def test_empty_project(tmp_path):
    (tmp_path / "facts").mkdir()
    (tmp_path / "inferences").mkdir()
    bl = BayesianLayer(tmp_path)
    facts, inferences = bl.propagate_all()
    assert facts == {}
    assert inferences == {}
