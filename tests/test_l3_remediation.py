"""Tests for bin/gac/l3-remediation.py

Covers:
  - _load_task handles missing/invalid files gracefully
  - _is_l3 detects both L3 risk_level and L3 allowed_operation_level
  - _is_actionable returns True for candidate/pending/blocked
  - _is_actionable returns False for closed/done
  - _remediation_plan produces plan with all required steps
  - main aggregation counts tasks correctly
  - --task filters to specific id
  - archived paths are skipped
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "gac" / "l3-remediation.py"
_MODULE = "_l3_remediation_test"


def _load():
    spec = importlib.util.spec_from_file_location(_MODULE, SCRIPT)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def l3():
    return _load()


def _write_task(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_load_task_valid_yaml(l3, tmp_path: Path):
    p = tmp_path / "t.yaml"
    p.write_text("id: TEST-1\nstatus: candidate\nrisk_level: L3\n")
    t = l3._load_task(p)
    assert t["id"] == "TEST-1"
    assert t["risk_level"] == "L3"


def test_load_task_invalid_yaml(l3, tmp_path: Path):
    p = tmp_path / "t.yaml"
    p.write_text(": :\nnot yaml")  # invalid yaml syntax
    assert l3._load_task(p) is None


def test_load_task_missing_file(l3):
    assert l3._load_task(Path("/nonexistent/path/nope.yaml")) is None


def test_is_l3_detects_risk_level(l3):
    assert l3._is_l3({"risk_level": "L3", "allowed_operation_level": "L2"}) is True


def test_is_l3_detects_operation_level(l3):
    assert l3._is_l3({"risk_level": "L2", "allowed_operation_level": "L3"}) is True


def test_is_l3_false_for_lower_levels(l3):
    assert l3._is_l3({"risk_level": "L2", "allowed_operation_level": "L2"}) is False


def test_is_l3_false_when_missing(l3):
    assert l3._is_l3({}) is False


def test_is_actionable_candidate(l3):
    actionable, reason = l3._is_actionable({"status": "candidate"})
    assert actionable is True
    assert "candidate" in reason


def test_is_actionable_pending(l3):
    actionable, reason = l3._is_actionable({"status": "pending"})
    assert actionable is True


def test_is_actionable_blocked(l3):
    actionable, reason = l3._is_actionable({"status": "blocked"})
    assert actionable is True


def test_is_actionable_closed(l3):
    actionable, reason = l3._is_actionable({"status": "closed"})
    assert actionable is False


def test_is_actionable_done(l3):
    actionable, reason = l3._is_actionable({"status": "done"})
    assert actionable is False


def test_is_actionable_completed_at(l3):
    actionable, reason = l3._is_actionable({
        "status": "candidate",
        "completed_at": "2026-08-01T00:00:00Z",
    })
    assert actionable is False
    assert "completed_at" in reason


def test_remediation_plan_includes_pre_flight(l3):
    plan = l3._remediation_plan({"id": "X"})
    assert any("Pre-flight" in step for step in plan)


def test_remediation_plan_includes_deps(l3):
    plan = l3._remediation_plan({
        "id": "X",
        "depends_on": ["A", "B"],
    })
    assert any("depends_on" in step and "A" in step for step in plan)


def test_remediation_plan_includes_entry_gate(l3):
    plan = l3._remediation_plan({
        "id": "X",
        "entry_gate": ["foo bar baz"],
    })
    assert any("foo bar baz" in step for step in plan)


def test_remediation_plan_includes_evidence(l3):
    plan = l3._remediation_plan({
        "id": "X",
        "evidence_required": ["calibration >= 0.6"],
    })
    assert any("calibration" in step for step in plan)


def test_remediation_plan_includes_human_action(l3):
    plan = l3._remediation_plan({
        "id": "X",
        "owner": "human",
        "human_approval_required": True,
    })
    assert any("HUMAN ACTION" in step for step in plan)


def test_remediation_plan_includes_workflow(l3):
    plan = l3._remediation_plan({
        "id": "X",
        "workflow": "bet-execution",
    })
    assert any("bet-execution" in step for step in plan)


def test_remediation_plan_includes_write_surfaces(l3):
    plan = l3._remediation_plan({
        "id": "X",
        "write_surfaces": ["docs/**", ".agents/**"],
    })
    assert any("docs/**" in step and ".agents/**" in step for step in plan)


def test_main_filters_by_task_id(l3, tmp_path: Path, monkeypatch, capsys):
    """--task should show only that id."""
    # Mock TASKS_DIR
    tasks = tmp_path / ".omo" / "tasks"
    _write_task(tasks / "a.yaml", "id: A\nrisk_level: L3\nstatus: candidate\n")
    _write_task(tasks / "b.yaml", "id: B\nrisk_level: L3\nstatus: candidate\n")
    monkeypatch.setattr(l3, "TASKS_DIR", tasks)
    monkeypatch.setattr(l3, "WORKSPACE", tmp_path)

    rc = l3.main(["--task", "A", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert data["total_l3"] == 1
    assert data["tasks"][0]["id"] == "A"


def test_main_skips_archived(l3, tmp_path: Path, monkeypatch, capsys):
    """Archived paths are skipped."""
    tasks = tmp_path / ".omo" / "tasks"
    _write_task(tasks / "active.yaml", "id: A\nrisk_level: L3\nstatus: candidate\n")
    _write_task(tasks / "archived" / "old.yaml", "id: B\nrisk_level: L3\nstatus: candidate\n")
    _write_task(tasks / "_archive" / "deep.yaml", "id: C\nrisk_level: L3\nstatus: candidate\n")
    monkeypatch.setattr(l3, "TASKS_DIR", tasks)
    monkeypatch.setattr(l3, "WORKSPACE", tmp_path)

    rc = l3.main(["--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert data["total_l3"] == 1
    assert data["tasks"][0]["id"] == "A"


def test_main_returns_0_when_no_actionable(l3, tmp_path: Path, monkeypatch, capsys):
    """If all L3 tasks are done/closed, return 0."""
    tasks = tmp_path / ".omo" / "tasks"
    _write_task(tasks / "done.yaml", "id: D\nrisk_level: L3\nstatus: done\n")
    monkeypatch.setattr(l3, "TASKS_DIR", tasks)
    monkeypatch.setattr(l3, "WORKSPACE", tmp_path)

    rc = l3.main(["--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["actionable"] == 0


def test_main_returns_1_when_actionable(l3, tmp_path: Path, monkeypatch):
    """If actionable L3 tasks exist, return 1 (signals operator action)."""
    tasks = tmp_path / ".omo" / "tasks"
    _write_task(tasks / "cand.yaml", "id: C\nrisk_level: L3\nstatus: candidate\n")
    monkeypatch.setattr(l3, "TASKS_DIR", tasks)
    monkeypatch.setattr(l3, "WORKSPACE", tmp_path)

    rc = l3.main(["--json"])
    assert rc == 1


def test_main_skips_non_l3(l3, tmp_path: Path, monkeypatch, capsys):
    """Non-L3 tasks are not counted even if status=candidate."""
    tasks = tmp_path / ".omo" / "tasks"
    _write_task(tasks / "low.yaml", "id: LOW\nrisk_level: L1\nstatus: candidate\n")
    monkeypatch.setattr(l3, "TASKS_DIR", tasks)
    monkeypatch.setattr(l3, "WORKSPACE", tmp_path)

    rc = l3.main(["--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["total_l3"] == 0


def test_main_skips_invalid_yaml(l3, tmp_path: Path, monkeypatch, capsys):
    """Invalid YAML files don't crash the tool."""
    tasks = tmp_path / ".omo" / "tasks"
    _write_task(tasks / "good.yaml", "id: G\nrisk_level: L3\nstatus: candidate\n")
    _write_task(tasks / "bad.yaml", ": invalid: :\n")
    monkeypatch.setattr(l3, "TASKS_DIR", tasks)
    monkeypatch.setattr(l3, "WORKSPACE", tmp_path)

    rc = l3.main(["--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert data["total_l3"] == 1
    assert data["tasks"][0]["id"] == "G"
