"""BET-Y2Q4-T10-352 — internal-scene-preflight proposal-lock 二选一语义.

根因: 锁要求 forbidden/proposal_only 但两值不在 standards 枚举, 显式写了
合法值的卡必违反 (自相矛盾红线)。修复: 枚举正式化 + proposal_lock_exemption
显式豁免通道 (owner 裁定 (a) 路线, 红线本体保留).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

MODULE_PATH = Path(__file__).parents[1] / "bin" / "ssot" / "internal-scene-preflight.py"
STANDARDS_PATH = Path(__file__).parents[1] / ".omo" / "standards" / "scene-card-lifecycle.yaml"


def _module():
    spec = importlib.util.spec_from_file_location("preflight_under_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _base_card() -> dict:
    """一张典型 internal_pipeline 卡 (supervised/active —— 违锁的常见态)."""
    return {
        "scene_id": "probe-internal",
        "scene_type": "internal_pipeline",
        "lifecycle": "supervised",
        "activation": "active",
    }


def test_lock_reports_without_exemption():
    """无豁免时红线照报 (红线本体保留)."""
    m = _module()
    r = m.build_preflight(_base_card(), root=Path("."))
    assert "activation_must_be_forbidden" in r["missing_fields"]
    assert "lifecycle_must_be_proposal_only" in r["missing_fields"]


def test_exemption_releases_lock():
    """BET-Y2Q4-T10-352: 显式 proposal_lock_exemption 豁免 → 两把锁放行."""
    m = _module()
    card = _base_card()
    card["proposal_lock_exemption"] = "owner 裁定 (a): 该内部场景正式投运 (T10-352)"
    r = m.build_preflight(card, root=Path("."))
    assert "activation_must_be_forbidden" not in r["missing_fields"]
    assert "lifecycle_must_be_proposal_only" not in r["missing_fields"]


def test_compliant_values_pass_without_exemption():
    """合规值 (forbidden/proposal_only) 本来就过 —— 枚举正式化后此路可用."""
    m = _module()
    card = _base_card()
    card["activation"] = "forbidden"
    card["lifecycle"] = "proposal_only"
    r = m.build_preflight(card, root=Path("."))
    assert "activation_must_be_forbidden" not in r["missing_fields"]
    assert "lifecycle_must_be_proposal_only" not in r["missing_fields"]


def test_standards_enums_formalized():
    """standards 枚举必须含 proposal_only (lifecycle) 与 forbidden (activation)."""
    d = yaml.safe_load(open(STANDARDS_PATH, encoding="utf-8"))
    assert "proposal_only" in d["lifecycle"], "lifecycle 枚举缺 proposal_only"
    assert "forbidden" in d["activation"], "activation 枚举缺 forbidden"
    assert d["lifecycle"]["proposal_only"]["can_execute"] is False
