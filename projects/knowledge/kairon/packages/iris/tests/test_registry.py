"""Tests for connector registry."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import tomllib
from pathlib import Path

import pytest
from iris.base import BaseConnector
from iris.registry import ConnectorRegistry


class MockConnector(BaseConnector):
    name = "mock"
    display_name = "Mock Platform"

    def is_available(self):
        return True

    def list_items(self, limit=20, cursor=None):  # type: ignore[reportIncompatibleMethodOverride]
        return []

    def get_item(self, id):
        return None

    def search(self, query, limit=10):
        return []

    def status(self):
        return {"mock": True}


class UnavailableConnector(BaseConnector):
    name = "unavailable"
    display_name = "Unavailable"

    def is_available(self):
        return False

    def list_items(self, limit=20, cursor=None):  # type: ignore[reportIncompatibleMethodOverride]
        return []

    def get_item(self, id):
        return None

    def search(self, query, limit=10):
        return []

    def status(self):
        return {"available": False}


class TestRegistry:
    def test_register_and_get(self):
        registry = ConnectorRegistry()
        conn = MockConnector()
        registry.register(conn)
        assert registry.get("mock") is conn

    def test_register_empty_name_raises(self):
        registry = ConnectorRegistry()
        conn = MockConnector()
        conn.name = ""
        with pytest.raises(ValueError):
            registry.register(conn)

    def test_list(self):
        registry = ConnectorRegistry()
        registry.register(MockConnector())
        registry.register(UnavailableConnector())
        assert len(registry.list_all()) == 2

    def test_list_names(self):
        registry = ConnectorRegistry()
        registry.register(MockConnector())
        assert registry.list_names() == ["mock"]

    def test_unregister(self):
        registry = ConnectorRegistry()
        conn = MockConnector()
        registry.register(conn)
        registry.unregister("mock")
        assert registry.get("mock") is None

    def test_contains(self):
        registry = ConnectorRegistry()
        registry.register(MockConnector())
        assert "mock" in registry
        assert "nope" not in registry

    def test_status_all(self):
        registry = ConnectorRegistry()
        registry.register(MockConnector())
        registry.register(UnavailableConnector())
        statuses = registry.status_all()
        assert len(statuses) == 2
        status_map = {s["name"]: s for s in statuses}
        assert status_map["mock"]["available"] is True
        assert status_map["unavailable"]["available"] is False

    def test_len(self):
        registry = ConnectorRegistry()
        assert len(registry) == 0
        registry.register(MockConnector())
        assert len(registry) == 1

    def test_external_descriptor_is_credential_free(self):
        descriptor = MockConnector().external_descriptor()
        assert descriptor["id"] == "iris:mock"
        assert descriptor["kind"] == "knowledge_source"
        assert descriptor["lifecycle"] == "active"
        assert descriptor["health"]["available"] is True
        assert "access_token" not in descriptor
        assert "password" not in descriptor

    def test_iris_package_declares_connector_entry_points(self):
        package_root = Path(__file__).resolve().parents[1]
        with (package_root / "pyproject.toml").open("rb") as stream:
            project = tomllib.load(stream)

        entry_points = project["project"]["entry-points"]["iris.connectors"]
        assert set(entry_points) == {
            "local_files",
            "obsidian",
            "openhuman",
            "wpsnote",
            "notebooklm",
            "zhihu",
            "wxread",
            "telegram",
            "wechat",
            "pocket",
            "polar",
            "applenotes",
            "github",
            "dingtalk",
            "feishu",
            # T2-01 感知面扩展 (BET-Y1Q3-T2-01/T2-03): 双邮件源+企微OA+CUA+通用私有
            "apple_mail",
            "netease_mailmaster",
            "seeyon_oa",
            "cua_browser",
            "universal_private",
        }

    def test_iris_connectors_are_external_resource_providers(self):
        package_root = Path(__file__).resolve().parents[1]
        with (package_root / "pyproject.toml").open("rb") as stream:
            project = tomllib.load(stream)

        external_entries = project["project"]["entry-points"]["external.resources"]
        iris_entries = project["project"]["entry-points"]["iris.connectors"]
        assert external_entries == iris_entries
