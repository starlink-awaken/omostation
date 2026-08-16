"""Knowledge E2E tests — test kos and ontoderive integration."""

import pytest


class TestKosSearch:
    """Test kos search types."""

    def test_kos_search_function(self):
        """Verify kos.search function is importable and callable."""
        from kos import search

        result = search("test")
        assert isinstance(result, list)


class TestOntoderive:
    """Test ontoderive type compatibility."""

    def test_import(self):
        """ontoderive has workspace-specific package layout; skip if unavailable."""
        try:
            import ontoderive  # noqa: F401
        except ImportError:
            pytest.skip("ontoderive not in PYTHONPATH (workspace-scoped package)")
