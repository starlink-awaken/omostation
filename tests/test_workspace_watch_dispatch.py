from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _module():
    path = Path(__file__).parents[1] / "bin/gac/workspace-watch-dispatch.py"
    spec = importlib.util.spec_from_file_location("workspace_watch_dispatch", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_watch_groups_are_canonical_and_have_no_legacy_documents_commands() -> None:
    module = _module()
    WATCH_GROUPS = module.WATCH_GROUPS

    assert {group.name for group in WATCH_GROUPS} == {
        "domain-manifests",
        "workspace-state",
        "inbox-router",
        "weekly-verdict",
    }
    legacy = ("domain-sync.py", "bridge-refresh.py", "session-brief.py", "weekly-verdict-generator.py")
    for group in WATCH_GROUPS:
        assert not any(token in " ".join(group.command) for token in legacy)


def test_dispatch_writes_stamps_under_workspace_and_marks_verdict_pending(tmp_path: Path) -> None:
    module = _module()
    WatchGroup, dispatch_once = module.WatchGroup, module.dispatch_once

    documents = tmp_path / "Documents"
    workspace = tmp_path / "Workspace"
    watched = documents / "@公共" / "_control" / "L4-DOMAIN-REGISTRY.yaml"
    watched.parent.mkdir(parents=True)
    watched.write_text("manifests: []\n", encoding="utf-8")
    stamps = workspace / "runtime" / "stamps.json"
    group = WatchGroup("domain-manifests", (watched,), ("owner", "domain"))
    verdict_file = workspace / "data" / "cards" / "cards.db"
    verdict_file.parent.mkdir(parents=True)
    verdict_file.write_bytes(b"cards")
    verdict = WatchGroup("weekly-verdict", (verdict_file,), ())
    calls: list[tuple[str, tuple[str, ...]]] = []

    def runner(name: str, command: tuple[str, ...]) -> int:
        calls.append((name, command))
        return 0

    events = dispatch_once((group, verdict), stamps_path=stamps, runner=runner)

    assert {event["group"] for event in events} == {"domain-manifests", "weekly-verdict"}
    assert next(event for event in events if event["group"] == "weekly-verdict")["status"] == "pending"
    assert calls == [("domain-manifests", ("owner", "domain"))]
    assert json.loads(stamps.read_text(encoding="utf-8"))
    assert not (documents / "_generated").exists()


def test_stable_inputs_do_not_run_owners(tmp_path: Path) -> None:
    module = _module()
    WatchGroup, dispatch_once = module.WatchGroup, module.dispatch_once

    watched = tmp_path / "watched"
    watched.write_text("same", encoding="utf-8")
    stamps = tmp_path / "Workspace" / "stamps.json"
    stamps.parent.mkdir()
    stamps.write_text(json.dumps({"one": watched.stat().st_mtime}), encoding="utf-8")
    calls: list[str] = []

    events = dispatch_once((WatchGroup("one", (watched,), ("owner",)),), stamps_path=stamps, runner=lambda name, command: calls.append(name) or 0)

    assert events == []
    assert calls == []
