from __future__ import annotations

from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[2]
OMO = WORKSPACE / ".omo"


def test_phase6_entry_hardening_plan_is_indexed_as_current_pre_gate_artifact():
    plans_readme = (OMO / "plans" / "README.md").read_text(encoding="utf-8")

    assert "phase6-entry-hardening-packet-implementation-plan.md" in plans_readme


def test_phase6_entry_hardening_closeout_records_go_no_go_judgment():
    closeout = (OMO / "summaries" / "phase6-entry-hardening-closeout.md").read_text(encoding="utf-8")

    assert "GO/NO-GO judgment" in closeout
    assert "Security GO" in closeout
    assert "Reliability GO" in closeout
    assert "Mechanism GO" in closeout
