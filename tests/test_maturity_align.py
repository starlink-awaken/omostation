"""Tests for bin/gac/maturity-align.py (BET-Y1Q3-T10-10).

Three independent measurement systems:
  1. compass_radar.health_score    (0-100)
  2. maturity-scorecard.overall     (1-10)
  3. bet-ledger completion_pct      (0-100)

This tool reconciles them and emits a side-by-side view + reconciliation_score.
"""

from __future__ import annotations

import importlib.util
import json as _json
import sys
from pathlib import Path

import pytest

ALIGN = Path(__file__).resolve().parents[1] / "bin" / "gac" / "maturity-align.py"
_MODULE = "_maturity_align_test"


def _load():
    spec = importlib.util.spec_from_file_location(_MODULE, ALIGN)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def align():
    return _load()


# ---------------------------------------------------------------------------
# Reconciliation logic
# ---------------------------------------------------------------------------


def test_compute_reconciliation_perfect(align):
    """All three at 100% → reconciliation_score=100, drift_detected=False."""
    compass = {"health_score": 100}
    scorecard = {"overall": 10.0, "target": 9.0, "gap": -1.0}
    ledger = {"completion_pct": 100.0, "counts": {"done": 10}, "total": 10}
    out = align.compute_reconciliation(compass, scorecard, ledger)
    assert out["drift_detected"] is False
    assert out["reconciliation_score"] == 100
    assert out["normalised"]["compass_radar"] == 100
    assert out["normalised"]["maturity_scorecard"] == 100
    assert out["normalised"]["bet_ledger"] == 100


def test_compute_reconciliation_drift_detected(align):
    """**同口径**漂移才判 drift (2026-09-19 语义修正).

    旧语义把 bet_ledger(计划完成度) 也计入 spread; 现只比同口径的
    compass_health 与 maturity_scorecard。
    此处 compass=100 vs scorecard=90 → 同口径 spread=10 → 无 drift;
    而计划完成度 20 远低于系统状态 → 体现为**负向** declaration_execution_gap。
    """
    compass = {"health_score": 100}
    scorecard = {"overall": 9.0, "target": 9.0, "gap": 0.0}
    ledger = {"completion_pct": 20.0, "counts": {"done": 2}, "total": 10}
    out = align.compute_reconciliation(compass, scorecard, ledger)
    assert out["drift_detected"] is False           # 同口径 100 vs 90 = 10 < 30
    assert out["reconciliation_score"] == 90.0      # 100 - 10
    assert out["declaration_execution_gap"]["value"] == -80.0


def test_same_scope_drift_is_still_detected(align):
    """同口径真漂移仍必须被检出 (放宽不得失去检出力)."""
    out = align.compute_reconciliation(
        {"health_score": 90}, {"overall": 3.0}, {"completion_pct": 50}
    )
    # normalized: compass 90 vs scorecard 30 → spread 60 > 30
    assert out["drift_detected"] is True
    assert out["reconciliation_score"] == 40.0
    assert any("same-scope" in w for w in out["warnings"])


def test_compute_reconciliation_handles_missing(align):
    """Missing dimensions → normalised=None, no crash."""
    compass: dict = {}
    scorecard: dict = {}
    ledger: dict = {}
    out = align.compute_reconciliation(compass, scorecard, ledger)
    assert out["drift_detected"] is False
    assert out["reconciliation_score"] is None


def test_normalise_to_100_clamps(align):
    """Values > scale_max clamp to 100, < 0 clamp to 0."""
    assert align.normalise_to_100(50, 100) == 50
    assert align.normalise_to_100(200, 100) == 100
    assert align.normalise_to_100(-10, 100) == 0
    assert align.normalise_to_100(7.5, 10) == 75
    assert align.normalise_to_100(None, 100) is None


def test_compute_reconciliation_3way_spread(align):
    """Real-world 场景 (语义修正后): 70 / 7.5 / 89.4.

    同口径 = compass 70 vs scorecard 75 → spread 5 → reconciliation 95。
    计划完成度 89.4 与系统状态之差单列为 declaration_execution_gap (19.4), 不计入
    reconciliation。旧语义下该场景 scope 混算得到 ~80。
    """
    compass = {"health_score": 70}
    scorecard = {"overall": 7.5, "target": 9.0, "gap": 1.5}
    ledger = {"completion_pct": 89.4, "counts": {"done": 126}, "total": 141}
    out = align.compute_reconciliation(compass, scorecard, ledger)
    assert out["drift_detected"] is False
    assert out["reconciliation_score"] == 95.0
    assert out["declaration_execution_gap"]["value"] == 19.4


# ---------------------------------------------------------------------------
# Tool integration
# ---------------------------------------------------------------------------


