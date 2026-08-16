"""Tests for iris configuration."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import json
import os
import tempfile

from iris.config import IrisConfig


class TestConfig:
    def test_default_values(self):
        config = IrisConfig()
        assert config.verbose is False

    def test_env_override(self):
        os.environ["IRIS_VERBOSE"] = "true"
        os.environ["IRIS_OBSIDIAN_VAULT"] = "/tmp/test-vault"
        try:
            config = IrisConfig()
            assert config.verbose is True
            assert config.obsidian_vault == "/tmp/test-vault"
        finally:
            del os.environ["IRIS_VERBOSE"]
            del os.environ["IRIS_OBSIDIAN_VAULT"]

    def test_file_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = tmp + "/config.json"
            with open(config_path, "w") as f:
                json.dump({"wxread": {"cookie": "test-cookie"}}, f)
            config = IrisConfig(config_path=config_path)
            assert config.wxread_cookie == "test-cookie"

    def test_set_and_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = tmp + "/config.json"
            config = IrisConfig(config_path=config_path)
            config.set("test.key", "value")
            config2 = IrisConfig(config_path=config_path)
            assert config2.get("test.key") == "value"

    def test_get_default(self):
        config = IrisConfig()
        assert config.get("nonexistent.key", "fallback") == "fallback"
