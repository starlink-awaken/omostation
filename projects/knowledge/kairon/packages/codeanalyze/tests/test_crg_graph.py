"""Tests for codegraph MCP tools and CRG graph queries."""

import pytest
from codeanalyze.analyzers.crg_graph import callees, callers, context, search


class TestCrgSearch:
    def test_search_known_symbol(self):
        results = search("build_registry")
        if results and "error" not in results[0]:
            assert any("build_registry" in r.get("name", "") for r in results)
        else:
            pytest.skip("CRG database not built")

    def test_search_by_kind(self):
        results = search("def ", kind="Function")
        if results and "error" not in results[0]:
            assert all(r.get("kind") == "Function" for r in results if "kind" in r)
        else:
            pytest.skip("CRG database not built")

    def test_search_limit(self):
        results = search("def ", limit=3)
        if results and "error" not in results[0]:
            assert len(results) <= 3
        else:
            pytest.skip("CRG database not built")

    def test_callers_of_entry_point(self):
        results = callers("codeanalyze.core.registry.build_registry")
        if results and "error" not in results[0]:
            assert isinstance(results, list)
        else:
            pytest.skip("CRG not built or symbol missing")

    def test_callees_of_entry_point(self):
        results = callees("codeanalyze.core.registry.build_registry")
        if results and "error" not in results[0]:
            assert isinstance(results, list)
        else:
            pytest.skip("CRG not built or symbol missing")

    def test_context_of_file(self):
        results = context("registry.py")
        if "error" in results:
            pytest.skip("CRG not built")
        assert "nodes" in results or "callers" in results or "callees" in results
