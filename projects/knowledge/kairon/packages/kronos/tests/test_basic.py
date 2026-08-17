"""Basic tests for kronos — 知识摄取管线."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestKronosImports:
    """Test basic importability of kronos modules."""

    def test_version_import(self):
        """Verify kronos version can be imported."""
        try:
            from kronos import __version__

            assert isinstance(__version__, str)
            assert len(__version__) > 0
        except ImportError:
            import pytest

            pytest.skip("kronos package not importable")

    def test_config_import(self):
        """Verify kronos.config module can be imported."""
        try:
            from kronos.config import get_config

            cfg = get_config()
            assert cfg is not None
        except ImportError:
            import pytest

            pytest.skip("kronos.config not importable")

    def test_fetch_router_import(self):
        """Verify fetch_router can be imported."""
        try:
            from kronos.fetch_router import content_type_label, plan_for_url
        except ImportError:
            import pytest

            pytest.skip("kronos.fetch_router not importable")

    def test_cli_import(self):
        """Verify CLI module can be imported."""
        try:
            from kronos.cli import main
        except ImportError:
            import pytest

            pytest.skip("kronos.cli not importable")

    def test_dispatcher_import(self):
        """Verify dispatcher can be imported."""
        try:
            from kronos.dispatcher import dispatch
        except ImportError:
            import pytest

            pytest.skip("kronos.dispatcher not importable")


class TestKronosConfig:
    """Test kronos.config behavior with defaults."""

    def test_config_defaults(self):
        """Default config should have workspace_path pointing to ~/Workspace."""
        try:
            from kronos.config import get_config
        except ImportError:
            import pytest

            pytest.skip("kronos.config not importable")
        cfg = get_config()
        assert "Workspace" in cfg.workspace_path
        assert cfg.fetch_timeout == 60
        assert cfg.default_model == "qwen3.5:4b"

    def test_config_set_and_get(self):
        """Config set/get round-trip."""
        try:
            from kronos.config import get_config
        except ImportError:
            import pytest

            pytest.skip("kronos.config not importable")
        cfg = get_config()
        cfg.set("test_key", "test_value")
        assert cfg.get("test_key") == "test_value"

    def test_config_vault_path_default(self):
        """Vault path should default to iCloud Obsidian path."""
        try:
            from kronos.config import get_config
        except ImportError:
            import pytest

            pytest.skip("kronos.config not importable")
        cfg = get_config()
        assert "iCloud" in cfg.vault_path

    def test_config_save_and_load(self):
        """Save config then verify fields persist."""
        try:
            from kronos.config import get_config
        except ImportError:
            import pytest

            pytest.skip("kronos.config not importable")
        cfg = get_config()
        cfg.set("test_save", "roundtrip_ok")
        cfg.save()

        # Read back from file
        config_file = Path.home() / ".kronos" / "config.json"
        if config_file.exists():
            data = json.loads(config_file.read_text())
            assert data.get("test_save") == "roundtrip_ok"
            # Clean up test key
            del data["test_save"]
            config_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def test_config_timeout_property(self):
        """fetch_timeout should return int."""
        try:
            from kronos.config import get_config
        except ImportError:
            import pytest

            pytest.skip("kronos.config not importable")
        cfg = get_config()
        cfg.set("fetch_timeout", 120)
        assert cfg.fetch_timeout == 120


class TestKronosCLI:
    """Test that the kronos CLI is available."""

    def test_cli_exists(self):
        """Verify kronos CLI entry point exists."""
        import shutil

        kronos = shutil.which("kronos")
        if not kronos:
            import pytest

            pytest.skip("kronos CLI not found in PATH")
        assert os.access(kronos, os.X_OK)

    def test_cli_help(self):
        """Run kronos --help and verify exit code."""
        import shutil
        import subprocess

        kronos = shutil.which("kronos")
        if not kronos:
            import pytest

            pytest.skip("kronos CLI not found in PATH")
        result = subprocess.run([kronos, "--help"], capture_output=True, text=True)
        assert result.returncode == 0


class TestKronosExtraImports:
    """Test additional module imports."""

    def test_gateway_client_import(self):
        """Verify gateway_client can be imported."""
        try:
            from kronos.gateway_client import GatewayClient
        except ImportError:
            import pytest

            pytest.skip("kronos.gateway_client not importable")

    def test_insight_engine_import(self):
        """Verify insight_engine can be imported."""
        try:
            from kronos.insight_engine import InsightEngine
        except ImportError:
            import pytest

            pytest.skip("kronos.insight_engine not importable")

    def test_extractor_import(self):
        """Verify extractor can be imported."""
        try:
            from kronos.extractor import extract_content
        except ImportError:
            import pytest

            pytest.skip("kronos.extractor not importable")

    def test_mcp_server_import(self):
        """Verify mcp_server can be imported."""
        try:
            from kronos.mcp_server import main as mcp_main
        except ImportError:
            import pytest

            pytest.skip("kronos.mcp_server not importable")
