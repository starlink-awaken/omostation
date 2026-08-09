import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from model_graph_query import query_constraint, query_family, query_rules


def test_query_constraint_finds_consumers():
    index = {
        "X1-C04": ["跨仓契约", "CR-CROSS", "CR-INTERFACE"],
        "QG-C04": ["安全", "CR-SEC"],
    }
    result = query_constraint("X1-C04", index)
    assert result["constraint_id"] == "X1-C04"
    assert "跨仓契约" in result["consumers"]
    assert "CR-CROSS" in result["consumers"]


def test_query_family_lists_constraints():
    index = {
        "X1-C04": ["跨仓契约", "CR-CROSS"],
        "X1-C05": ["提交纪律", "CR-COMMIT"],
        "QG-C04": ["安全", "CR-SEC"],
    }
    result = query_family("安全", index)
    assert result["family"] == "安全"
    assert result["constraints"] == ["QG-C04"]


def test_query_rules_returns_rule_consumers():
    index = {
        "X1-C04": ["跨仓契约", "CR-CROSS", "CR-INTERFACE"],
        "QG-C04": ["安全", "CR-SEC"],
    }
    result = query_rules("CR-SEC", index)
    assert "QG-C04" in result["constraints"]
