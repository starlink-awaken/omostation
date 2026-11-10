"""治理代码只在仓根 —— 宿主缓存里的嵌套副本不是治理代码。

缺陷（2026-11-11 自证）：`check-resolve-not-stub.py` 的 `GOVERNED_PATTERNS`
用子串匹配（`bin/gac/`），于是 `.codebase-memory/<id>/ws/bin/gac/…` 这类
**宿主工具缓存**里的历史 worktree 副本全被算成治理代码 —— 实测 1322 条匹配里
**752 条**来自 `.codebase-memory/`，其中两个 0 字节 `__init__.py` 让本检查器在
本地直接 FAIL（CI 无此目录故绿，属本地/CI 分歧）。

判据：`GOVERNED_PATTERNS` 以 `^` 锚定仓根。
本文件的用例端到端跑 `main()`（`REPO_ROOT` 指向临时树）。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "gac" / "check-resolve-not-stub.py"


def _load():
    spec = importlib.util.spec_from_file_location("resolve_not_stub_probe", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load()


def _run(monkeypatch, tmp_path: Path, files: dict) -> int:
    for rel, content in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    monkeypatch.setattr(MODULE, "REPO_ROOT", tmp_path)
    return MODULE.main()


def test_gitignored_host_cache_is_skipped(monkeypatch, tmp_path) -> None:
    """.codebase-memory 是 gitignore 的宿主工具缓存, 里面的 0 字节副本不算治理代码。"""
    files = {".codebase-memory/root-ac05/ws/bin/gac/__init__.py": ""}
    assert _run(monkeypatch, tmp_path, files) == 0, "宿主缓存副本被当成治理代码"


def test_nested_copy_outside_repo_root_is_not_governed(monkeypatch, tmp_path) -> None:
    """反例保护的一般形: 任何非仓根目录下的 bin/gac 副本都不算治理代码。"""
    files = {"vendor-copy/ws/bin/gac/__init__.py": ""}
    assert _run(monkeypatch, tmp_path, files) == 0, "嵌套副本被当成治理代码"


def test_repo_root_governed_file_is_still_checked(monkeypatch, tmp_path) -> None:
    """反例保护: 仓根治理目录里的 0 字节文件仍必须被抓。"""
    files = {"bin/gac/__init__.py": ""}
    assert _run(monkeypatch, tmp_path, files) == 1, "仓根治理文件未被检查"


def test_repo_root_stub_is_still_flagged(monkeypatch, tmp_path) -> None:
    """反例保护: 仓根治理文件里的 TODO 仍必须被抓。"""
    files = {"bin/gac/x.py": "# TODO: 待办\n"}
    assert _run(monkeypatch, tmp_path, files) == 1, "仓根 TODO 未被识别"
