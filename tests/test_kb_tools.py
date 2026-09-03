"""Tests for bin/kb/ tools (knowledge-graph, search, staleness-check)."""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

import pytest

WS = Path(__file__).resolve().parents[1]

def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, WS / rel)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


# ── knowledge-graph ──────────────────────────────────────────────────────────

class TestKnowledgeGraph:
    def test_load_module(self):
        kg = _load("_kg", "bin/kb/knowledge-graph.py")
        assert hasattr(kg, "build_graph")

    def test_scan_adrs(self, tmp_path: Path):
        kg = _load("_kg2", "bin/kb/knowledge-graph.py")
        adr_dir = tmp_path / ".omo" / "_knowledge" / "decisions"
        adr_dir.mkdir(parents=True)
        (adr_dir / "0001-test.md").write_text(
            "# ADR-0001: Test\n\nstatus: active\nUses `bin/gac/foo.py`\n"
        )
        nodes, edges = kg._scan_adrs(tmp_path)
        assert len(nodes) == 1
        assert nodes[0]["id"] == "ADR-0001"
        assert any("bin/gac/foo.py" in e["to"] for e in edges)

    def test_scan_scripts_skips_archive(self, tmp_path: Path):
        kg = _load("_kg3", "bin/kb/knowledge-graph.py")
        bin_gac = tmp_path / "bin" / "gac"
        bin_gac.mkdir(parents=True)
        (bin_gac / "active.py").write_text('"""Active tool."""\n')
        archive = tmp_path / "bin" / "_archive"
        archive.mkdir(parents=True)
        (archive / "old.py").write_text("pass\n")
        nodes, _ = kg._scan_scripts(tmp_path)
        names = [n["name"] for n in nodes]
        assert "active" in names
        assert "old" not in names

    def test_build_graph_summary(self, tmp_path: Path):
        kg = _load("_kg4", "bin/kb/knowledge-graph.py")
        # Create minimal structure
        adr = tmp_path / ".omo" / "_knowledge" / "decisions"
        adr.mkdir(parents=True)
        (adr / "0001-t.md").write_text("# T\nstatus: active\n")
        ops = tmp_path / "docs" / "operations"
        ops.mkdir(parents=True)
        (ops / "runbook-test.md").write_text("# Runbook Test\nUse `bin/gac/x.py`\n")
        graph = kg.build_graph(tmp_path)
        assert graph["summary"]["total_nodes"] >= 2
        assert "adr" in graph["summary"]["by_type"]
        assert "runbook" in graph["summary"]["by_type"]


# ── search ────────────────────────────────────────────────────────────────────

class TestSearch:
    def _make_graph(self, tmp_path: Path) -> Path:
        g = {
            "nodes": [
                {"type": "adr", "id": "ADR-001", "path": "a.md", "title": "Concurrent write handling"},
                {"type": "script", "id": "script:bin/gac/drift-sweep.py", "path": "bin/gac/drift-sweep.py", "name": "drift-sweep", "docstring": "Weekly anti-corruption sweep"},
                {"type": "runbook", "id": "runbook:ci-red", "path": "docs/operations/runbook-ci-red.md", "title": "CI red runbook"},
            ],
            "edges": [
                {"from": "adr:ADR-001", "to": "script:bin/gac/drift-sweep.py", "relation": "references"},
            ],
        }
        p = tmp_path / "graph.json"
        p.write_text(json.dumps(g), encoding="utf-8")
        return p

    def test_keyword_search(self, tmp_path: Path):
        s = _load("_s1", "bin/kb/search.py")
        graph = s._load_graph(self._make_graph(tmp_path))
        results = s._keyword_search(graph, "drift")
        assert len(results) == 1
        assert results[0]["id"] == "script:bin/gac/drift-sweep.py"

    def test_keyword_search_title_match(self, tmp_path: Path):
        s = _load("_s2", "bin/kb/search.py")
        graph = s._load_graph(self._make_graph(tmp_path))
        results = s._keyword_search(graph, "concurrent")
        assert len(results) == 1
        assert results[0]["type"] == "adr"

    def test_type_filter(self, tmp_path: Path):
        s = _load("_s3", "bin/kb/search.py")
        graph = s._load_graph(self._make_graph(tmp_path))
        results = s._keyword_search(graph, "drift", node_type="script")
        assert len(results) == 1
        results = s._keyword_search(graph, "drift", node_type="adr")
        assert len(results) == 0

    def test_ref_search(self, tmp_path: Path):
        s = _load("_s4", "bin/kb/search.py")
        graph = s._load_graph(self._make_graph(tmp_path))
        results = s._ref_search(graph, "bin/gac/drift-sweep.py")
        assert len(results) == 1
        assert results[0]["node"]["type"] == "adr"


# ── staleness-check ───────────────────────────────────────────────────────────

class TestStaleness:
    def test_check_fresh_file(self, tmp_path: Path):
        st = _load("_st1", "bin/kb/staleness-check.py")
        f = tmp_path / "fresh.md"
        f.write_text("last-reviewed: 2026-08-24\n# Fresh\n")
        r = st.check_file(tmp_path, f)
        assert r["issue_count"] == 0

    def test_check_stale_mtime(self, tmp_path: Path):
        import os
        st = _load("_st2", "bin/kb/staleness-check.py")
        f = tmp_path / "stale.md"
        f.write_text("last-reviewed: 2026-08-24\n# Stale\n")
        old_ts = time.time() - 200 * 86400  # 200 days ago
        os.utime(f, (old_ts, old_ts))
        r = st.check_file(tmp_path, f)
        assert r["issue_count"] > 0
        assert any("mtime" in i for i in r["issues"])

    def test_check_missing_last_reviewed(self, tmp_path: Path):
        st = _load("_st3", "bin/kb/staleness-check.py")
        f = tmp_path / "no-lr.md"
        f.write_text("# No last-reviewed\n")
        r = st.check_file(tmp_path, f)
        assert any("missing last-reviewed" in i for i in r["issues"])

    def test_check_broken_bin_ref(self, tmp_path: Path):
        st = _load("_st4", "bin/kb/staleness-check.py")
        f = tmp_path / "bad-ref.md"
        f.write_text("last-reviewed: 2026-08-24\nUse `bin/nonexistent/tool.py`\n")
        r = st.check_file(tmp_path, f)
        assert any("broken ref" in i for i in r["issues"])
