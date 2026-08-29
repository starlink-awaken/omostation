"""Regression tests for the legacy decide compatibility adapter."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import cockpit.commands.decide as decide


def test_decide_list_reads_canonical_scene_intents(monkeypatch, capsys) -> None:
    """Legacy decide list must consume the canonical scenario-inbox shape."""
    canonical = {
        "ok": True,
        "scenes": [
            {
                "id": "scene-1",
                "journeys": [
                    {
                        "id": "journey-1",
                        "intents": [
                            {
                                "id": "intent-123456789",
                                "status": "pending",
                                "source": "manual",
                                "raw_content": "Review the migration plan",
                            }
                        ],
                    }
                ],
            }
        ],
    }
    monkeypatch.setattr(decide, "resolve_workspace_root", lambda: Path("/tmp/workspace"))
    monkeypatch.setattr(decide, "_decision_inbox_list", lambda _root: canonical)

    rc = decide.cmd_list(Namespace())

    assert rc == 0
    assert "Review the migration plan" in capsys.readouterr().out
