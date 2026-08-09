import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from semantic_diff import semantic_diff


def test_detect_added_constraint():
    old = {"constraints": [{"id": "X1-C04", "dimension": "X1"}]}
    new = {"constraints": [
        {"id": "X1-C04", "dimension": "X1"},
        {"id": "X2-C06", "dimension": "X2"},
    ]}
    diffs = semantic_diff(old, new)
    assert any(d["type"] == "added" and d["constraint_id"] == "X2-C06" for d in diffs)


def test_detect_removed_constraint():
    old = {"constraints": [
        {"id": "X1-C04", "dimension": "X1"},
        {"id": "QG-C04", "dimension": "QG"},
    ]}
    new = {"constraints": [{"id": "X1-C04", "dimension": "X1"}]}
    diffs = semantic_diff(old, new)
    assert any(d["type"] == "removed" and d["constraint_id"] == "QG-C04" for d in diffs)


def test_detect_severity_change():
    old = {"constraints": [{"id": "X1-C04", "dimension": "X1", "severity": "medium"}]}
    new = {"constraints": [{"id": "X1-C04", "dimension": "X1", "severity": "high"}]}
    diffs = semantic_diff(old, new)
    assert any(d["type"] == "changed" and d["constraint_id"] == "X1-C04" for d in diffs)


def test_no_change():
    same = {"constraints": [{"id": "X1-C04", "dimension": "X1"}]}
    assert semantic_diff(same, dict(same)) == []
