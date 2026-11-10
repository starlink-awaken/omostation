"""doc-link-check 必须跳过 .gitignore 覆盖的生成物目标。

缺陷背景 (2026-11-10): `doc-link-check.py` 是**已接线**的门禁 (gac-local-gate),
判据是 `target_path.exists()` —— 于是 markdown 链接指向运行期生成物
(如 `.omo/state/*.yaml`) 时, 干净检出不报、本机报, CI 与本地口径不一致。
与 `check-cross-refs` / `CR-OMO-SURFACE-01` 属同一类「判据与检出形态不兼容」。

本文件钉住 `_is_gitignored()` 的两面: 命中的要豁免, 未命中的不得误豁免。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin" / "gac" / "doc-link-check.py"


@pytest.fixture()
def module():
    spec = importlib.util.spec_from_file_location("doc_link_check_gitignore", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_generated_target_is_recognised(module, tmp_path: Path) -> None:
    """.omo/state/*.yaml 在真实 .gitignore 里 (:304) —— 必须被豁免。"""
    target = ROOT / ".omo" / "state" / "health.yaml"
    assert module._is_gitignored(target) is True


def test_tracked_target_is_not_exempted(module) -> None:
    """未被忽略的跟踪文件不得被误豁免 —— 否则判据会被整体架空。"""
    target = ROOT / "docs" / "README.md"
    if not target.is_file():
        pytest.skip("docs/README.md 不在当前检出")
    assert module._is_gitignored(target) is False


def test_path_outside_repo_is_not_exempted(module, tmp_path: Path) -> None:
    """仓库外的路径 (如 ~/Documents) 既不该崩也不该被豁免。"""
    assert module._is_gitignored(tmp_path / "x.md") is False


def test_probe_failure_is_not_exempted(module, monkeypatch) -> None:
    """git 探测失败时返回 False (不豁免), 保持判据偏严。"""
    def boom(*a, **k):
        raise RuntimeError("git unavailable")

    monkeypatch.setattr(module.subprocess, "run", boom)
    assert module._is_gitignored(ROOT / ".omo" / "state" / "health.yaml") is False


def test_check_links_skips_gitignored_target(module) -> None:
    """端到端: markdown 链接指向 gitignored 生成物时不得报死链。

    上面三条只测 `_is_gitignored()` 这个零件 —— 把过滤那三行删掉它们照样绿
    (变异不红)。这条直接打 `check_links()` 本体。
    """
    probe = ROOT / ".linkcheck-gitignore-probe"
    probe.mkdir(exist_ok=True)
    try:
        (probe / "doc.md").write_text(
            "# t\n\n[gen](../.omo/state/health.yaml)\n", encoding="utf-8"
        )
        assert module.check_links(probe) == []
    finally:
        for p in sorted(probe.rglob("*"), reverse=True):
            p.rmdir() if p.is_dir() else p.unlink()
        probe.rmdir()


def test_check_links_still_flags_real_breakage(module) -> None:
    """反面: 非 gitignored 的死链仍须报出来 (否则豁免逻辑把判据架空)。"""
    probe = ROOT / ".linkcheck-gitignore-probe"
    probe.mkdir(exist_ok=True)
    try:
        (probe / "doc.md").write_text(
            "# t\n\n[dead](../docs/NO-SUCH-FILE.md)\n", encoding="utf-8"
        )
        broken = module.check_links(probe)
        assert any("NO-SUCH-FILE.md" in b["link"] for b in broken), broken
    finally:
        for p in sorted(probe.rglob("*"), reverse=True):
            p.rmdir() if p.is_dir() else p.unlink()
        probe.rmdir()
