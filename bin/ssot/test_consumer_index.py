# bin/ssot/test_consumer_index.py
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from consumer_index import consumer_index


def test_basic_index():
    derived = {"constraints": [
        {"id": "X1-C04", "dimension": "X1", "name": "cross-repo-contract-registered"},
        {"id": "QG-C04", "dimension": "QG", "name": "security-baseline"},
    ]}
    families = {"分层边界": {"constraints": ["X1-C04"], "rules": ["CR-LAYER-01"]},
                "安全": {"constraints": ["QG-C04"], "rules": ["CR-SEC-01"]}}
    idx = consumer_index(derived, families)
    assert "X1-C04" in idx
    assert idx["X1-C04"] == ["分层边界", "CR-LAYER-01"]


def test_dimension_matching():
    """维度匹配：dimension 相同的约束归入对应族。"""
    derived = {"constraints": [
        {"id": "X2-C06", "dimension": "X2", "name": "health-score-gate"},
    ]}
    idx = consumer_index(derived)
    assert "X2-C06" in idx
    assert "健康度/可观测" in idx["X2-C06"]


def test_empty_derived():
    assert consumer_index({"constraints": []}) == {}
