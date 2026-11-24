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


# --- doc_links / doc_ssot：断链目标全属「输入没备齐」时，读数不可用 ---
#
# #5530 把这两项留在 red_items 里，而实测干净检出上 doc-link-check 的 11 条断链
# 全部指向未检出的子模块或 gitignore 覆盖的生成态 ⇒ 那条红传递的信息量是 0。


def test_doc_links_all_targets_absent_is_unavailable() -> None:
    red, not_measured = _load().classify_health(
        _report(doc_links={"ok": False, "unavailable": True})
    )
    assert red == []
    assert not_measured == ["doc_links"]


def test_doc_links_with_a_real_target_is_still_red() -> None:
    """反证三：只要有一个断链目标不属于「输入没备齐」，就必须仍算红。"""
    red, not_measured = _load().classify_health(
        _report(doc_links={"ok": False, "unavailable": False})
    )
    assert red == ["doc_links"]
    assert not_measured == []


def test_doc_ssot_all_conflict_sources_absent_is_unavailable() -> None:
    red, not_measured = _load().classify_health(
        _report(doc_ssot={"ok": False, "conflicts": 1, "unavailable": True})
    )
    assert red == []
    assert not_measured == ["doc_ssot"]


def test_doc_ssot_with_one_real_source_is_still_red() -> None:
    red, not_measured = _load().classify_health(
        _report(doc_ssot={"ok": False, "conflicts": 1, "unavailable": False})
    )
    assert red == ["doc_ssot"]
    assert not_measured == []


# --- 判据本体：抽成 helper 是为了让「折态」这件事本身可被变异对照 ---


def test_input_absent_accepts_absolute_and_relative_paths() -> None:
    """绝对路径与相对路径必须同解（锚在 WORKSPACE，不取调用方 cwd）。"""
    module = _load()
    ws = str(module.WORKSPACE)
    assert module.input_absent(".omo/state/system.yaml") is True  # gitignore 覆盖的生成态
    assert module.input_absent(ws + "/.omo/state/system.yaml") is True
    assert module.input_absent("bin/gac/gac-healthcheck.py") is False  # 就在本检出里


def test_repo_relative_anchors_at_workspace_not_cwd() -> None:
    """`repo_relative` 是那条缝：仓内 → 相对形式；仓外 → None。"""
    module = _load()
    ws = str(module.WORKSPACE)
    assert module.repo_relative(".omo/state/system.yaml") == ".omo/state/system.yaml"
    assert module.repo_relative(ws + "/.omo/state/system.yaml") == ".omo/state/system.yaml"
    assert module.repo_relative("/etc/hosts") is None


def test_input_absent_treats_submodule_path_same_in_both_forms() -> None:
    """反证四：子模块规则必须对两种写法一致 —— 否则分类随调用目录/写法漂移。

    不断言具体值（本机与 CI 的子模块检出程度不同），只断言**同解**。
    """
    module = _load()
    rel = "projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml"
    assert module.input_absent(rel) is module.input_absent(str(module.WORKSPACE / rel))


def test_input_absent_rejects_paths_outside_the_checkout() -> None:
    """仓外路径不属「本检出的输入没备齐」—— 它必须让本项保持可测。"""
    assert _load().input_absent("/etc/hosts") is False


def test_unavailable_if_all_absent_empty_set_is_measurable() -> None:
    """空集不算不可用：没有断链/冲突就没有「因输入缺席而读不到」这回事。"""
    assert _load().unavailable_if_all_absent([]) is False


def test_unavailable_if_all_absent_true_only_when_every_target_absent() -> None:
    """反证五：一个目标在、其余全缺席 ⇒ 仍算可测（不得被折成不可用）。"""
    module = _load()
    assert module.unavailable_if_all_absent([".omo/state/system.yaml"]) is True
    mixed = [".omo/state/system.yaml", "bin/gac/gac-healthcheck.py"]
    assert module.unavailable_if_all_absent(mixed) is False


def test_doc_link_absent_targets_skip_findings_without_resolved() -> None:
    module = _load()
    targets = module.doc_link_absent_targets(
        {"findings": [{"resolved": "projects/ecos/src/x.yaml"}, {"target": "无 resolved"}]}
    )
    assert targets == ["projects/ecos/src/x.yaml"]


def test_doc_ssot_absent_targets_only_take_workspace_paths() -> None:
    module = _load()
    ws = str(module.WORKSPACE)
    targets = module.doc_ssot_absent_targets(
        {
            "findings": [
                {"reason": f"L0 约束源缺失: {ws}/projects/ecos/a.yaml / {ws}/projects/omo/b.md"},
                {"reason": "别的机器上的路径: /home/someone/else/x.yaml"},
            ]
        }
    )
    assert targets == [f"{ws}/projects/ecos/a.yaml", f"{ws}/projects/omo/b.md"]
