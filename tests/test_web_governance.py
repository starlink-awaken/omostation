"""Tests for web/governance.py — governance data providers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import web.governance as gov


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear governance cache before each test."""
    gov._cache.clear()
    yield
    gov._cache.clear()


class TestLoadYaml:
    def test_nonexistent_file(self):
        assert gov._load_yaml(Path("/nonexistent/file.yaml")) == {}

    def test_valid_yaml(self, tmp_path):
        f = tmp_path / "test.yaml"
        f.write_text("key: value\nnum: 42")
        result = gov._load_yaml(f)
        assert result["key"] == "value"
        assert result["num"] == 42

    def test_invalid_yaml(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text("{{invalid")
        assert gov._load_yaml(f) == {}


class TestCache:
    def test_cache_hit(self):
        gov._cache.clear()
        call_count = 0

        def loader():
            nonlocal call_count
            call_count += 1
            return {"count": call_count}

        gov._cached("test", loader, ttl=60)
        gov._cached("test", loader, ttl=60)
        assert call_count == 1

    def test_cache_miss_after_ttl(self):
        gov._cache.clear()
        call_count = 0

        def loader():
            nonlocal call_count
            call_count += 1
            return {"count": call_count}

        gov._cached("test2", loader, ttl=0)
        gov._cached("test2", loader, ttl=0)
        assert call_count == 2

    def test_different_keys(self):
        gov._cache.clear()
        a = gov._cached("key_a", lambda: {"a": 1}, ttl=60)
        b = gov._cached("key_b", lambda: {"b": 2}, ttl=60)
        assert a != b


class TestLoadOmoStatus:
    def test_with_data(self, tmp_path):
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "system.yaml").write_text("current_phase: 42\nhealth_score: 95")
        (state_dir / "system_health.yaml").write_text("services:\n  agora:\n    health_check: healthy")
        debt_dir = tmp_path / "debt" / "dashboard"
        debt_dir.mkdir(parents=True)
        (debt_dir / "current.yaml").write_text("total_items: 10\nopen_items: 3")

        with patch.object(gov, "OMO_DIR", tmp_path):
            gov._cache.clear()
            result = gov.load_omo_status()

        assert result["phase"] == 42
        assert result["health_score"] == 95
        assert result["debt"]["total"] == 10
        assert result["debt"]["open"] == 3

    def test_without_data(self, tmp_path):
        with patch.object(gov, "OMO_DIR", tmp_path):
            gov._cache.clear()
            result = gov.load_omo_status()

        assert result["phase"] == "?"


class TestLoadDebtData:
    def test_with_data(self, tmp_path):
        debt_dir = tmp_path / "debt" / "dashboard"
        debt_dir.mkdir(parents=True)
        (debt_dir / "current.yaml").write_text("total_items: 5")

        with patch.object(gov, "OMO_DIR", tmp_path):
            result = gov.load_debt_data()

        assert result.get("total_items") == 5

    def test_without_data(self, tmp_path):
        with patch.object(gov, "OMO_DIR", tmp_path):
            result = gov.load_debt_data()

        assert result == {}


class TestLoadEcosStatus:
    def test_with_m0_snapshot(self, tmp_path):
        m0_dir = tmp_path / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m0"
        m0_dir.mkdir(parents=True)
        (m0_dir / "snapshot.yaml").write_text("nodes:\n  - id: n1\n  - id: n2")

        with patch("web.governance.Path.home", return_value=tmp_path):
            result = gov.load_ecos_status()

        assert result["node_count"] == 2

    def test_without_snapshot(self, tmp_path):
        with patch("web.governance.Path.home", return_value=tmp_path):
            result = gov.load_ecos_status()

        assert result["node_count"] == 0


class TestLoadOmoReport:
    def test_with_data(self, tmp_path):
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "system.yaml").write_text("current_phase: 42\nhealth_score: 95\nupdated: 2026-06-16")

        with patch.object(gov, "OMO_DIR", tmp_path):
            result = gov.load_omo_report()

        assert result["phase"] == 42


