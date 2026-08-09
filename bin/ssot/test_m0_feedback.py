import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from m0_feedback import m0_drift

EXPECTED_STAGES = ("stage1", "stage2", "stage3", "stage4", "stage5", "stage6", "stage7")


def test_no_drift_when_all_stages_present():
    snap = {"snapshot": {"stages": [{"id": s} for s in EXPECTED_STAGES]}}
    assert m0_drift(snap, derived_count=137) == []


def test_detect_missing_stage():
    snap = {"snapshot": {"stages": [{"id": "stage1"}, {"id": "stage2"}]}}
    drifts = m0_drift(snap, derived_count=137)
    assert any(d["type"] == "stage_missing" for d in drifts)
    assert len(drifts) == 5


def test_detect_constraint_count_mismatch():
    snap = {"snapshot": {"stages": [{"id": s} for s in EXPECTED_STAGES],
                         "constraint_count": 100}}
    drifts = m0_drift(snap, derived_count=137)
    assert any(d["type"] == "constraint_count_mismatch" for d in drifts)
