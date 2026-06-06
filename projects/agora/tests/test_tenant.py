"""Tests for multi-tenant access control."""

import tempfile
from pathlib import Path

from agora.auth.tenant import Tenant, TenantManager


def test_tenant_dataclass():
    t = Tenant(name="test", token="sk-test", services=["minerva"], rate_limit=50)  # noqa: S106
    assert t.name == "test"
    assert t.token == "sk-test"  # noqa: S105
    assert t.services == ["minerva"]
    assert t.rate_limit == 50


class TestTenantManager:
    def _make_config(self, content: str) -> str:
        """Create a temp config file and return its path."""
        td = tempfile.mkdtemp()
        config = Path(td) / "tenants.yaml"
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(content)
        return str(config)

    def test_authenticate_valid(self):
        path = self._make_config(
            "tenants:\n  - name: test\n    token: sk-valid\n    services: [minerva]\n    rate_limit: 10\n"
        )
        tm = TenantManager(path)
        tenant = tm.authenticate("sk-valid")
        assert tenant is not None
        assert tenant.name == "test"
        assert tenant.token == "sk-valid"  # noqa: S105

    def test_authenticate_invalid(self):
        path = self._make_config(
            "tenants:\n  - name: test\n    token: sk-valid\n    services: []\n    rate_limit: 10\n"
        )
        tm = TenantManager(path)
        assert tm.authenticate("sk-wrong") is None

    def test_check_rate_limit_allowed(self):
        path = self._make_config(
            "tenants:\n  - name: test\n    token: sk-test\n    services: []\n    rate_limit: 100\n"
        )
        tm = TenantManager(path)
        assert tm.check_rate_limit("test") is True

    def test_check_rate_limit_unknown(self):
        path = self._make_config(
            "tenants:\n  - name: test\n    token: sk-test\n    services: []\n    rate_limit: 100\n"
        )
        tm = TenantManager(path)
        assert tm.check_rate_limit("nonexistent") is False

    def test_add_and_remove_tenant(self):
        path = self._make_config("tenants:\n  - name: test\n    token: sk-test\n    services: []\n    rate_limit: 10\n")
        tm = TenantManager(path)
        token = tm.add_tenant("new-team", services=["minerva"])
        assert token.startswith("sk-")
        tenant = tm.authenticate(token)
        assert tenant is not None
        assert tenant.name == "new-team"
        assert tm.remove_tenant("new-team") is True
        assert tm.remove_tenant("nonexistent") is False

    def test_has_service_access(self):
        path = self._make_config(
            "tenants:\n  - name: test\n    token: sk-test\n    services: [minerva]\n    rate_limit: 10\n"
        )
        tm = TenantManager(path)
        assert tm.has_service_access("test", "minerva") is True
        assert tm.has_service_access("test", "sophia") is False
        # Empty services = all access
        tm.add_tenant("admin")
        assert tm.has_service_access("admin", "anything") is True
        # Unknown tenant
        assert tm.has_service_access("ghost", "minerva") is False

    def test_list_tenants_no_token_exposure(self):
        path = self._make_config(
            "tenants:\n  - name: test\n    token: sk-secret\n    services: [minerva]\n    rate_limit: 10\n"
        )
        tm = TenantManager(path)
        tenants = tm.list_tenants()
        assert len(tenants) == 1
        assert tenants[0]["name"] == "test"
        assert "token" not in tenants[0]

    def test_default_config_auto_created(self):
        with tempfile.TemporaryDirectory() as td:
            config = Path(td) / "tenants.yaml"
            assert not config.exists()
            tm = TenantManager(str(config))
            assert config.exists()
            # Default tenant is created
            tenants = tm.list_tenants()
            assert len(tenants) == 1
            assert tenants[0]["name"] == "default"

    def test_remove_tenant_updates_token_map(self):
        path = self._make_config("tenants:\n  - name: test\n    token: sk-test\n    services: []\n    rate_limit: 10\n")
        tm = TenantManager(path)
        token = tm.add_tenant("temp")
        assert tm.authenticate(token) is not None
        tm.remove_tenant("temp")
        assert tm.authenticate(token) is None
