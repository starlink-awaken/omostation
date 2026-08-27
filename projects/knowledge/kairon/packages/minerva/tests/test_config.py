"""Tests for minerva.config — YAML + env var loader.

Covers dataclass defaults, _from_dict YAML parsing, _apply_env_overrides
behavior, and full MinervaConfig.load() integration.
"""

from __future__ import annotations

import os

from minerva.config import (
    ExecutionConfig,
    LLMConfig,
    MinervaConfig,
    SearchConfig,
    _load_forge_env,
)

# ── Dataclass defaults ───────────────────────────────────────────────


class TestLLMConfig:
    def test_default_provider(self):
        c = LLMConfig()
        assert c.provider == "ollama"

    def test_default_base_url(self):
        c = LLMConfig()
        assert c.base_url == "http://localhost:11434/v1"

    def test_default_models(self):
        c = LLMConfig()
        assert c.models["agent"] == "qwen3:30b-a3b"
        assert c.models["reasoning"] == "deepseek-r1:70b"

    def test_custom_models(self):
        c = LLMConfig(models={"agent": "custom:7b"})
        assert c.models == {"agent": "custom:7b"}


class TestSearchConfig:
    def test_default_searxng_port(self):
        c = SearchConfig()
        assert c.searxng_url == "http://localhost:8080"

    def test_custom_searxng_port(self):
        c = SearchConfig(searxng_url="http://x:9000")
        assert c.searxng_url == "http://x:9000"


class TestExecutionConfig:
    def test_default_thresholds(self):
        c = ExecutionConfig()
        assert c.warn_threshold == 0.80
        assert c.block_threshold == 1.00

    def test_default_per_level_max_cost(self):
        c = ExecutionConfig()
        assert c.per_level_max_cost["L0"] == 0.0
        assert c.per_level_max_cost["L4"] == 15.0


# ── _load_forge_env ──────────────────────────────────────────────────


class TestLoadForgeEnv:
    def test_skips_when_config_missing(self, tmp_path, monkeypatch):
        """When ~/.workspace/config.py does not exist, _load_forge_env returns silently."""
        monkeypatch.setattr(os.path, "expanduser", lambda x: str(tmp_path / "nonexistent.py"))
        # Should not raise
        _load_forge_env()

    def test_loads_exports_from_config(self, tmp_path, monkeypatch):
        """When config.py prints 'export KEY=val', env var is set (if not already)."""
        config = tmp_path / "config.py"
        config.write_text(
            "#!/usr/bin/env python3\nprint('export FOO_TEST_KEY=foo_value')\nprint('export BAR_TEST_KEY=bar_value')\n"
        )
        monkeypatch.setattr(os.path, "expanduser", lambda x: str(config))
        monkeypatch.delenv("FOO_TEST_KEY", raising=False)
        monkeypatch.delenv("BAR_TEST_KEY", raising=False)
        _load_forge_env()
        assert os.environ.get("FOO_TEST_KEY") == "foo_value"
        assert os.environ.get("BAR_TEST_KEY") == "bar_value"

    def test_does_not_override_existing_env(self, tmp_path, monkeypatch):
        """If env var already set, _load_forge_env does not overwrite."""
        config = tmp_path / "config.py"
        config.write_text("print('export EXISTING_KEY=new_value')\n")
        monkeypatch.setattr(os.path, "expanduser", lambda x: str(config))
        monkeypatch.setenv("EXISTING_KEY", "original_value")
        _load_forge_env()
        assert os.environ["EXISTING_KEY"] == "original_value"

    def test_swallows_subprocess_failure(self, tmp_path, monkeypatch):
        """When subprocess.run fails or times out, _load_forge_env silently passes."""
        config = tmp_path / "config.py"
        config.write_text("raise SystemExit(1)\n")
        monkeypatch.setattr(os.path, "expanduser", lambda x: str(config))
        # Should not raise
        _load_forge_env()

    def test_ignores_non_export_lines(self, tmp_path, monkeypatch):
        """Lines not starting with 'export' are skipped."""
        config = tmp_path / "config.py"
        config.write_text("print('# comment')\nprint('NOT_AN_EXPORT=ignored')\n")
        monkeypatch.setattr(os.path, "expanduser", lambda x: str(config))
        monkeypatch.delenv("NOT_AN_EXPORT", raising=False)
        _load_forge_env()
        assert "NOT_AN_EXPORT" not in os.environ


