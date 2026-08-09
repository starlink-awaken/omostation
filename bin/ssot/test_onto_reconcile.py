import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from onto_reconcile import reconcile, missing_concepts, suggestions


def test_missing_concepts_detects_gap():
    candidates = [
        {"name": "adr", "count": 641, "source": "docs", "dimension": "X3", "surface": "L3"},
        {"name": "agent-workflow", "count": 88, "source": ".omo", "dimension": "X3", "surface": "L3"},
        {"name": "layer-contract", "count": 12, "source": "docs", "dimension": "X1", "surface": "L3"},
    ]
    existing = {"equivalences": [{"left": "layer-contract", "right": "layer-contract.yaml"}],
                "generalizations": []}
    missing = missing_concepts(candidates, existing)
    assert "adr" in missing
    assert "agent-workflow" in missing
    assert "layer-contract" not in missing


def test_suggestions_builds_generalizations():
    missing = ["adr", "agent-workflow"]
    sugg = suggestions(missing)
    assert any(s["concept"] == "adr" and "generalize" in s["action"] for s in sugg)
    assert len(sugg) == 2


def test_reconcile_returns_report():
    candidates = [{"name": "adr", "count": 10, "source": "a", "dimension": "X3", "surface": "L3"}]
    existing = {"equivalences": [], "generalizations": []}
    report = reconcile(candidates, existing)
    assert "adr" in report
    assert "缺口: 1 个" in report
