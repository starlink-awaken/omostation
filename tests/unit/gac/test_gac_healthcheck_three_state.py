"""healthcheck 的总体聚合必须是三态：测出红 / 读数不可用 / 已退役待裁。

缺陷（2026-11-24）：`healthy` 是一个布尔，把三类状态折在一起 ——
(a) 测出红、(b) **读数不可用**（工具没跑起来）、(c) **链路已退役待裁**。
后果是干净检出上 `总体: ❌ 有红` 恒成立；而其中 `legacy_drift` 那条红传递的信息量
是 0（债务条目 GAC-INGEST-LEGACY-REFS-NOT-FOLLOWED 自己写着「健康检查的总体结论
因此长期带红，而这条红传递的信息是 0」）。恒真的结论等于没有结论，读者会学会忽略整份报告。

同口径参照：`gac-local-gate` 的 preflight / `not_measured`、`gac-executor` 的
`executors_not_checked`（#5525）、`architecture-drift` 按登记面而非分类目录取集合。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin" / "gac" / "gac-healthcheck.py"


def _load():
    spec = importlib.util.spec_from_file_location("gac_healthcheck_three_state", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _report(**overrides):
    """一份形状齐全的报告；只按需要覆写单项。"""
    base = {
        "validate": {"ok": True},
        "drift": {"ok": True},
        "adr_residue_0104": 0,
        "coverage": {"dimension_complete": True},
        "doc_ssot": {"ok": True},
        "doc_snapshots": {"ok": True},
        "doc_links": {"ok": True},
        "submodule_reachability": {"ok": True},
        "hygiene": {"ok": True},
        "registry_drift": {"ok": True},
        "bootstrap": {"ok": True},
        "ci_plane": {"ok": True},
        "ssot_usage": {"ok": True},
        "files": {"missing": []},
        "m2_type": {"ok": True},
        "legacy_drift": {"ok": True, "retired": False},
        "m1_instance_drift": {"ok": True, "unavailable": False},
        "executor_drift": {"ok": True, "unchecked_only": False},
    }
    base.update(overrides)
    return base


def test_all_measurable_green_yields_no_red_and_no_unmeasured() -> None:
    red, not_measured = _load().classify_health(_report())
    assert red == []
    assert not_measured == []


def test_genuine_red_is_reported_as_red() -> None:
    """反证一：真红必须落在 red_items 里，且不是未判定。"""
    red, not_measured = _load().classify_health(_report(doc_links={"ok": False}))
    assert red == ["doc_links"]
    assert not_measured == []


def test_retired_item_is_not_counted_as_red() -> None:
    """退役待裁（工具被归档）不算红 —— 这是本改动的主对象。"""
    red, not_measured = _load().classify_health(
        _report(legacy_drift={"ok": False, "retired": True})
    )
    assert red == [], "退役项被算成了红"
    assert not_measured == ["legacy_drift"]


def test_unavailable_reading_is_not_counted_as_red() -> None:
    """工具没跑起来（非 JSON 输出）⇒ 读数不可用，不是测出红。"""
    red, not_measured = _load().classify_health(
        _report(m1_instance_drift={"ok": False, "unavailable": True})
    )
    assert red == []
    assert not_measured == ["m1_instance_drift"]


def test_executors_under_unchecked_submodules_are_not_missing() -> None:
    """候选全在未检出的子模块里 ⇒ 没测成，不算 executor 缺失（#5525 的同类）。"""
    red, not_measured = _load().classify_health(
        _report(executor_drift={"ok": False, "unchecked_only": True})
    )
    assert red == []
    assert not_measured == ["executor_drift"]


def test_core_files_missing_only_in_absent_submodules_are_unavailable() -> None:
    """核心文件全部因未检出子模块而缺席 ⇒ 输入没备齐，不是文件缺失。"""
    red, not_measured = _load().classify_health(
        _report(files={"missing": ["projects/omo/src/omo/cli.py"], "unavailable": True})
    )
    assert red == []
    assert not_measured == ["core_files"]


def test_partial_absence_is_still_a_real_red() -> None:
    """反证二：只要有一个缺席不属于「输入没备齐」，就必须仍算红。"""
    red, not_measured = _load().classify_health(
        _report(files={"missing": ["README.md"], "unavailable": False})
    )
    assert red == ["core_files"]
    assert not_measured == []


def test_m2_absent_only_because_submodule_unchecked_is_unavailable() -> None:
    red, not_measured = _load().classify_health(_report(m2_type={"ok": False, "unavailable": True}))
    assert red == []
    assert not_measured == ["m2_type"]


def test_healthy_flag_follows_red_items_only() -> None:
    """`healthy` 只由 red_items 决定 —— 未判定项不得让它变 ❌。"""
    module = _load()
    report = _report(legacy_drift={"ok": False, "retired": True})
    red, not_measured = module.classify_health(report)
    assert not red and not_measured == ["legacy_drift"]
