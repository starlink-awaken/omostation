"""Tests for Plugin SDK."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import pytest
from kairon_plugin_sdk.context import PluginContext
from kairon_plugin_sdk.plugin import BosPlugin


class TestPluginContext:
    """Test PluginContext."""

    def test_default_context(self):
        ctx = PluginContext()
        assert ctx.environment is not None
        assert "timestamp" in ctx.environment
        assert "os" in ctx.environment
        assert ctx.workspace_path == ""
        assert ctx.metadata == {}

    def test_custom_context(self):
        ctx = PluginContext(workspace="/tmp/test", metadata={"key": "value"})
        assert ctx.workspace == "/tmp/test"
        assert ctx.metadata == {"key": "value"}


class MinimalPlugin(BosPlugin):
    """Minimal plugin implementation for testing."""

    plugin_id = "test-minimal"
    plugin_version = "1.0.0"
    plugin_name = "Test Plugin"
    plugin_description = "A test plugin"
    plugin_author = "Test Author"
    plugin_tags = ["test"]
    plugin_capabilities = ["test"]

    def execute(self, **kwargs) -> dict:
        return {"status": "success", **kwargs}


class TestBosPlugin:
    """Test BosPlugin base class."""

    def test_initialization(self):
        plugin = MinimalPlugin()
        assert plugin.context is not None
        assert plugin.plugin_id == "test-minimal"
        assert plugin.plugin_version == "1.0.0"

    def test_initialization_with_context(self):
        ctx = PluginContext(workspace="/test")
        plugin = MinimalPlugin(context=ctx)
        assert plugin.context.workspace == "/test"

    def test_execute(self):
        plugin = MinimalPlugin()
        result = plugin.execute(value=42)
        assert result["status"] == "success"
        assert result["value"] == 42

    def test_configure(self):
        plugin = MinimalPlugin()
        plugin.configure({"api_key": "secret", "timeout": 30})
        assert plugin.config["api_key"] == "secret"
        assert plugin.config["timeout"] == 30

    def test_validate(self):
        plugin = MinimalPlugin()
        assert plugin.validate() is True

    def test_health_check(self):
        plugin = MinimalPlugin()
        health = plugin.health_check()
        assert health["status"] == "healthy"
        assert health["plugin_id"] == "test-minimal"
        assert health["version"] == "1.0.0"

    def test_get_metadata(self):
        plugin = MinimalPlugin()
        meta = plugin.get_metadata()
        assert meta["id"] == "test-minimal"
        assert meta["version"] == "1.0.0"
        assert meta["name"] == "Test Plugin"
        assert meta["author"] == "Test Author"
        assert "test" in meta["tags"]

    def test_repr(self):
        plugin = MinimalPlugin()
        repr_str = repr(plugin)
        assert "test-minimal" in repr_str
        assert "1.0.0" in repr_str


class TestAbstractPlugin:
    """Test abstract plugin behavior."""

    def test_cannot_instantiate_abstract(self):
        class IncompletePlugin(BosPlugin):
            plugin_id = "incomplete"

        with pytest.raises(TypeError) as exc_info:
            IncompletePlugin()  # type: ignore[reportAbstractUsage]

        assert "abstract" in str(exc_info.value).lower()


class TestPluginWithComplexConfig:
    """Test plugin with complex configuration."""

    def test_nested_config(self):
        class ConfiguredPlugin(BosPlugin):
            plugin_id = "configured"

            def execute(self, **kwargs) -> dict:
                return {"config": self.config}

        plugin = ConfiguredPlugin()
        plugin.configure({"database": {"host": "localhost", "port": 5432}, "api_keys": ["key1", "key2"]})

        result = plugin.execute()
        assert result["config"]["database"]["host"] == "localhost"
        assert result["config"]["api_keys"] == ["key1", "key2"]
