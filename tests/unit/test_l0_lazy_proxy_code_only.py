"""L0 调用点判据只认代码 —— 注释/docstring 里的 `lazy=False` 不是违规。

缺陷（2026-11-11 自证）：`check-l0-constraints.py::check_cr_mcp_lazy_01`
（CR-MCP-LAZY-01 / E-L0-011，**阻塞型** L0 约束）对文件全文跑
`proxy_manager\\.start\\([^)]*lazy\\s*=\\s*False` 之类的正则，注释或
docstring 里提到同一形态即被判成「检出 lazy=False (eager 初始化)」。

实测反例（正则直调，未改子模块）：

- `# 旧实现: proxy_manager.start(host, port, lazy=False)` ⇒ bad=True
- `add_service(name, lazy=False) 是旧的 eager 形态。` 写进 docstring ⇒ bad=True

判据：匹配前用 AST 抹掉 docstring / 字符串常量 / 注释。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "gac" / "check-l0-constraints.py"

BOOTSTRAP = "projects/agora/src/agora/mcp/mcp_bootstrap.py"
SWARM = "projects/agora/src/agora/mcp/swarm.py"


def _load():
    spec = importlib.util.spec_from_file_location("l0_lazy_probe", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load()


def _check(monkeypatch, tmp_path: Path, files: dict) -> tuple[bool, str]:
    for rel, text in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    monkeypatch.setattr(MODULE, "REPO", tmp_path)
    return MODULE.check_cr_mcp_lazy_01()


GOOD = {
    BOOTSTRAP: "def boot():\n    proxy_manager.start(host, port, lazy=True)\n",
    SWARM: "def add():\n    proxy.add_service(name, handler, lazy=True)\n",
}


def test_comment_mentioning_lazy_false_is_not_a_violation(monkeypatch, tmp_path) -> None:
    """注释里回顾旧形态 (lazy=False) 不算 eager 违规。"""
    files = dict(GOOD)
    files[BOOTSTRAP] = "# 旧实现: proxy_manager.start(host, port, lazy=False) —— 已改 lazy=True\n" + GOOD[BOOTSTRAP]
    ok, msg = _check(monkeypatch, tmp_path, files)
    assert ok, f"注释里的 lazy=False 被当成违规: {msg}"


def test_docstring_mentioning_lazy_false_is_not_a_violation(monkeypatch, tmp_path) -> None:
    """docstring 里说明旧形态同理。"""
    files = dict(GOOD)
    files[SWARM] = '"""Swarm.\n\n' + "add_service(name, lazy=False) 是已废弃的 eager 形态。\n" + '"""\n' + GOOD[SWARM]
    ok, msg = _check(monkeypatch, tmp_path, files)
    assert ok, f"docstring 里的 lazy=False 被当成违规: {msg}"


def test_string_literal_mentioning_lazy_false_is_not_a_violation(monkeypatch, tmp_path) -> None:
    """字符串常量里的同形态也不是调用。"""
    files = dict(GOOD)
    files[BOOTSTRAP] = 'LEGACY = "proxy_manager.start(host, port, lazy=False)"\n' + GOOD[BOOTSTRAP]
    ok, msg = _check(monkeypatch, tmp_path, files)
    assert ok, f"字符串里的 lazy=False 被当成违规: {msg}"


def test_real_lazy_false_is_still_flagged(monkeypatch, tmp_path) -> None:
    """反例保护: 代码里的真 lazy=False 必须仍被拦下。"""
    files = dict(GOOD)
    files[BOOTSTRAP] = "def boot():\n    proxy_manager.start(host, port, lazy=False)\n"
    ok, msg = _check(monkeypatch, tmp_path, files)
    assert not ok, f"真实 lazy=False 未被拦下: {msg}"
    assert "eager" in msg


def test_missing_lazy_true_is_still_flagged(monkeypatch, tmp_path) -> None:
    """反例保护: 调用点整个消失 (fail-closed) 仍要报。"""
    files = {BOOTSTRAP: "def boot():\n    proxy_manager.start(host, port)\n", SWARM: GOOD[SWARM]}
    ok, msg = _check(monkeypatch, tmp_path, files)
    assert not ok, f"缺失 lazy=True 未被报: {msg}"
