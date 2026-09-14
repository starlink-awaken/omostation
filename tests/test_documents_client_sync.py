"""Tests for bin/gac/documents-client-sync.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

# Ensure the bin/gac directory is importable and import the hyphenated module
_worktree_root = Path(__file__).resolve().parents[1]  # tests/ → worktree root
_bin_gac = _worktree_root / "bin" / "gac"
sys.path.insert(0, str(_bin_gac))
import importlib
spec = importlib.util.spec_from_file_location(
    "documents_client_sync",
    str(_bin_gac / "documents-client-sync.py"),
)
documents_client_sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(documents_client_sync)


@pytest.fixture()
def fake_registry(tmp_path: Path) -> Path:
    """Create a minimal documents-domain-projects.yaml for testing."""
    registry = {
        "apiVersion": "workspace.omostation/v1",
        "kind": "DocumentsDomainProjects",
        "id": "documents-domain-projects",
        "status": "active",
        "owner": "cockpit",
        "clients": {
            "claude": {
                "config_contract": {
                    "config_path": "~/Library/Application Support/Claude/claude_desktop_config.json",
                    "managed_mcp_server": "cockpit",
                }
            }
        },
        "domains": [
            {"id": "shared", "profile": "content-domain"},
            {"id": "personal", "profile": "content-domain"},
        ],
        "runtime_jobs": [
            {"id": "test-job", "domain_id": "shared", "schedule": "manual"}
        ],
    }
    path = tmp_path / "documents-domain-projects.yaml"
    with open(path, "w") as fh:
        yaml.dump(registry, fh)
    return path


@pytest.fixture()
def claude_config_ok(tmp_path: Path) -> Path:
    """Create a valid Claude Desktop config with managed MCP server."""
    config_dir = tmp_path / "claude_config"
    config_dir.mkdir()
    config = {
        "mcpServers": {
            "cockpit": {"command": "cockpit", "args": ["mcp"], "transport": "stdio"}
        }
    }
    path = config_dir / "claude_desktop_config.json"
    with open(path, "w") as fh:
        json.dump(config, fh)
    return path


@pytest.fixture()
def claude_config_drift(tmp_path: Path) -> Path:
    """Create a Claude Desktop config with drift (missing cockpit server)."""
    config_dir = tmp_path / "claude_config_drift"
    config_dir.mkdir()
    config = {"mcpServers": {"other-server": {"command": "other"}}}
    path = config_dir / "claude_desktop_config.json"
    with open(path, "w") as fh:
        json.dump(config, fh)
    return path


class TestDocumentsClientSyncCheck:
    """Tests for the check mode."""

    def test_check_no_drift(
        self,
        fake_registry: Path,
        claude_config_ok: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When cockpit MCP server is present and correct, check returns ok."""
        sync = documents_client_sync
        monkeypatch.setattr(sync, "_REGISTRY_PATH", fake_registry)
        monkeypatch.setattr(sync, "_CLAUDE_DESKTOP_CONFIG", claude_config_ok)
        # Mark others as non-existent
        monkeypatch.setattr(sync, "_CODEX_CONFIG", fake_registry / "nonexistent")
        monkeypatch.setattr(sync, "_ZED_CONFIG", fake_registry / "nonexistent")
        monkeypatch.setattr(sync, "_ZCODE_CONFIG", fake_registry / "nonexistent")

        registry = sync._load_registry()
        results = [checker(registry) for checker in sync._CHECKERS]
        has_drift = any(r["status"] == "drift" for r in results)
        assert not has_drift

    def test_check_drift_detected(
        self,
        fake_registry: Path,
        claude_config_drift: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When cockpit MCP server is missing, check returns drift."""
        sync = documents_client_sync

        monkeypatch.setattr(sync, "_REGISTRY_PATH", fake_registry)
        monkeypatch.setattr(sync, "_CLAUDE_DESKTOP_CONFIG", claude_config_drift)
        monkeypatch.setattr(sync, "_CODEX_CONFIG", fake_registry / "nonexistent")
        monkeypatch.setattr(sync, "_ZED_CONFIG", fake_registry / "nonexistent")
        monkeypatch.setattr(sync, "_ZCODE_CONFIG", fake_registry / "nonexistent")

        registry = sync._load_registry()
        results = [checker(registry) for checker in sync._CHECKERS]
        drift_results = [r for r in results if r["status"] == "drift"]
        assert len(drift_results) == 1
        assert drift_results[0]["client"] == "claude_desktop"

    def test_check_missing_config(
        self,
        fake_registry: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When config file doesn't exist, status is 'missing' (no drift)."""
        sync = documents_client_sync

        monkeypatch.setattr(sync, "_REGISTRY_PATH", fake_registry)
        monkeypatch.setattr(sync, "_CLAUDE_DESKTOP_CONFIG", fake_registry / "nonexistent")
        monkeypatch.setattr(sync, "_CODEX_CONFIG", fake_registry / "nonexistent")
        monkeypatch.setattr(sync, "_ZED_CONFIG", fake_registry / "nonexistent")
        monkeypatch.setattr(sync, "_ZCODE_CONFIG", fake_registry / "nonexistent")

        registry = sync._load_registry()
        results = [checker(registry) for checker in sync._CHECKERS]
        # All should be missing, not drift
        for r in results:
            assert r["status"] == "missing"

    def test_check_json_output(
        self,
        fake_registry: Path,
        claude_config_ok: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Check mode with --json outputs valid JSON."""
        sync = documents_client_sync

        monkeypatch.setattr(sync, "_REGISTRY_PATH", fake_registry)
        monkeypatch.setattr(sync, "_CLAUDE_DESKTOP_CONFIG", claude_config_ok)
        monkeypatch.setattr(sync, "_CODEX_CONFIG", fake_registry / "nonexistent")
        monkeypatch.setattr(sync, "_ZED_CONFIG", fake_registry / "nonexistent")
        monkeypatch.setattr(sync, "_ZCODE_CONFIG", fake_registry / "nonexistent")

        exit_code = sync.main(["check", "--json", "--registry", str(fake_registry)])
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "ok" in output
        assert "details" in output


class TestDocumentsClientSyncApply:
    """Tests for the apply mode."""

    def test_apply_repair_drift(
        self,
        fake_registry: Path,
        claude_config_drift: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Apply mode repairs drift and creates backup."""
        sync = documents_client_sync
        # Use tmp subdirs for missing configs so mkdir(parents=True) works
        _nxd = tmp_path / "missing_configs"
        monkeypatch.setattr(sync, "_REGISTRY_PATH", fake_registry)
        monkeypatch.setattr(sync, "_CLAUDE_DESKTOP_CONFIG", claude_config_drift)
        monkeypatch.setattr(sync, "_CODEX_CONFIG", _nxd / "codex.json")
        monkeypatch.setattr(sync, "_ZED_CONFIG", _nxd / "zed.json")
        monkeypatch.setattr(sync, "_ZCODE_CONFIG", _nxd / "zcode.json")

        exit_code = sync.main(["apply", "--registry", str(fake_registry)])
        assert exit_code == 0

        # Verify backup was created
        backup = claude_config_drift.with_suffix(claude_config_drift.suffix + ".bak")
        assert backup.exists()

        # Verify the config was repaired
        with open(claude_config_drift) as fh:
            repaired = json.load(fh)
        assert "cockpit" in repaired.get("mcpServers", {})

    def test_apply_idempotent(
        self,
        fake_registry: Path,
        claude_config_ok: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Apply mode on an already-correct config is idempotent."""
        sync = documents_client_sync
        _nxd = tmp_path / "missing_configs"
        monkeypatch.setattr(sync, "_REGISTRY_PATH", fake_registry)
        monkeypatch.setattr(sync, "_CLAUDE_DESKTOP_CONFIG", claude_config_ok)
        monkeypatch.setattr(sync, "_CODEX_CONFIG", _nxd / "codex.json")
        monkeypatch.setattr(sync, "_ZED_CONFIG", _nxd / "zed.json")
        monkeypatch.setattr(sync, "_ZCODE_CONFIG", _nxd / "zcode.json")

        exit_code = sync.main(["apply", "--registry", str(fake_registry)])
        assert exit_code == 0

        # Config should be unchanged
        with open(claude_config_ok) as fh:
            config = json.load(fh)
        assert config["mcpServers"]["cockpit"]["command"] == "cockpit"


class TestDocumentsClientSyncIntegration:
    """Integration tests using the main() entry point."""

    def test_main_check_returns_0_on_ok(
        self,
        fake_registry: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """main('check') returns exit 0 when no drift."""
        sync = documents_client_sync

        monkeypatch.setattr(sync, "_CLAUDE_DESKTOP_CONFIG", fake_registry / "nonexistent")
        monkeypatch.setattr(sync, "_CODEX_CONFIG", fake_registry / "nonexistent")
        monkeypatch.setattr(sync, "_ZED_CONFIG", fake_registry / "nonexistent")
        monkeypatch.setattr(sync, "_ZCODE_CONFIG", fake_registry / "nonexistent")

        exit_code = sync.main(["check", "--registry", str(fake_registry)])
        assert exit_code == 0

    def test_main_check_returns_2_on_drift(
        self,
        fake_registry: Path,
        claude_config_drift: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """main('check') returns exit 2 when drift detected."""
        sync = documents_client_sync

        monkeypatch.setattr(sync, "_REGISTRY_PATH", fake_registry)
        monkeypatch.setattr(sync, "_CLAUDE_DESKTOP_CONFIG", claude_config_drift)
        monkeypatch.setattr(sync, "_CODEX_CONFIG", fake_registry / "nonexistent")
        monkeypatch.setattr(sync, "_ZED_CONFIG", fake_registry / "nonexistent")
        monkeypatch.setattr(sync, "_ZCODE_CONFIG", fake_registry / "nonexistent")

        exit_code = sync.main(["check", "--registry", str(fake_registry)])
        assert exit_code == 2
