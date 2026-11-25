"""capability-ownership / auto-fix-loop：error 目标全属「输入没备齐」⇒ 未判定。

两处同因（都报 `projects/ecos/src/ecos/ssot/tools` 这类未检出子模块里的实现缺失）。
判据抽成各自的 `measured_flag()`，本文件直接驱动它，不依赖注册表状态。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def capown():
    return _load("capown_nm", "bin/gac/check-capability-ownership.py")


@pytest.fixture(scope="module")
def autofix():
    return _load("autofix_nm", "bin/gac/auto-fix-loop.py")


def test_input_absent_true_for_unchecked_submodule(capown, autofix, tmp_path):
    """两个脚本各自实现的 `_input_absent` 必须同解。"""
    for mod, attr in ((capown, "ROOT"), (autofix, "WORKSPACE")):
        mod.__dict__[attr] = tmp_path.resolve()
    target = "projects/ecos/src/ecos/ssot/tools"
    assert capown._input_absent(target) is True
    assert autofix._input_absent(target) is True


def test_input_absent_false_for_existing_tracked_file(capown, autofix, tmp_path):
    f = tmp_path / "README.md"
    f.write_text("# x\n", encoding="utf-8")
    for mod, attr in ((capown, "ROOT"), (autofix, "WORKSPACE")):
        mod.__dict__[attr] = tmp_path.resolve()
    assert capown._input_absent("README.md") is False
    assert autofix._input_absent("README.md") is False


def test_measured_flag_empty_is_measured(capown, autofix):
    assert capown.measured_flag([]) == (True, [])
    assert autofix.measured_flag([]) == (True, [])


def test_auto_fix_all_paths_absent_is_not_measured(autofix, tmp_path):
    autofix.WORKSPACE = tmp_path.resolve()
    drifts = [
        autofix.Drift("PATH-DRIFT", "error", "x", paths=("projects/ecos/src/a",)),
        autofix.Drift("PATH-DRIFT", "error", "y", paths=("projects/omo/src/b", "projects/agora/etc/c")),
    ]
    measured, paths = autofix.measured_flag(drifts)
    assert measured is False
    assert len(paths) == 3


def test_auto_fix_one_real_path_is_measured(autofix, tmp_path):
    """反证：混进一个不属于输入缺席的目标 ⇒ 仍算可测（不得整体折没）。"""
    autofix.WORKSPACE = tmp_path.resolve()
    real = tmp_path / "really-missing.md"
    drifts = [
        autofix.Drift("PATH-DRIFT", "error", "x", paths=("projects/ecos/src/a",)),
        autofix.Drift("PATH-DRIFT", "error", "y", paths=(str(real),)),
    ]
    measured, _ = autofix.measured_flag(drifts)
    assert measured is True


def test_capown_all_error_paths_absent_is_not_measured(capown, tmp_path):
    capown.ROOT = tmp_path.resolve()
    findings = [
        capown.Finding("IMPL-EXISTS", "error", "x", "cap-a", "projects/ecos/src/a"),
        capown.Finding("IMPL-EXISTS", "error", "y", "cap-b", "projects/omo/src/b"),
    ]
    measured, paths = capown.measured_flag(findings)
    assert measured is False
    assert len(paths) == 2


def test_capown_info_findings_do_not_affect_measurement(capown, tmp_path):
    """info 级（孤儿能力）不进 error 集合，不应影响 measured。"""
    capown.ROOT = tmp_path.resolve()
    findings = [capown.Finding("IMPL-REGISTERED", "info", "z", "bin/workspace")]
    assert capown.measured_flag(findings) == (True, [])
