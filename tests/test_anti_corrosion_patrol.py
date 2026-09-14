"""test_anti_corrosion_patrol — 防腐巡检单测.

验证核心逻辑:
  - weekly_net_lines(): 红线判定
  - rule_health_score(): 评分/等级
  - dead_code_and_dupes(): 调用 detector
  - budget_check(): 预算合规
  - patrol(): 汇总 + enforce exit code
  - --json 输出格式
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "gac" / "anti-corrosion-patrol.py"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_GOV_CHECKS = """\
gac:
  version: '1.0'
  rules:
  - id: CR-TEST-A
    dimension: X1
    layer: L0
    name: Test rule A
    description: A test rule
    check_type: audit_chain
    executor:
    - gac_local_gate
    lifecycle: active
    version: 1.0.0
  - id: CR-TEST-B
    dimension: X2
    layer: L1
    name: Test rule B
    description: Another test rule
    check_type: freshness
    executor:
    - omo_audit
    lifecycle: active
    version: 1.0.0
  - id: CR-TEST-C
    dimension: X3
    layer: L1
    name: Test rule C
    check_type: value_roi
    lifecycle: deprecated
    version: 1.0.0
"""

SAMPLE_GOV_CHECKS_ALL_ACTIVE = """\
gac:
  version: '1.0'
  rules:
  - id: CR-GOOD-1
    dimension: X1
    layer: L0
    name: Good rule 1
    description: A good rule
    executor:
    - gac_local_gate
    lifecycle: active
    version: 1.0.0
  - id: CR-GOOD-2
    dimension: X2
    layer: L0
    name: Good rule 2
    description: Another good rule
    executor:
    - ci_gate
    lifecycle: active
    version: 1.0.0
"""

SAMPLE_BUDGET_OK = """\
schema: anti-corrosion-budget/v1
budgets:
  governance_rules:
    max_count: 100
    current: 85
"""

SAMPLE_BUDGET_BREACH = """\
schema: anti-corrosion-budget/v1
budgets:
  governance_rules:
    max_count: 100
    current: 110
