"""Tests for ecos.services.integration.gateway."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _patch_gateway_scripts(tmp_path, monkeypatch):
    """Create mock scripts dir and patch gateway module-level imports."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "domain-manager.py").write_text("# mock")
    (scripts_dir / "ecos-health-check.py").write_text("# mock")

    # Patch Path.home() for the scripts dir
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    # Force reimport gateway with patched paths
    keys_to_remove = [k for k in sys.modules if "gateway" in k]
    for k in keys_to_remove:
        del sys.modules[k]

    mock_dm = MagicMock()
    mock_dm.load_registry.return_value = [
        {"id": "vault", "name": "Vault", "domain_type": "engine", "layer": "L2"},
        {
            "id": "workspace",
            "name": "Workspace",
            "domain_type": "project",
            "layer": "L3",
        },
    ]
    mock_dm.parse_bos_uri.side_effect = lambda uri, r: (
        (
            {"id": "vault", "name": "Vault", "domain_type": "engine", "layer": "L2"},
            "_state",
        )
        if "vault" in uri
        else (None, None)
    )
    mock_dm.resolve_path.side_effect = lambda d: tmp_path / "scripts" / d["id"]

    with patch(
        "importlib.machinery.SourceFileLoader.load_module", return_value=mock_dm
    ):
        import ecos.services.integration.gateway as gw

        gw.dm = mock_dm
        yield mock_dm, gw


class TestBosResolve:
    def test_valid_uri(self, tmp_path, _patch_gateway_scripts):
        mock_dm, gw = _patch_gateway_scripts
        vault_dir = tmp_path / "scripts" / "vault"
        vault_dir.mkdir(parents=True, exist_ok=True)
        result = gw.bos_resolve("bos://vault/_state")
        assert result["domain"] == "Vault"
        assert result["type"] == "engine"

    def test_invalid_uri(self, _patch_gateway_scripts):
        mock_dm, gw = _patch_gateway_scripts
        result = gw.bos_resolve("bos://nonexistent")
        assert "error" in result


class TestBosDomains:
    def test_all_domains(self, _patch_gateway_scripts):
        mock_dm, gw = _patch_gateway_scripts
        result = gw.bos_domains()
        assert result["total"] == 2

    def test_filter_by_type(self, _patch_gateway_scripts):
        mock_dm, gw = _patch_gateway_scripts
        result = gw.bos_domains(dtype="engine")
        assert result["total"] == 1


class TestHTTPHandler:
    def test_health_endpoint(self):
        from ecos.services.integration.gateway import BosHTTPHandler

        handler = BosHTTPHandler.__new__(BosHTTPHandler)
        handler._send = MagicMock()
        handler.path = "/health"
        handler.do_GET()
        handler._send.assert_called_once_with(
            {"status": "ok", "service": "ecos-gateway"}
        )

    def test_not_found(self):
        from ecos.services.integration.gateway import BosHTTPHandler

        handler = BosHTTPHandler.__new__(BosHTTPHandler)
        handler._send = MagicMock()
        handler.path = "/unknown"
        handler.do_GET()
        args = handler._send.call_args
        assert args[0][1] == 404

    def test_options(self):
        from ecos.services.integration.gateway import BosHTTPHandler

        handler = BosHTTPHandler.__new__(BosHTTPHandler)
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.do_OPTIONS()
        handler.send_response.assert_called_once_with(200)