# ── MinervaConfig._from_dict ────────────────────────────────────────


class TestFromDict:
    def test_empty_dict_returns_defaults(self):
        c = MinervaConfig._from_dict({})
        assert c.llm.provider == "ollama"
        assert c.search.searxng_url.startswith("http://")

    def test_tier1_llm_parsing(self):
        data = {
            "tier1": {
                "llm": {
                    "provider": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "defaults": {"temperature": 0.3, "top_p": 0.5, "context_size": 8192},
                }
            }
        }
        c = MinervaConfig._from_dict(data)
        assert c.llm.provider == "openai"
        assert c.llm.temperature == 0.3
        assert c.llm.context_size == 8192

    def test_tier1_search_parsing(self):
        data = {"tier1": {"search": {"searxng": {"base_url": "http://s:9999"}}}}
        c = MinervaConfig._from_dict(data)
        assert c.search.searxng_url == "http://s:9999"

    def test_tier1_knowledge_parsing(self):
        data = {"tier1": {"knowledge": {"sqlite_path": "/tmp/k.db", "lancedb_path": "/tmp/l"}}}
        c = MinervaConfig._from_dict(data)
        assert c.knowledge.sqlite_path == "/tmp/k.db"
        assert c.knowledge.lancedb_path == "/tmp/l"

    def test_tier1_nlp_parsing(self):
        data = {"tier1": {"nlp": {"spacy_model": "en_core_web_lg"}}}
        c = MinervaConfig._from_dict(data)
        assert c.nlp.spacy_model == "en_core_web_lg"

    def test_tier2_metaso_api_key(self):
        data = {"tier2": {"search_apis": {"metaso": {"api_key": "real_key_value"}}}}
        c = MinervaConfig._from_dict(data)
        assert c.search.metaso_api_key == "real_key_value"

    def test_tier2_metaso_placeholder_ignored(self):
        data = {"tier2": {"search_apis": {"metaso": {"api_key": "${METASO_API_KEY}"}}}}
        c = MinervaConfig._from_dict(data)
        # Placeholder string is not loaded
        assert c.search.metaso_api_key is None

    def test_cloud_llm_parsing(self):
        data = {"cloud_llm": {"deepseek": {"api_key": "ds_key", "models": {"flash": "f1", "pro": "p1"}}}}
        c = MinervaConfig._from_dict(data)
        assert c.cloud.deepseek_api_key == "ds_key"
        assert c.cloud.deepseek_flash_model == "f1"
        assert c.cloud.deepseek_pro_model == "p1"

    def test_execution_parsing(self):
        data = {"execution": {"cost_guard": {"monthly_budget_usd": 100.0, "warn_threshold": 0.5}}}
        c = MinervaConfig._from_dict(data)
        assert c.execution.monthly_budget_usd == 100.0
        assert c.execution.warn_threshold == 0.5


# ── MinervaConfig._apply_env_overrides ───────────────────────────


