"""check-readme-hardcoded 的计数判据自证 —— 真计数要抓, 序数/阈值不能抓。

缺陷背景 (2026-11-10 实测): COUNT_RE 旧式 `(\\d+)\\s*(个|条|项|…)` 把
CLAUDE.md 里两处**正常措辞**报成「硬编码计数」:
  · L54「如果命中 ≥1 条相关记录」—— 这是**阈值**, 不是「此处有多少个」
  · L98「（第 4 条 · 需求迭代强制 Workflow）」—— 这是**序数** (章节号)
误报会训练读者忽略这份报告, 于是真正的陈旧计数 (README 曾写「12 个 SSOT
文件」而 SSOT_FILES 实为 13 项) 也跟着被无视。

本测试钉住判据的两面: 真计数必须命中, 序数/阈值必须放过。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin" / "gac" / "check-readme-hardcoded.py"


@pytest.fixture()
def module():
    spec = importlib.util.spec_from_file_location("check_readme_hardcoded", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


TRUE_COUNTS = [
    "12 个 SSOT 文件的 SHA-256 变更追踪",
    "仓库有 30 个 agent",
    "共 8 项",
    "3 个 BET 已关闭",
]

FALSE_POSITIVES = [
    "如果命中 ≥1 条相关记录",
    "（第 4 条 · 需求迭代强制 Workflow）",
    "第4条",
    "≥ 3 项",
    "< 5 个 PR",
]


@pytest.mark.parametrize("text", TRUE_COUNTS)
def test_real_counts_are_caught(module, text: str) -> None:
    assert module.COUNT_RE.search(text), text


@pytest.mark.parametrize("text", FALSE_POSITIVES)
def test_ordinals_and_thresholds_are_not_counts(module, text: str) -> None:
    assert module.COUNT_RE.search(text) is None, text


def test_real_repository_is_clean(module) -> None:
    """真实仓库: README/CLAUDE.md 当前不该有硬编码计数/端口/陈旧日期。"""
    issues: list[dict] = []
    for name in ("README.md", "CLAUDE.md"):
        issues.extend(module.check_file(ROOT / name))
    assert issues == [], issues