class TestLoadE2eStatus:
    def test_returns_stub(self):
        result = gov.load_e2e_status()
        assert result["status"] == "not_run"


class TestLoadHealingStatus:
    def test_unavailable(self):
        result = gov.load_healing_status()
        assert "status" in result


class TestLoadHealingFixes:
    def test_returns_list(self):
        result = gov.load_healing_fixes()
        assert isinstance(result, list)


class TestLoadHealingTrends:
    def test_returns_dict(self):
        result = gov.load_healing_trends()
        assert isinstance(result, dict)


class TestLoadEcosSsbStats:
    def test_no_db(self, tmp_path):
        with patch("web.governance.Path.home", return_value=tmp_path):
            result = gov.load_ecos_ssb_stats()

        assert result["total"] == 0

    def test_with_db(self, tmp_path):
        import sqlite3

        kos_dir = tmp_path / "Workspace" / "data" / "kos"
        kos_dir.mkdir(parents=True)
        db_path = kos_dir / "ssb.db"
        db = sqlite3.connect(str(db_path))
        db.execute("CREATE TABLE ssb_events (seq INTEGER, event_type TEXT, source_agent TEXT, summary TEXT, timestamp TEXT, agent_signature TEXT)")
        db.execute("INSERT INTO ssb_events VALUES (1, 'test', 'agent1', 'test event', '2026-01-01', 'sig1')")
        db.execute("INSERT INTO ssb_events VALUES (2, 'test', 'agent2', 'test event 2', '2026-01-02', '')")
        db.commit()
        db.close()

        with patch("web.governance.Path.home", return_value=tmp_path):
            result = gov.load_ecos_ssb_stats()

        assert result["total"] == 2
        assert result["signed"] == 1
        assert result["coverage_pct"] == 50.0


class TestLoadEcosWatchdog:
    def test_no_file(self, tmp_path):
        with patch("web.governance.Path.home", return_value=tmp_path):
            result = gov.load_ecos_watchdog()

        assert result["status"] == "no_data"

    def test_with_file(self, tmp_path):
        watch_dir = tmp_path / ".hermes" / "ecos-watchdog"
        watch_dir.mkdir(parents=True)
        (watch_dir / "failures.json").write_text(json.dumps({"failures": ["svc1"]}))

        with patch("web.governance.Path.home", return_value=tmp_path):
            result = gov.load_ecos_watchdog()

        assert result["failures"] == ["svc1"]


class TestLoadRuntimeStatus:
    def test_no_file(self, tmp_path):
        with patch("web.governance.Path.home", return_value=tmp_path):
            result = gov.load_runtime_status()

        assert result["status"] == "no_data"

    def test_with_file(self, tmp_path):
        runtime_dir = tmp_path / "runtime"
        runtime_dir.mkdir()
        (runtime_dir / "matrix_state.json").write_text(json.dumps({"services": ["agora"]}))

        with patch("web.governance.Path.home", return_value=tmp_path):
            result = gov.load_runtime_status()

        assert result["services"] == ["agora"]


class TestLoadMetaosStatus:
    def test_unavailable(self):
        result = gov.load_metaos_status()
        assert "status" in result


class TestLoadL4kernelStatus:
    def test_unavailable(self):
        result = gov.load_l4kernel_status()
        assert "status" in result


class TestLoadSwarmRadar:
    def test_unavailable(self):
        result = gov.load_swarm_radar()
        assert "status" in result or "node_id" in result


class TestCacheEdgeCases:
    def test_cache_different_keys(self):
        gov._cache.clear()
        a = gov._cached("key_a", lambda: {"a": 1}, ttl=60)
        b = gov._cached("key_b", lambda: {"b": 2}, ttl=60)
        assert a != b

    def test_cache_ttl_zero(self):
        gov._cache.clear()
        call_count = 0

        def loader():
            nonlocal call_count
            call_count += 1
            return {"count": call_count}

        gov._cached("ttl_test", loader, ttl=0)
        gov._cached("ttl_test", loader, ttl=0)
        assert call_count == 2