class TestApplyEnvOverrides:
    def setup_method(self):
        self.config = MinervaConfig()

    def test_no_env_no_change(self, monkeypatch):
        # Strip all overrides before testing
        for k in [
            "DEEPSEEK_API_KEY",
            "METASO_API_KEY",
            "EXA_API_KEY",
            "JINA_API_KEY",
            "LLM_PROVIDER",
            "LLM_BASE_URL",
            "OLLAMA_BASE_URL",
            "LLM_API_KEY",
            "LLM_MODEL",
            "MINERVA_HOME",
        ]:
            monkeypatch.delenv(k, raising=False)
        c = self.config
        out = MinervaConfig._apply_env_overrides(c)
        assert out.llm.provider == "ollama"
        assert out.cloud.deepseek_api_key is None

    def test_deepseek_override(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "key_ds")
        out = MinervaConfig._apply_env_overrides(self.config)
        assert out.cloud.deepseek_api_key == "key_ds"

    def test_metaso_override(self, monkeypatch):
        monkeypatch.setenv("METASO_API_KEY", "key_metaso")
        out = MinervaConfig._apply_env_overrides(self.config)
        assert out.search.metaso_api_key == "key_metaso"

    def test_exa_override(self, monkeypatch):
        monkeypatch.setenv("EXA_API_KEY", "key_exa")
        out = MinervaConfig._apply_env_overrides(self.config)
        assert out.search.exa_api_key == "key_exa"

    def test_jina_override(self, monkeypatch):
        monkeypatch.setenv("JINA_API_KEY", "key_jina")
        out = MinervaConfig._apply_env_overrides(self.config)
        assert out.search.jina_api_key == "key_jina"

    def test_llm_provider_override(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        out = MinervaConfig._apply_env_overrides(self.config)
        assert out.llm.provider == "openai"

    def test_llm_base_url_override(self, monkeypatch):
        monkeypatch.setenv("LLM_BASE_URL", "https://custom.api/v1")
        out = MinervaConfig._apply_env_overrides(self.config)
        assert out.llm.base_url == "https://custom.api/v1"

    def test_ollama_base_url_fallback(self, monkeypatch):
        """LLM_BASE_URL takes precedence; OLLAMA_BASE_URL is fallback."""
        monkeypatch.delenv("LLM_BASE_URL", raising=False)
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11435/v1")
        out = MinervaConfig._apply_env_overrides(self.config)
        assert out.llm.base_url == "http://ollama:11435/v1"

    def test_llm_api_key_override(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "sk-1234")
        out = MinervaConfig._apply_env_overrides(self.config)
        assert out.llm.api_key == "sk-1234"

    def test_llm_model_override_all_slots(self, monkeypatch):
        """LLM_MODEL replaces all model slot values (agent/reasoning/writer)."""
        monkeypatch.setenv("LLM_MODEL", "shared:7b")
        out = MinervaConfig._apply_env_overrides(self.config)
        assert out.llm.models["agent"] == "shared:7b"
        assert out.llm.models["reasoning"] == "shared:7b"
        assert out.llm.models["writer"] == "shared:7b"

    def test_minerva_home_derives_paths(self, monkeypatch):
        """MINERVA_HOME sets data_dir + state_dir + knowledge_dir."""
        monkeypatch.setenv("MINERVA_HOME", "/custom/home")
        out = MinervaConfig._apply_env_overrides(self.config)
        assert out.data_dir == "/custom/home"
        assert out.state_dir == "/custom/home/state"
        assert out.knowledge_dir == "/custom/home/knowledge"


# ── MinervaConfig.load integration ────────────────────────────────


class TestLoad:
    def test_load_with_no_file_returns_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MINERVA_CONFIG", str(tmp_path / "nonexistent.yaml"))
        c = MinervaConfig.load()
        assert c.llm.provider == "ollama"

    def test_load_with_yaml(self, tmp_path, monkeypatch):
        yaml_path = tmp_path / "minerva.yaml"
        yaml_path.write_text(
            "tier1:\n  llm:\n    provider: openai\n  search:\n    searxng:\n      base_url: http://test:8080\n"
        )
        monkeypatch.setenv("MINERVA_CONFIG", str(yaml_path))
        c = MinervaConfig.load()
        assert c.llm.provider == "openai"
        assert c.search.searxng_url == "http://test:8080"

    def test_load_with_yaml_and_env_override(self, tmp_path, monkeypatch):
        yaml_path = tmp_path / "minerva.yaml"
        yaml_path.write_text("tier1:\n  llm:\n    provider: openai\n")
        monkeypatch.setenv("MINERVA_CONFIG", str(yaml_path))
        monkeypatch.setenv("LLM_PROVIDER", "deepseek")
        c = MinervaConfig.load()
        # Env overrides YAML
        assert c.llm.provider == "deepseek"

    def test_load_with_explicit_path(self, tmp_path):
        yaml_path = tmp_path / "custom.yaml"
        yaml_path.write_text("tier1:\n  llm:\n    provider: anthropic\n")
        c = MinervaConfig.load(config_path=str(yaml_path))
        assert c.llm.provider == "anthropic"