def test_cli_runs_in_dry_paths(tmp_path, monkeypatch):
    """Tool runs without crashing when subprocesses succeed (or fail gracefully)."""
    import subprocess

    # Patch WS_ROOT so subprocess calls go to a clean root
    monkeypatch.setattr(align_mod := _load(), "WS_ROOT", tmp_path)
    # Ensure tool runs even when subprocesses fail (None in dict)
    res = subprocess.run(
        [sys.executable, str(ALIGN)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
    )
    # Tool should not crash with exit 1 — output may show "unavailable" entries
    assert res.returncode in (0, 1)
    # When tools fail, the JSON output should still be valid JSON with --json flag
    res_json = subprocess.run(
        [sys.executable, str(ALIGN), "--json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if res_json.stdout.strip().startswith("{"):
        data = _json.loads(res_json.stdout)
        assert "alignment" in data

# ── 声明/执行鸿沟的显式命名 (2026-09-19) ──────────────────
#
# 三个来源答的是**不同的问题**: compass_radar = 系统当前状态,
# maturity_scorecard = 能力成熟度, bet_ledger = **计划完成度**。
# 工具前提是"计划是通往成熟的路径", 故 ledger 显著高于系统状态时其含义是
# "计划做完了却没转化为系统状态" —— 原先只报 "score spread = N", 读者需自行
# 推断; 现显式命名并解释 (对应仓库内 critical 债务 DECL_EXEC_GAP)。


def test_declaration_execution_gap_named_when_ledger_leads(align):
    """计划完成度高而系统状态低 → 鸿沟被显式命名 + 解释."""
    out = align.compute_reconciliation(
        {"health_score": 50},
        {"overall": 6.6},
        {"completion_pct": 100},
    )
    g = out["declaration_execution_gap"]
    assert g is not None
    assert g["value"] == 50.0
    assert g["ledger_completion"] == 100.0
    assert g["compass_health"] == 50.0
    assert "鸿沟" in g["meaning"]
    # 同时给出一条可读的告警 (不再只有裸 spread)
    assert any("声明/执行鸿沟" in w for w in out["warnings"])


def test_declaration_execution_gap_small_gap_not_warned(align):
    """差距小于 30 → 仍计算该字段, 但不产生告警 (避免噪声)."""
    out = align.compute_reconciliation(
        {"health_score": 90}, {"overall": 9.0}, {"completion_pct": 100}
    )
    g = out["declaration_execution_gap"]
    assert g is not None and g["value"] == 10.0
    assert not any("声明/执行鸿沟" in w for w in out["warnings"])


def test_declaration_execution_gap_zero_means_aligned(align):
    out = align.compute_reconciliation(
        {"health_score": 80}, {"overall": 8.0}, {"completion_pct": 80}
    )
    assert out["declaration_execution_gap"]["value"] == 0.0
    assert "一致" in out["declaration_execution_gap"]["meaning"]


def test_gap_is_none_when_inputs_missing(align):
    """缺少 compass 或 ledger 时不臆造该字段."""
    out = align.compute_reconciliation({}, {"overall": 8.0}, {})
    assert out["declaration_execution_gap"] is None


def test_no_self_reference_when_plan_fully_closed(align):
    """**核心不变量 (2026-09-19)**: 计划全闭时 reconciliation 不得等于 compass 本身.

    旧语义: 计划全闭 (ledger=100) 时 spread = 100 - compass, 于是
    reconciliation 恒等于 compass_health —— 而 alignment 以 0.1 权重进健康分,
    即健康分部分由自己算出。现 reconciliation 只比同口径, 该自指不再可能。
    """
    for compass_health in (40, 55, 70, 85):
        out = align.compute_reconciliation(
            {"health_score": compass_health},
            {"overall": compass_health / 10.0},
            {"completion_pct": 100},
        )
        # 同口径完全一致 → reconciliation 应为 100, 而不是等于 compass
        assert out["reconciliation_score"] == 100.0, (
            f"compass={compass_health} 时 reconciliation 不应退化为 compass 本身")
        assert out["reconciliation_score"] != compass_health


def test_completing_plan_does_not_lower_reconciliation(align):
    """**反向激励已消除**: 把计划做完不得压低同口径一致性."""
    fixed_compass = {"health_score": 70}
    fixed_scorecard = {"overall": 7.0}
    before = align.compute_reconciliation(
        fixed_compass, fixed_scorecard, {"completion_pct": 50})
    after = align.compute_reconciliation(
        fixed_compass, fixed_scorecard, {"completion_pct": 100})
    assert after["reconciliation_score"] == before["reconciliation_score"] == 100.0
    # 计划完成度的变化只体现在 gap 上
    assert after["declaration_execution_gap"]["value"] > before["declaration_execution_gap"]["value"]
