"""agent-onboard includes Memory OS cold-start phase."""

from __future__ import annotations

from cockpit.commands.agent_onboard import _check_memory_os_surfaces


def test_memory_os_surface_checks_populate_results():
    results: dict[str, bool] = {}
    _check_memory_os_surfaces(results)
    assert "skill_memory-recall" in results
    assert "memory_os_ssot" in results
    assert "memory_os_light_gate" in results
    assert "memory_cli_entry" in results
    # In full workspace checkout these should pass; if sparse, still keys present
    assert isinstance(results["skill_memory-recall"], bool)
