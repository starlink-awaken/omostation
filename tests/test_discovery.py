"""Tests for DiscoveryEngine."""

from agora.core.discovery import DiscoveredService, DiscoveryEngine
from pathlib import Path


class TestDiscoveryEngine:
    def test_find_workspace(self):
        engine = DiscoveryEngine()
        root = engine._find_workspace()
        root_path = Path(root)
        assert (root_path / "projects" / "agora").is_dir()
        assert (root_path / "projects" / "kairon").is_dir()

    def test_scan_known_projects(self):
        engine = DiscoveryEngine()
        services = engine.scan_known_projects()
        names = {s.name for s in services}
        assert "agora" in names  # always finds itself
        assert all(isinstance(s, DiscoveredService) for s in services)

    def test_discover_all_dedup(self):
        engine = DiscoveryEngine()
        services = engine.discover_all()
        names = [s.name for s in services]
        assert len(names) == len(set(names))  # no duplicates

    def test_discovered_service_fields(self):
        s = DiscoveredService(
            name="test",
            description="desc",
            mcp_endpoint="stdio://test",
            health_endpoint="http://localhost:8000/health",
            port=8000,
            tags=["a", "b"],
            source="test",
            confidence=0.95,
        )
        assert s.name == "test"
        assert s.confidence == 0.95
        assert len(s.tags) == 2
