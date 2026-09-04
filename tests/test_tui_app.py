"""Unit tests for Sovereign TUI 2.0 (BET-Y1Q4-T8-18)."""

from __future__ import annotations

import pytest

pytest.importorskip("textual")

from cockpit.surface.protocol import SurfaceDomain
from cockpit.tui.adapters import (
    AgentAdapter,
    ComputeAdapter,
    GovernanceAdapter,
    get_adapter,
)
from cockpit.tui.app import (
    ORTHOGONAL_DOMAINS,
    CockpitTUIApp,
    DomainSidebar,
    SovereignCockpitApp,
)


class TestTUIStructure:
    def test_app_export_and_alias(self) -> None:
        assert SovereignCockpitApp is not None
        assert CockpitTUIApp is SovereignCockpitApp

    def test_eight_orthogonal_domains_defined(self) -> None:
        assert len(ORTHOGONAL_DOMAINS) == 8
        keys = [k for _, k, _ in ORTHOGONAL_DOMAINS]
        expected = [
            "governance",
            "agent",
            "knowledge",
            "delivery",
            "compute",
            "observability",
            "system",
            "business",
        ]
        assert keys == expected

    def test_app_instantiation(self) -> None:
        app = SovereignCockpitApp()
        assert app.TITLE == "🛸 Sovereign Cockpit TUI 2.0"
        assert app.active_domain == "governance"

    def test_bindings_present(self) -> None:
        app = SovereignCockpitApp()
        key_bindings = {b.key for b in app.BINDINGS}
        assert "q" in key_bindings
        assert "tab" in key_bindings
        assert "grave_accent" in key_bindings
        assert "ctrl+p" in key_bindings
        for num in "12345678":
            assert num in key_bindings


class TestDomainAdapters:
    def test_governance_adapter_returns_valid_envelopes(self) -> None:
        adapter = get_adapter("governance")
        assert isinstance(adapter, GovernanceAdapter)
        summary = adapter.get_summary_card()
        assert summary.domain == SurfaceDomain.GOVERNANCE
        assert summary.card_type.value == "metric_grid"

        details = adapter.get_detail_cards()
        assert len(details) >= 1
        assert details[0].card_type.value == "data_table"

    def test_agent_adapter_fuses_swarm(self) -> None:
        adapter = get_adapter("agent")
        assert isinstance(adapter, AgentAdapter)
        summary = adapter.get_summary_card()
        assert summary.domain == SurfaceDomain.AGENT
        details = adapter.get_detail_cards()
        assert len(details) >= 1
        assert details[0].card_type.value == "dag_graph"

    def test_compute_adapter_fuses_hud(self) -> None:
        adapter = get_adapter("compute")
        assert isinstance(adapter, ComputeAdapter)
        summary = adapter.get_summary_card()
        assert summary.domain == SurfaceDomain.COMPUTE
        assert "VRAM" in summary.title or "Compute" in summary.title

    def test_generic_fallback_for_all_8_domains(self) -> None:
        for _, key, _ in ORTHOGONAL_DOMAINS:
            adapter = get_adapter(key)
            assert adapter is not None
            card = adapter.get_summary_card()
            assert card.title != ""


@pytest.mark.asyncio
async def test_headless_tui_app_lifecycle() -> None:
    """Run SovereignCockpitApp headlessly via Textual pilot."""
    app = SovereignCockpitApp()
    async with app.run_test() as pilot:
        # Check components mounted
        assert app.query_one("#domain-sidebar") is not None
        assert app.query_one("#card-deck") is not None
        assert app.query_one("#log-drawer") is not None

        # Test drawer toggle
        drawer = app.query_one("#log-drawer")
        assert "collapsed" in drawer.classes
        app.action_toggle_log_drawer()
        assert "collapsed" not in drawer.classes
        app.action_toggle_log_drawer()
        assert "collapsed" in drawer.classes

        # Test domain switching
        app.action_select_domain_2()
        assert app.active_domain == "agent"

        app.action_select_domain_5()
        assert app.active_domain == "compute"

        app.action_select_domain_1()
        assert app.active_domain == "governance"

        # Quit cleanly
        await pilot.press("q")
