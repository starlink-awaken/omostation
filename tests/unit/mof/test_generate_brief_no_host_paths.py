"""BRIEF.md is a committed generated artifact — it must not encode the host that built it.

Regression guard for the 2026-09-24 retro finding: ``generate_brief_content()``
emitted ``file://{WORKSPACE}/...`` links, so whichever worktree ran the generator
left its absolute path in git (origin/main carried a dead ``ws-p0-claims-gat010``
link long after that worktree was released).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin" / "mof" / "generate-brief.py"


def _load_module() -> object:
    spec = importlib.util.spec_from_file_location("generate_brief", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _render_one_decision(monkeypatch: pytest.MonkeyPatch) -> tuple[str, object]:
    module = _load_module()
    monkeypatch.setattr(module, "SYSTEM_YAML", Path("/nonexistent/system.yaml"))
    monkeypatch.setattr(
        module,
        "scan_decision_inbox",
        lambda: [
            {
                "source": "omo-debt",
                "title": "planned 卡 status 归一",
                "path": ".omo/tasks/archived/done/w3w3-planned-status-normalize.yaml",
            }
        ],
    )
    monkeypatch.setattr(module, "scan_active_pitfalls", lambda: [])
    monkeypatch.setattr(module, "scan_x3_metrics", lambda: {"creations": 0, "knowledge_reuse": 0})
    monkeypatch.setattr(module, "run_write_owner_audit", lambda: [])
    return module.generate_brief_content(), module


def test_decision_inbox_links_are_repo_relative(monkeypatch: pytest.MonkeyPatch) -> None:
    content, _module = _render_one_decision(monkeypatch)

    assert "](<.omo/tasks/archived/done/w3w3-planned-status-normalize.yaml>)" in content


def test_brief_content_carries_no_host_absolute_path(monkeypatch: pytest.MonkeyPatch) -> None:
    content, module = _render_one_decision(monkeypatch)

    assert "file://" not in content
    assert str(module.WORKSPACE) not in content
    assert "/Users/" not in content
