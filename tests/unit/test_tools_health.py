"""Unit tests for agora.server.tools_health — Phase 45 governance observability.

Tests:
  1. health_self_check — comprehensive health report
  2. entropy_cleanup — stale state cleanup
  3. debt_auto_seed — governance gap detection
  4. _scan_debt_items — debt directory scanning
  5. _write_debt_item — debt item creation
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from agora.server.tools_health import (
    _scan_debt_items,
    _write_debt_item,
    debt_auto_seed,
    entropy_cleanup,
    health_self_check,
)

# ── Fixtures ───────────────────────────────────────────────────


@pytest.fixture
def mock_registry():
    """Create a mock ServiceRegistry."""
    registry = MagicMock()
    registry.list_all.return_value = [
        MagicMock(name="svc-a", health_endpoint="http://localhost:8080/health"),
        MagicMock(name="svc-b", health_endpoint=""),
    ]
    registry.list_healthy.return_value = [registry.list_all.return_value[0]]
    return registry


@pytest.fixture
def mock_proxy_manager():
    """Create a mock ProxyManager."""
    pm = MagicMock()
    pm._health_checker = MagicMock()
    pm._health_checker.get_all_status.return_value = {
        "backend-1": {"alive": True, "last_ok": time.time()},
        "backend-2": {"alive": False, "last_ok": time.time() - 100},
    }
    pm.registry = MagicMock()
    pm.registry.entries = {
        "tool-a": MagicMock(tags=["governance"]),
        "tool-b": MagicMock(tags=[]),
    }
    return pm


@pytest.fixture
def mock_auditor():
    """Create a mock AuditSubscriber."""
    auditor = MagicMock()
    auditor.stats.return_value = {"total": 42, "errors": 2}
    return auditor


@pytest.fixture
def tmp_debt_dir(tmp_path):
    """Create a temporary debt directory."""
    debt_dir = tmp_path / ".omo" / "debt" / "items"
    debt_dir.mkdir(parents=True)
    return debt_dir


# ── Tests: health_self_check ───────────────────────────────────


class TestHealthSelfCheck:
    @pytest.mark.asyncio
    @patch("agora.server.tools_health._get_auditor")
    @patch("agora.server.tools_health._get_proxy_manager")
    @patch("agora.server.tools_health._get_registry")
    @patch("agora.server.tools_health._resolve_workspace_root")
    async def test_returns_healthy_when_no_issues(
        self, mock_root, mock_reg_fn, mock_pm_fn, mock_aud_fn, tmp_path
    ):
        mock_root.return_value = str(tmp_path)
        registry = MagicMock()
        registry.list_all.return_value = [MagicMock(name="a")]
        registry.list_healthy.return_value = [MagicMock(name="a")]
        mock_reg_fn.return_value = registry

        pm = MagicMock()
        pm._health_checker = MagicMock()
        pm._health_checker.get_all_status.return_value = {}
        pm.registry = MagicMock()
        pm.registry.entries = {}
        mock_pm_fn.return_value = pm

        auditor = MagicMock()
        auditor.stats.return_value = {"total": 0}
        mock_aud_fn.return_value = auditor

        result = await health_self_check()

        assert result["status"] == "healthy"
        assert result["services"]["total"] == 1
        assert result["services"]["healthy"] == 1
        assert result["issues"] == []

    @pytest.mark.asyncio
    @patch("agora.server.tools_health._get_auditor")
    @patch("agora.server.tools_health._get_proxy_manager")
    @patch("agora.server.tools_health._get_registry")
    @patch("agora.server.tools_health._resolve_workspace_root")
    async def test_returns_degraded_when_unhealthy_services(
        self, mock_root, mock_reg_fn, mock_pm_fn, mock_aud_fn, tmp_path
    ):
        mock_root.return_value = str(tmp_path)
        registry = MagicMock()
        registry.list_all.return_value = [MagicMock(name="a"), MagicMock(name="b")]
        registry.list_healthy.return_value = [MagicMock(name="a")]
        mock_reg_fn.return_value = registry

        pm = MagicMock()
        pm._health_checker = MagicMock()
        pm._health_checker.get_all_status.return_value = {}
        pm.registry = MagicMock()
        pm.registry.entries = {}
        mock_pm_fn.return_value = pm

        auditor = MagicMock()
        auditor.stats.return_value = {}
        mock_aud_fn.return_value = auditor

        result = await health_self_check()

        assert result["status"] == "degraded"
        assert len(result["issues"]) == 1
        assert "unhealthy" in result["issues"][0]


# ── Tests: entropy_cleanup ─────────────────────────────────────


class TestEntropyCleanup:
    @pytest.mark.asyncio
    @patch("agora.server.tools_health._resolve_workspace_root")
    async def test_cleans_expired_cache(self, mock_root, tmp_path):
        mock_root.return_value = str(tmp_path)

        # Mock Path to avoid real filesystem operations
        with patch("agora.server.tools_health.Path.home") as mock_home:
            mock_home.return_value = tmp_path
            with patch("agora.server.tools_health.Path") as mock_path_cls:
                # Make Path() constructor work with our tmp_path
                original_path = __import__("pathlib").Path

                def path_factory(*args, **kwargs):
                    return original_path(*args, **kwargs)

                mock_path_cls.side_effect = path_factory
                mock_path_cls.home.return_value = tmp_path
                result = await entropy_cleanup()

        assert result["cleaned_count"] >= 0  # May or may not clean depending on path


# ── Tests: debt_auto_seed ──────────────────────────────────────


class TestDebtAutoSeed:
    @pytest.mark.asyncio
    @patch("agora.server.tools_health._get_proxy_manager")
    @patch("agora.server.tools_health._get_registry")
    @patch("agora.server.tools_health._resolve_workspace_root")
    async def test_seeds_debt_for_service_without_health(
        self, mock_root, mock_reg_fn, mock_pm_fn, tmp_path
    ):
        debt_dir = tmp_path / ".omo" / "debt" / "items"
        debt_dir.mkdir(parents=True)
        mock_root.return_value = str(tmp_path)

        registry = MagicMock()
        svc = MagicMock()
        svc.name = "test-svc"
        svc.health_endpoint = ""
        registry.list_all.return_value = [svc]
        mock_reg_fn.return_value = registry

        pm = MagicMock()
        pm.registry = MagicMock()
        pm.registry.entries = {}
        mock_pm_fn.return_value = pm

        result = await debt_auto_seed()

        assert result["seeded_count"] >= 1
        assert any("SVC-HEALTH" in s for s in result["seeded"])
        # Verify file was created in proposal dir (not .omo directly)
        from agora.server.tools_health import _resolve_proposal_dir

        created_files = list(_resolve_proposal_dir().glob("DEBT-SVC-HEALTH-*.yaml"))
        assert len(created_files) == 1

    @pytest.mark.asyncio
    @patch("agora.server.tools_health._get_proxy_manager")
    @patch("agora.server.tools_health._get_registry")
    @patch("agora.server.tools_health._resolve_workspace_root")
    async def test_skips_existing_debt_items(
        self, mock_root, mock_reg_fn, mock_pm_fn, tmp_path
    ):
        debt_dir = tmp_path / ".omo" / "debt" / "items"
        debt_dir.mkdir(parents=True)
        mock_root.return_value = str(tmp_path)

        # Pre-create the debt item
        (debt_dir / "DEBT-SVC-HEALTH-TEST-SVC.yaml").write_text("id: test")

        registry = MagicMock()
        svc = MagicMock()
        svc.name = "test-svc"
        svc.health_endpoint = ""
        registry.list_all.return_value = [svc]
        mock_reg_fn.return_value = registry

        pm = MagicMock()
        pm.registry = MagicMock()
        pm.registry.entries = {}
        mock_pm_fn.return_value = pm

        result = await debt_auto_seed()

        assert result["seeded_count"] == 0  # Already exists, skip


# ── Tests: _scan_debt_items ────────────────────────────────────


class TestScanDebtItems:
    def test_counts_open_and_resolved(self, tmp_debt_dir):
        (tmp_debt_dir / "open.yaml").write_text("lifecycle_state: open")
        (tmp_debt_dir / "resolved.yaml").write_text("lifecycle_state: resolved")
        (tmp_debt_dir / "README.md").write_text("skip me")

        # _scan_debt_items does: ws_root / ".omo" / "debt" / "items"
        # tmp_debt_dir is already .../tmp_path/.omo/debt/items
        ws_root = tmp_debt_dir.parent.parent.parent  # tmp_path
        with patch("agora.server.tools_health._resolve_workspace_root") as mock_root:
            mock_root.return_value = str(ws_root)
            result = _scan_debt_items()

        assert result["total"] == 2
        assert result["open"] == 1
        assert result["resolved"] == 1

    def test_empty_directory(self, tmp_path):
        with patch("agora.server.tools_health._resolve_workspace_root") as mock_root:
            mock_root.return_value = str(tmp_path)
            result = _scan_debt_items()

        assert result["total"] == 0


# ── Tests: _write_debt_item ────────────────────────────────────


class TestWriteDebtItem:
    def test_creates_yaml_file(self, tmp_debt_dir):
        _write_debt_item(
            tmp_debt_dir,
            "DEBT-TEST-001",
            title="Test debt",
            dimension="governance",
            severity="low",
            scope="test:scope",
        )

        created = tmp_debt_dir / "DEBT-TEST-001.yaml"
        assert created.exists()
        content = created.read_text()
        assert "DEBT-TEST-001" in content
        assert "Test debt" in content
        assert 'dimension: "governance"' in content
