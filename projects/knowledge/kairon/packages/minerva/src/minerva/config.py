"""Minerva configuration loader — YAML + env vars."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml


# ── Forge Registry bootstrap ──────────────────────────────────────────────
def _load_forge_env() -> None:
    """Load environment variables from Forge Registry via config.py env.

    Runs once at module import time to populate os.environ with
    registry-defined values (ports, paths, etc.) before any config is loaded.
    Only sets keys not already present in the environment (user overrides win).
    """
    config_py = os.path.expanduser("~/.workspace/config.py")
    if not os.path.isfile(config_py):
        return
    try:
        result = subprocess.run(
            ["python3", config_py, "env"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                line = line.strip()
                if line.startswith("export "):
                    parts = line[7:].split("=", 1)
                    if len(parts) == 2:
                        key, val = parts[0], parts[1]
                        if key not in os.environ:
                            os.environ[key] = val
    except Exception:
        pass


_load_forge_env()


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""

    pass


@dataclass
class LLMConfig:
    provider: str = "ollama"
    base_url: str = "http://localhost:11434/v1"
    api_key: str = "ollama"
    models: dict = field(
        default_factory=lambda: {
            "agent": "qwen3:30b-a3b",
            "reasoning": "deepseek-r1:70b",
            "writer": "qwen3.5:27b",
        }
    )
    temperature: float = 0.7
    top_p: float = 0.95
    context_size: int = 16384


@dataclass
class SearchConfig:
    searxng_url: str = f"http://localhost:{os.environ.get('ONTODERIVE_WEB_PORT', '8080')}"
    exa_api_key: str | None = None
    jina_api_key: str | None = None
    metaso_api_key: str | None = None


@dataclass
class KnowledgeConfig:
    sqlite_path: str = "~/minerva/knowledge.db"
    lancedb_path: str = "~/minerva/vectors"
    wiki_path: str = "~/knowledge/wiki"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384


@dataclass
class NLPConfig:
    spacy_model: str = "en_core_web_sm"
    spacy_model_zh: str = "zh_core_web_sm"


@dataclass
class ExecutionConfig:
    monthly_budget_usd: float = 50.0
    warn_threshold: float = 0.80
    block_threshold: float = 1.00
    per_level_max_cost: dict = field(
        default_factory=lambda: {
            "L0": 0.0,
            "L1": 0.0,
            "L2": 1.0,
            "L3": 5.0,
            "L4": 15.0,
        }
    )


@dataclass
class CloudLLMConfig:
    deepseek_api_key: str | None = None
    deepseek_flash_model: str = "deepseek-v4-flash"
    deepseek_pro_model: str = "deepseek-v4-pro"
    glm_api_key: str | None = None
    glm_model: str = "glm-5"


@dataclass
class MinervaConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    knowledge: KnowledgeConfig = field(default_factory=KnowledgeConfig)
    nlp: NLPConfig = field(default_factory=NLPConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    cloud: CloudLLMConfig = field(default_factory=CloudLLMConfig)
    data_dir: str = "~/minerva"
    state_dir: str = "~/minerva/state"
    knowledge_dir: str = "~/knowledge"

    @classmethod
    def load(cls, config_path: str | None = None) -> MinervaConfig:
        """Load configuration from YAML file + environment variables.

        Environment variables override YAML values.
        Required env vars: none (all have defaults).
        Optional env vars: DEEPSEEK_API_KEY, EXA_API_KEY, JINA_API_KEY, etc.
        """
        config = cls()

        # Try loading YAML
        if config_path is None:
            config_path = os.environ.get(
                "MINERVA_CONFIG",
                str(Path(__file__).parent.parent.parent / "config" / "minerva.yaml"),
            )

        if os.path.exists(config_path):
            with open(config_path) as f:
                data = yaml.safe_load(f)
            if data:
                config = cls._from_dict(data)

        # Environment variable overrides
        config = cls._apply_env_overrides(config)
        return config

    @classmethod
    def _from_dict(cls, data: dict) -> MinervaConfig:
        """Parse YAML dict into config."""
        config = cls()

        tier1 = data.get("tier1", {})
        if "llm" in tier1:
            llm_data = tier1["llm"]
            config.llm = LLMConfig(
                provider=llm_data.get("provider", "ollama"),
                base_url=llm_data.get("base_url", "http://localhost:11434/v1"),
                models=llm_data.get("models", config.llm.models),
                temperature=llm_data.get("defaults", {}).get("temperature", 0.7),
                top_p=llm_data.get("defaults", {}).get("top_p", 0.95),
                context_size=llm_data.get("defaults", {}).get("context_size", 16384),
            )
        if "search" in tier1:
            s = tier1["search"].get("searxng", {})
            config.search.searxng_url = s.get(
                "base_url", f"http://localhost:{os.environ.get('ONTODERIVE_WEB_PORT', '8080')}"
            )
        if "knowledge" in tier1:
            k = tier1["knowledge"]
            config.knowledge = KnowledgeConfig(
                sqlite_path=k.get("sqlite_path", config.knowledge.sqlite_path),
                lancedb_path=k.get("lancedb_path", config.knowledge.lancedb_path),
                wiki_path=k.get("wiki_path", config.knowledge.wiki_path),
            )

        # Tier 2 search APIs
        tier2 = data.get("tier2", {})
        search_apis = tier2.get("search_apis", {})
        metaso_cfg = search_apis.get("metaso", {})
        if metaso_cfg.get("api_key") and metaso_cfg["api_key"] != "${METASO_API_KEY}":
            config.search.metaso_api_key = metaso_cfg["api_key"]

        if "nlp" in tier1:
            n = tier1["nlp"]
            config.nlp = NLPConfig(
                spacy_model=n.get("spacy_model", "en_core_web_sm"),
                spacy_model_zh=n.get("spacy_model_zh", "zh_core_web_sm"),
            )

        # Cloud LLM
        cloud = data.get("cloud_llm", {})
        ds = cloud.get("deepseek", {})
        config.cloud.deepseek_api_key = ds.get("api_key") or os.environ.get("DEEPSEEK_API_KEY")
        config.cloud.deepseek_flash_model = ds.get("models", {}).get("flash", "deepseek-v4-flash")
        config.cloud.deepseek_pro_model = ds.get("models", {}).get("pro", "deepseek-v4-pro")

        # Execution
        exec_data = data.get("execution", {})
        cg = exec_data.get("cost_guard", {})
        if cg:
            config.execution = ExecutionConfig(
                monthly_budget_usd=cg.get("monthly_budget_usd", 50.0),
                warn_threshold=cg.get("warn_threshold", 0.80),
                block_threshold=cg.get("block_threshold", 1.00),
                per_level_max_cost=cg.get("per_level_max_cost", config.execution.per_level_max_cost),
            )

        return config

    @classmethod
    def _apply_env_overrides(cls, config: MinervaConfig) -> MinervaConfig:
        """Apply environment variable overrides."""
        if v := os.environ.get("DEEPSEEK_API_KEY"):
            config.cloud.deepseek_api_key = v
        if v := os.environ.get("METASO_API_KEY"):
            config.search.metaso_api_key = v
        if v := os.environ.get("EXA_API_KEY"):
            config.search.exa_api_key = v
        if v := os.environ.get("JINA_API_KEY"):
            config.search.jina_api_key = v
        if v := os.environ.get("LLM_PROVIDER"):
            config.llm.provider = v
        base_url = os.environ.get("LLM_BASE_URL") or os.environ.get("OLLAMA_BASE_URL")
        if base_url:
            config.llm.base_url = base_url
        if v := os.environ.get("LLM_API_KEY"):
            config.llm.api_key = v
        if v := os.environ.get("LLM_MODEL"):
            config.llm.models = dict.fromkeys(config.llm.models, v)
        if v := os.environ.get("MINERVA_HOME"):
            config.data_dir = v
            config.state_dir = f"{v}/state"
            config.knowledge_dir = f"{v}/knowledge"
        return config
