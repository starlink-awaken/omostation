"""Tests that brief readers honor OMOSTATION_STATE_ROOT without relative_to errors."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_brief_readers_fallback_to_workspace_root_when_state_root_unset(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.delenv("OMOSTATION_STATE_ROOT", raising=False)
    detector = _load("bin/ssot/drift-face-detector.py", "detector_brief_unset")
    pruner = _load("bin/ssot/auto-pruner.py", "pruner_brief_unset")
    ws = tmp_path / "ws"
    brief = ws / "runtime/dashboard/agent-brief.json"
    brief.parent.mkdir(parents=True)
    brief.write_text(json.dumps({"generated_at": "2020-01-01T00:00:00+00:00"}), encoding="utf-8")

    monkeypatch.setattr(detector, "WORKSPACE_ROOT", ws)
    monkeypatch.setattr(pruner, "WORKSPACE_ROOT", ws)

    findings = detector.detect_brief()
    actions = pruner.prune_brief(dry_run=True)
    assert len(findings) == 1 and findings[0]["id"] == "BRIEF-STALE"
    assert findings[0]["path"] == "runtime/dashboard/agent-brief.json"
    assert len(actions) == 1 and actions[0]["id"] == "BRIEF-CONTENT-AGE"
    assert actions[0]["path"] == "runtime/dashboard/agent-brief.json"


def test_brief_readers_prefer_state_root_without_relative_to_crash(
    tmp_path, monkeypatch
) -> None:
    ws = tmp_path / "ws"
    state = tmp_path / "state"
    ws.mkdir()
    brief = state / "runtime/dashboard/agent-brief.json"
    brief.parent.mkdir(parents=True)
    brief.write_text(json.dumps({"generated_at": "2020-01-01T00:00:00+00:00"}), encoding="utf-8")

    monkeypatch.setenv("OMOSTATION_STATE_ROOT", str(state))
    detector = _load("bin/ssot/drift-face-detector.py", "detector_brief_state")
    pruner = _load("bin/ssot/auto-pruner.py", "pruner_brief_state")
    monkeypatch.setattr(detector, "WORKSPACE_ROOT", ws)
    monkeypatch.setattr(pruner, "WORKSPACE_ROOT", ws)

    findings = detector.detect_brief()
    actions = pruner.prune_brief(dry_run=True)
    assert len(findings) == 1 and findings[0]["id"] == "BRIEF-STALE"
    assert findings[0]["path"] == str(brief)
    assert len(actions) == 1 and actions[0]["id"] == "BRIEF-CONTENT-AGE"
    assert actions[0]["path"] == str(brief)
