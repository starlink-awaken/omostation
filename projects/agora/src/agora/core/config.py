"""Configuration management for agentmesh gateway migration.

Loads gateway config from JSON file or environment variable AGORA_CONFIG_PATH.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from agora.types import AgentConfig, GatewayConfig, RoutingConfig, RoutingRule  # type: ignore[import-not-found]

DEFAULT_CONFIG = GatewayConfig()

_config_cache: GatewayConfig | None = None


def load_config(config_path: str | None = None) -> GatewayConfig:
    """Load gateway configuration from file or return defaults."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    if config_path is None:
        config_path = os.environ.get("AGORA_CONFIG_PATH", "")
    if config_path and Path(config_path).exists():
        raw = json.loads(Path(config_path).read_text())
        _config_cache = _merge_config(raw)
        return _config_cache
    _config_cache = DEFAULT_CONFIG
    return _config_cache


def _merge_config(raw: dict[str, Any]) -> GatewayConfig:
    routing_raw = raw.get("routing", {})
    rules_raw = routing_raw.get("rules", [])
    agents_raw = raw.get("agents", [])
    rules = [
        RoutingRule(
            name=r.get("name", ""),
            keywords=r.get("keywords", []),
            agent=r.get("agent"),
            agents=r.get("agents"),
            strategy=r.get("strategy", "direct"),
            priority=r.get("priority", 0),
        )
        for r in rules_raw
    ]
    agents = [
        AgentConfig(
            id=a.get("id", ""),
            name=a.get("name", a.get("id", "")),
            type=a.get("type", "process"),
            capabilities=a.get("capabilities", []),
            command=a.get("command"),
            args=a.get("args"),
            env=a.get("env"),
            endpoint=a.get("endpoint"),
        )
        for a in agents_raw
    ]
    return GatewayConfig(
        port=raw.get("port", DEFAULT_CONFIG.port),
        ws_port=raw.get("ws_port", DEFAULT_CONFIG.ws_port),
        host=raw.get("host", DEFAULT_CONFIG.host),
        data_dir=raw.get("data_dir", DEFAULT_CONFIG.data_dir),
        log_dir=raw.get("log_dir", DEFAULT_CONFIG.log_dir),
        log_level=raw.get("log_level", DEFAULT_CONFIG.log_level),
        routing=RoutingConfig(default_agent=routing_raw.get("default_agent"), rules=rules),
        agents=agents,
        models=raw.get("models"),
    )


def reload_config(config_path: str | None = None) -> GatewayConfig:
    """Clear cache and reload configuration."""
    global _config_cache
    _config_cache = None
    return load_config(config_path)


def get_config() -> GatewayConfig:
    """Get the current configuration (loads if not cached)."""
    return load_config()


def get_routing_rules() -> list[RoutingRule]:
    """Get routing rules from current configuration."""
    cfg = get_config()
    return cfg.routing.rules if cfg.routing else []


def get_default_agent() -> str | None:
    """Get default agent ID from current configuration."""
    cfg = get_config()
    return cfg.routing.default_agent if cfg.routing else None


def get_agent_config(agent_id: str) -> AgentConfig | None:
    """Find agent config by ID."""
    cfg = get_config()
    for a in cfg.agents:
        if a.id == agent_id:
            return a
    return None


def get_all_agent_configs() -> list[AgentConfig]:
    """Get all agent configs from current configuration."""
    return list(get_config().agents)
