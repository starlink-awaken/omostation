"""scene-signal-poller connector resolution — connector mapping coverage."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "scene_signal_poller", ROOT / "bin/ssot/scene-signal-poller.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["scene_signal_poller"] = module
    spec.loader.exec_module(module)
    return module


mod = _load_module()


def test_explicit_connector_wins():
    assert mod._resolve_connector("note.created", {"connector": "applenotes"}) == "applenotes"


def test_signal_name_mapping():
    assert mod._resolve_connector("note.created", {}) == "applenotes"
    assert mod._resolve_connector("email.received", {}) == "apple_mail"
    assert mod._resolve_connector("zhihu.item", {}) == "zhihu"
    assert mod._resolve_connector("github.event", {}) == "github"
    assert mod._resolve_connector("wechat.message", {}) == "wechat"
    assert mod._resolve_connector("file.changed", {}) == "local_files"
    # BET-Y2Q4-T7-02: 治理文档变更源 (本地工作区, 非 iris)
    assert mod._resolve_connector("doc.changed", {}) == "workspace_docs"
    assert mod._resolve_connector("document.changed", {}) == "workspace_docs"


def test_workspace_docs_local_source(tmp_path, monkeypatch):
    """workspace_docs 直读工作区 md, id 含 mtime (变更即新信号)."""
    (tmp_path / "docs").mkdir()
    a = tmp_path / "docs" / "alpha.md"
    a.write_text("# alpha\n", encoding="utf-8")
    monkeypatch.setattr(mod, "_ROOT", tmp_path)
    monkeypatch.setattr(mod, "WORKSPACE_DOC_ROOTS", ("docs",))

    items = mod._workspace_docs_list(limit=10)
    assert len(items) == 1
    assert items[0]["path"] == "docs/alpha.md"
    assert items[0]["platform"] == "workspace_docs"
    assert items[0]["id"].startswith("docs/alpha.md@")

    # 变更文件 → mtime 变 → 新 id (watermark 去重的变更检测语义)
    old_id = items[0]["id"]
    import os, time
    time.sleep(1.1)
    a.write_text("# alpha v2\n", encoding="utf-8")
    os.utime(a, None)
    items2 = mod._workspace_docs_list(limit=10)
    assert items2[0]["id"] != old_id


def test_iris_list_routes_workspace_docs(monkeypatch):
    """_iris_list 对 workspace_docs 不分派给 iris 子进程."""
    called = {"iris": False}

    def _boom(*a, **k):
        called["iris"] = True
        raise AssertionError("iris must not be called for workspace_docs")

    monkeypatch.setattr(mod.subprocess, "run", _boom)
    monkeypatch.setattr(mod, "_workspace_docs_list", lambda limit=10: [{"id": "x"}])
    assert mod._iris_list("workspace_docs", 5) == [{"id": "x"}]
    assert called["iris"] is False


def test_iris_prefix_format():
    assert mod._resolve_connector("iris:applenotes", {}) == "applenotes"


def test_unknown_signal_resolves_none():
    assert mod._resolve_connector("something.else", {}) is None
