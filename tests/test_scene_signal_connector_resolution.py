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


def test_iris_prefix_format():
    assert mod._resolve_connector("iris:applenotes", {}) == "applenotes"


def test_unknown_signal_resolves_none():
    assert mod._resolve_connector("something.else", {}) is None
