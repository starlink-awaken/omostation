"""B4b 验收尺的缝可达性自证 (BET-Y2Q4-T10-281).

scripts/tools/launchd-workspace-reality-check.py 是 plan §分期 B4b 判据
「指向 Workspace 的 plist 由 43 → 0」的量具。它原先把 repo_root 缝算成
`parents[1] / "lib"` = scripts/lib —— 该目录按构造不存在, 于是每次运行都走
`except ImportError` 的字面量兜底: canonical/code 钉死在某台机器的检出路径,
install 兜底永不返回 None (与 repo_root 契约相反)。后果是这把尺在 B4b 目标态
达成后仍会报「指向 Workspace」。

四条用例: 正向落点、尺内无字面量、注入旧形状的合成违规必红 (尺不得按构造就绿)、
安装位缺席时 fail-closed 而非静默退回检出根。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
RULER = REPO / "scripts" / "tools" / "launchd-workspace-reality-check.py"
SEAM_LINE = '_LIB_DIR = Path(__file__).resolve().parents[2] / "bin" / "lib"'


def _exec(path: Path, name: str) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


def _load_ruler(monkeypatch) -> object:
    # 尺的 canonical_root 会兜底 ~/Workspace; hermetic 复跑不得读 host 面。
    monkeypatch.setenv("OMOSTATION_ROOT", str(REPO))
    monkeypatch.delenv("OMOSTATION_STATE_ROOT", raising=False)
    monkeypatch.delenv("OMOSTATION_ROOT_OVERRIDE", raising=False)
    return _exec(RULER, "b4b_ruler_under_test")


def test_ruler_seam_resolves_to_the_real_repo_root(monkeypatch) -> None:
    """正向落点: 三个 resolver 必须来自 repo_root 模块, 不是尺自己的局部 def。"""
    module = _load_ruler(monkeypatch)
    for name in ("canonical_root", "code_root", "install_root"):
        fn = getattr(module, name)
        assert fn.__module__ == "repo_root", f"{name} 来自兜底局部函数 —— 缝又不可达了"
    assert Path(module.canonical_root()) == REPO


def test_ruler_source_has_no_checkout_literal() -> None:
    """判据与读数不共享失效模式: 直接按尺自己的源码文本查字面量。"""
    text = RULER.read_text(encoding="utf-8")
    assert 'Path("/Users' not in text, "尺内重新出现了硬编码检出根"
    assert 'parents[1] / "lib"' not in text, "缝又算回 scripts/lib"


def test_seam_depth_mutation_is_caught_by_the_guard(tmp_path: Path) -> None:
    """合成违规自证: 缝改回 parents[1] 时守卫必须当场拒, 而不是静默降级。"""
    mutated = RULER.read_text(encoding="utf-8").replace(
        SEAM_LINE,
        '_LIB_DIR = Path(__file__).resolve().parents[1] / "lib"',
    )
    assert mutated != RULER.read_text(encoding="utf-8"), (
        "变异点未命中 —— 本用例的断言按构造不可信"
    )
    bad = tmp_path / "scripts" / "tools" / "ruler_mutated.py"
    bad.parent.mkdir(parents=True)
    bad.write_text(mutated, encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        _exec(bad, "b4b_ruler_mutated")
    assert "缝不可达" in str(exc.value)


def test_ruler_fails_closed_when_install_root_absent(monkeypatch, tmp_path: Path) -> None:
    """install_root() 返回 None 时不得静默退回检出根 (ADR-0456 B4b 契约)。"""
    module = _load_ruler(monkeypatch)
    monkeypatch.setattr(module, "install_root", lambda: None)
    fake_dir = tmp_path / "LaunchAgents"
    fake_dir.mkdir()
    (fake_dir / "com.example.plist").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"'
        ' "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0"><dict>\n'
        "<key>Label</key><string>com.example</string>\n"
        "<key>ProgramArguments</key><array><string>/bin/echo</string></array>\n"
        "</dict></plist>\n",
        encoding="utf-8",
    )
    with pytest.raises(SystemExit) as exc:
        module.scan_launchd_workspace_targets(launchd_dir=fake_dir)
    assert "安装位" in str(exc.value)
