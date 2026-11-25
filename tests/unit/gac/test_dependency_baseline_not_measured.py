"""dependency-baseline-drift：扫描面不完整时不得把 STALE/MISSING 当结论。

`projects/**/pyproject.toml` 是推导基准的来源；有子模块未检出时这些文件不在本检出里，
于是全量 baseline 的条目都被算成「已移除」。旧实现逐条报（干净检出实测 74 项），
读数与「真的移除了一批依赖」同形。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[3] / "bin" / "mof" / "gen-dependency-baseline.py"
)


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("dep_baseline_nm", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_unchecked_marks_dash_prefix_only(mod):
    sample = (
        " a1b2c3d projects/ecos (v1)\n"
        "-9f8e7d6 projects/agora (heads/main)\n"
        " 0123456 projects/agora/projects/l4-kernel (v2)\n"
        "-abcdef0 projects/knowledge/gbrain (v3)\n"
    )
    assert mod._parse_unchecked(sample) == [
        "projects/agora",
        "projects/knowledge/gbrain",
    ]


def test_measured_when_no_drift(mod, monkeypatch):
    """没有 drift 就没有「因扫描不全而误判」这回事，必须算测过。"""
    monkeypatch.setattr(mod, "unchecked_gitlinks", lambda: ["projects/agora"])
    assert mod.measured_flag(0) == (True, ["projects/agora"])


def test_not_measured_when_drift_and_scan_incomplete(mod, monkeypatch):
    monkeypatch.setattr(
        mod,
        "unchecked_gitlinks",
        lambda: ["projects/agora", "projects/knowledge/gbrain"],
    )
    measured, unchecked = mod.measured_flag(68)
    assert measured is False
    assert unchecked == ["projects/agora", "projects/knowledge/gbrain"]


def test_measured_when_all_submodules_checked_out(mod, monkeypatch):
    """反证：扫描面完整时即便有 drift 也必须仍算可测（不得恒折成未判定）。"""
    monkeypatch.setattr(mod, "unchecked_gitlinks", lambda: [])
    assert mod.measured_flag(68) == (True, [])


def test_real_repo_unchecked_matches_git(mod):
    """在真实仓上跑一次：本函数必须与 `git submodule status --recursive` 一致。"""
    out = mod.unchecked_gitlinks()
    assert isinstance(out, list)
    # 每个条目都应是 .gitmodules 里的子模块路径（本仓顶层或嵌套）
    assert all(p.startswith("projects/") for p in out)
