"""Multica AS0 topology relations (T1..T7) over synthetic probe payloads.

Hermetic: no `multica` invocation, no network.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "bin/gac/multica-as0-verify.py"


def _load():
    spec = importlib.util.spec_from_file_location("multica_as0_verify", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["multica_as0_verify"] = module
    spec.loader.exec_module(module)
    return module


def _topology(module, **payloads):
    return {entry["id"]: entry for entry in module.build_topology(payloads)}


def _runtime(rid: str, provider: str, name: str | None = None, custom: str | None = None) -> dict:
    return {"id": rid, "provider": provider, "name": name or f"{provider} (mbp)",
            "custom_name": custom}


def test_runtime_daemon_overlap_joins_on_provider():
    module = _load()
    entries = _topology(
        module,
        daemon_status={"agents": ["claude", "codex"]},
        runtime_list=[_runtime("r1", "claude"), _runtime("r2", "codex")],
    )
    assert entries["runtime_daemon_overlap"]["ok"] is True
    assert "overlap=2" in entries["runtime_daemon_overlap"]["detail"]


def test_runtime_daemon_overlap_ignores_display_and_device_labels():
    """`name`/`custom_name` are labels, not the daemon's CLI slugs."""
    module = _load()
    entries = _topology(
        module,
        daemon_status={"agents": ["claude"]},
        runtime_list=[_runtime("r1", "claude", name="Claude (mbp)", custom="MacbookPro-M5")],
    )
    assert entries["runtime_daemon_overlap"]["ok"] is True


@pytest.mark.parametrize("daemon_agents, runtimes", [([], [_runtime("r1", "claude")]), (["claude"], [])])
def test_runtime_daemon_overlap_is_vacuous_when_either_side_is_empty(daemon_agents, runtimes):
    """Spec T5 asserts the intersection only 'when both non-empty'."""
    module = _load()
    entries = _topology(module, daemon_status={"agents": daemon_agents}, runtime_list=runtimes)
    assert entries["runtime_daemon_overlap"]["ok"] is True


def test_runtime_daemon_overlap_fails_on_real_inconsistency():
    module = _load()
    entries = _topology(
        module,
        daemon_status={"agents": ["claude"]},
        runtime_list=[_runtime("r1", "codex")],
    )
    assert entries["runtime_daemon_overlap"]["ok"] is False


def test_agent_runtime_refs_and_squad_member_refs_still_enforced():
    module = _load()
    entries = _topology(
        module,
        runtime_list=[_runtime("r1", "claude")],
        agent_list=[{"id": "a1", "runtime_id": "missing"}],
        squad_list=[{"leader_id": "ghost"}],
    )
    assert entries["agent_runtime_refs"]["ok"] is False
    assert entries["squad_member_refs"]["ok"] is False


def test_topology_reports_all_seven_relations():
    module = _load()
    entries = _topology(module)
    assert set(entries) == {
        "agent_runtime_refs", "squad_member_refs", "issue_project_refs",
        "squad_count_readable", "runtime_daemon_overlap",
        "workspace_resource_scope", "repo_list_readable",
    }