"""


def _load_module():
    spec = importlib.util.spec_from_file_location("anti_corrosion_patrol", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# weekly_net_lines
# ---------------------------------------------------------------------------

def test_weekly_net_lines_returns_dict():
    mod = _load_module()
    result = mod.weekly_net_lines()
    assert "net" in result
    assert "ok" in result
    assert "added" in result
    assert "deleted" in result
    assert isinstance(result["net"], int)


def test_weekly_net_lines_no_breach_on_empty_repo(tmp_path, monkeypatch):
    """Empty repo → net=0 → ok=True."""
    mod = _load_module()
    # monkeypatch subprocess to simulate empty diff
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **kw: type("R", (), {"stdout": "", "returncode": 0})())
    result = mod.weekly_net_lines()
    assert result["net"] == 0
    assert result["ok"] is True
    assert result["red_line_breached"] is False


def test_weekly_net_lines_detects_breach(tmp_path, monkeypatch):
    """When more added than deleted → red_line_breached=True."""
    mod = _load_module()
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **kw: type(
        "R", (), {"stdout": "3 files changed, 100 insertions(+), 10 deletions(-)", "returncode": 0})())
    result = mod.weekly_net_lines()
    assert result["net"] == 90
    assert result["red_line_breached"] is True
    assert result["ok"] is False


def test_weekly_net_lines_under_target(tmp_path, monkeypatch):
    """When more deleted than added → ok=True."""
    mod = _load_module()
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **kw: type(
        "R", (), {"stdout": "5 files changed, 10 insertions(+), 200 deletions(-)", "returncode": 0})())
    result = mod.weekly_net_lines()
    assert result["net"] == -190
    assert result["red_line_breached"] is False
    assert result["ok"] is True


# ---------------------------------------------------------------------------
# rule_health_score
# ---------------------------------------------------------------------------

def test_rule_health_score_with_mixed_lifecycle(tmp_path, monkeypatch):
    mod = _load_module()
    monkeypatch.setattr(mod, "GOV_CHECKS_YAML", tmp_path / "governance-checks.yaml")
    (tmp_path / "governance-checks.yaml").write_text(SAMPLE_GOV_CHECKS)
    result = mod.rule_health_score()
    assert result["total"] == 3
    assert result["active"] == 2
    assert result["deprecated"] == 1
    assert result["retirement_candidates"] == 1
    assert result["grade"] in ("green", "yellow", "red")


def test_rule_health_score_all_active_green(tmp_path, monkeypatch):
    mod = _load_module()
    monkeypatch.setattr(mod, "GOV_CHECKS_YAML", tmp_path / "governance-checks.yaml")
    (tmp_path / "governance-checks.yaml").write_text(SAMPLE_GOV_CHECKS_ALL_ACTIVE)
    result = mod.rule_health_score()
    assert result["total"] == 2
    assert result["active"] == 2
    assert result["retirement_candidates"] == 0
    assert result["ok"] is True


def test_rule_health_score_missing_file(tmp_path, monkeypatch):
    mod = _load_module()
    monkeypatch.setattr(mod, "GOV_CHECKS_YAML", tmp_path / "nonexistent.yaml")
    result = mod.rule_health_score()
    assert result["total"] == 0
    assert result["ok"] is True


# ---------------------------------------------------------------------------
# budget_check
# ---------------------------------------------------------------------------

def test_budget_check_ok(tmp_path, monkeypatch):
    mod = _load_module()
    monkeypatch.setattr(mod, "BUDGET_FILE", tmp_path / "budget.yaml")
    (tmp_path / "budget.yaml").write_text(SAMPLE_BUDGET_OK)
    result = mod.budget_check()
    assert result["ok"] is True
    assert result["over_budget"] is False


def test_budget_check_breach(tmp_path, monkeypatch):
    mod = _load_module()
    budget = tmp_path / "budget.yaml"
    budget.write_text(SAMPLE_BUDGET_BREACH)
    # Direct assignment to ensure the function sees the patched value
    original = mod.BUDGET_FILE
    mod.BUDGET_FILE = budget
    try:
        result = mod.budget_check()
        assert result["ok"] is False
        assert result["over_budget"] is True
        assert len(result["breaches"]) == 1
        assert result["breaches"][0]["over_by"] == 10
    finally:
        mod.BUDGET_FILE = original


# ---------------------------------------------------------------------------
# patrol summary
# ---------------------------------------------------------------------------

def test_patrol_returns_snapshot():
    mod = _load_module()
    snapshot = mod.patrol()
    assert "timestamp" in snapshot
    assert "ok" in snapshot
    assert "checks" in snapshot
    assert "summary" in snapshot
    assert snapshot["ok"] in (True, False)


# ---------------------------------------------------------------------------
# enforce exit code
# ---------------------------------------------------------------------------

def test_enforce_exit_0_when_ok(capsys, monkeypatch):
    mod = _load_module()
    monkeypatch.setattr("sys.argv", ["anti-corrosion-patrol.py", "--enforce"])
    # Patch patrol to return ok
    monkeypatch.setattr(mod, "patrol", lambda: {
        "timestamp": "2026-09-06T00:00:00",
        "ok": True,
        "checks": {"weekly_net_lines": {"ok": True}, "rule_health": {"ok": True},
                   "dead_code": {"ok": True}, "budget": {"ok": True}},
        "summary": {"net_lines": -5, "red_line_breached": False, "health_grade": "green",
                    "retirement_candidates": 0, "dead_code_findings": 0, "budget_breaches": 0},
    })
    result = mod.main()
    assert result == 0


def test_enforce_exit_1_when_fail(capsys, monkeypatch):
    mod = _load_module()
    monkeypatch.setattr("sys.argv", ["anti-corrosion-patrol.py", "--enforce"])
    monkeypatch.setattr(mod, "patrol", lambda: {
        "timestamp": "2026-09-06T00:00:00",
        "ok": False,
        "checks": {"weekly_net_lines": {"ok": False, "net": 50, "added": 100, "deleted": 50,
                                         "red_line_breached": True, "over_by": 50},
                   "rule_health": {"ok": True, "grade": "green", "avg_score": 2.7,
                                   "active": 85, "total": 85, "retirement_candidates": 0},
                   "dead_code": {"ok": True, "findings_count": 0, "findings": []},
                   "budget": {"ok": True, "over_budget": False, "breaches": []}},
        "summary": {"net_lines": 50, "red_line_breached": True, "health_grade": "green",
                    "retirement_candidates": 0, "dead_code_findings": 0, "budget_breaches": 0},
    })
    result = mod.main()
    assert result == 1


def test_json_output(capsys, monkeypatch):
    mod = _load_module()
    monkeypatch.setattr("sys.argv", ["anti-corrosion-patrol.py", "--json"])
    monkeypatch.setattr(mod, "patrol", lambda: {
        "timestamp": "2026-09-06T00:00:00",
        "ok": True,
        "checks": {},
        "summary": {},
    })
    mod.main()
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "timestamp" in data
    assert "ok" in data
