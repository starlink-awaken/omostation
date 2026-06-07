"""AetherForge unified configuration loader.

Loads settings from ``aetherforge.yaml`` with fallback to env vars
and defaults.

Config file search order:
  1. ``./aetherforge.yaml`` (project-local)
  2. ``~/.aetherforge/config.yaml`` (user-global)
  3. Environment variables (``AETHERFORGE_*``)
  4. Built-in defaults

Usage::

    from aetherforge.config import load_config

    cfg = load_config()
    # cfg.gateway.default_model
    # cfg.mesh.health_check_interval
    # cfg.rate_limiter.default_tpm
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ── Config dataclasses ─────────────────────────────────────────────────────


@dataclass
class GatewayConfig:
    """Gateway provider and routing settings."""

    enabled: bool = True
    default_model: str = ""
    default_provider: str = ""
    auto_detect: bool = True
    mcp_port: int = 0  # 0 = stdio, >0 = SSE


@dataclass
class RateLimiterConfig:
    """Rate limiter settings."""

    enabled: bool = True
    default_tpm: int = 0  # 0 = unlimited
    default_rpm: int = 0
    window_seconds: float = 60.0


@dataclass
class TopologyConfig:
    """Topology discovery settings."""

    enabled: bool = True
    scan_on_start: bool = True
    health_check_interval: int = 60  # seconds
    m1_dir: str = str(Path.home() / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "compute_engine")
    probe_local: bool = True
    detect_cloud: bool = True
    static_nodes: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PoolConfig:
    """Compute pool settings."""

    workers_per_node: int = 2
    auto_scale: bool = True
    min_workers: int = 1
    max_workers: int = 20
    scale_up_threshold: float = 0.8
    scale_down_threshold: float = 0.2
    scale_cooldown: int = 30  # seconds between scale events


@dataclass
class WorkerConfig:
    """Worker settings."""

    heartbeat_timeout: float = 60.0
    enable_message_bus: bool = True
    message_bus_persist: bool = True


@dataclass
class SwarmConfig:
    """Swarm engine settings."""

    enabled: bool = True
    use_gateway_synapse: bool = True  # use gateway providers vs native synapses


@dataclass
class MetricsConfig:
    """Metrics collection settings."""

    enabled: bool = True
    export_interval: int = 300  # seconds between JSONL exports
    export_path: str = str(Path.home() / ".aetherforge" / "metrics.jsonl")


@dataclass
class LoggingConfig:
    """Logging configuration."""

    level: str = "INFO"
    format: str = "console"  # console or json


@dataclass
class AetherForgeConfig:
    """Root configuration object."""

    gateway: GatewayConfig = field(default_factory=GatewayConfig)
    rate_limiter: RateLimiterConfig = field(default_factory=RateLimiterConfig)
    topology: TopologyConfig = field(default_factory=TopologyConfig)
    pool: PoolConfig = field(default_factory=PoolConfig)
    worker: WorkerConfig = field(default_factory=WorkerConfig)
    swarm: SwarmConfig = field(default_factory=SwarmConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    # ── Factory helpers ──────────────────────────────────────────────────────

    def apply_to_rate_limiter(self, limiter: Any) -> None:
        """Apply rate limiter config to a ``RateLimiter`` instance."""
        if not self.rate_limiter.enabled:
            return
        limiter.set_default_limits(
            tpm=self.rate_limiter.default_tpm,
            rpm=self.rate_limiter.default_rpm,
        )

    def apply_to_pool(self, pool: Any) -> dict[str, Any]:
        """Apply pool config, returning kwargs for ``ComputePool``."""
        return {
            "min_workers": self.pool.min_workers,
            "max_workers": self.pool.max_workers,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize config to a dictionary."""
        return {
            "gateway": {
                "enabled": self.gateway.enabled,
                "default_model": self.gateway.default_model,
                "default_provider": self.gateway.default_provider,
                "auto_detect": self.gateway.auto_detect,
            },
            "rate_limiter": {
                "enabled": self.rate_limiter.enabled,
                "default_tpm": self.rate_limiter.default_tpm,
                "default_rpm": self.rate_limiter.default_rpm,
                "window_seconds": self.rate_limiter.window_seconds,
            },
            "topology": {
                "enabled": self.topology.enabled,
                "health_check_interval": self.topology.health_check_interval,
            },
            "pool": {
                "workers_per_node": self.pool.workers_per_node,
                "auto_scale": self.pool.auto_scale,
                "min_workers": self.pool.min_workers,
                "max_workers": self.pool.max_workers,
            },
            "metrics": {"enabled": self.metrics.enabled},
            "logging": {"level": self.logging.level},
        }


# ── Default config (embedded YAML-like) ─────────────────────────────────────

_DEFAULT_CONFIG_YAML = """
# AetherForge Configuration
# See https://github.com/aetherforge/aetherforge for docs

gateway:
  enabled: true
  auto_detect: true

rate_limiter:
  enabled: true
  default_tpm: 0       # 0 = unlimited
  default_rpm: 0
  window_seconds: 60

topology:
  enabled: true
  scan_on_start: true
  health_check_interval: 60
  probe_local: true
  detect_cloud: true

pool:
  workers_per_node: 2
  auto_scale: true
  min_workers: 1
  max_workers: 20
  scale_up_threshold: 0.8
  scale_down_threshold: 0.2
  scale_cooldown: 30

worker:
  enable_message_bus: true
  message_bus_persist: true
  heartbeat_timeout: 60.0

swarm:
  enabled: true
  use_gateway_synapse: true

metrics:
  enabled: true
  export_interval: 300

logging:
  level: INFO
  format: console
"""


def _find_config_file() -> Path | None:
    """Search for config file in order of precedence."""
    # 1. Environment override
    env_path = os.environ.get("AETHERFORGE_CONFIG", "")
    if env_path:
        p = Path(env_path)
        if p.is_file():
            return p

    # 2. Project-local
    for candidate in [Path.cwd() / "aetherforge.yaml", Path.cwd() / "aetherforge.yml"]:
        if candidate.is_file():
            return candidate

    # 3. User-global
    user_dir = Path.home() / ".aetherforge"
    for candidate in [user_dir / "config.yaml", user_dir / "config.yml"]:
        if candidate.is_file():
            return candidate

    return None


def _merge_dict(base: dict, override: dict) -> dict:
    """Deep merge two dicts (override wins)."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _merge_dict(result[k], v)
        else:
            result[k] = v
    return result


def _dict_to_config(data: dict) -> AetherForgeConfig:
    """Convert a nested dict to AetherForgeConfig."""
    cfg = AetherForgeConfig()

    g = data.get("gateway", {})
    cfg.gateway = GatewayConfig(
        enabled=g.get("enabled", True),
        default_model=g.get("default_model", ""),
        default_provider=g.get("default_provider", ""),
        auto_detect=g.get("auto_detect", True),
        mcp_port=g.get("mcp_port", 0),
    )

    rl = data.get("rate_limiter", {})
    cfg.rate_limiter = RateLimiterConfig(
        enabled=rl.get("enabled", True),
        default_tpm=rl.get("default_tpm", 0),
        default_rpm=rl.get("default_rpm", 0),
        window_seconds=rl.get("window_seconds", 60.0),
    )

    t = data.get("topology", {})
    cfg.topology = TopologyConfig(
        enabled=t.get("enabled", True),
        scan_on_start=t.get("scan_on_start", True),
        health_check_interval=t.get("health_check_interval", 60),
        m1_dir=t.get("m1_dir", cfg.topology.m1_dir),
        probe_local=t.get("probe_local", True),
        detect_cloud=t.get("detect_cloud", True),
        static_nodes=t.get("static_nodes", []),
    )

    p = data.get("pool", {})
    cfg.pool = PoolConfig(
        workers_per_node=p.get("workers_per_node", 2),
        auto_scale=p.get("auto_scale", True),
        min_workers=p.get("min_workers", 1),
        max_workers=p.get("max_workers", 20),
        scale_up_threshold=p.get("scale_up_threshold", 0.8),
        scale_down_threshold=p.get("scale_down_threshold", 0.2),
        scale_cooldown=p.get("scale_cooldown", 30),
    )

    w = data.get("worker", {})
    cfg.worker = WorkerConfig(
        heartbeat_timeout=w.get("heartbeat_timeout", 60.0),
        enable_message_bus=w.get("enable_message_bus", True),
        message_bus_persist=w.get("message_bus_persist", True),
    )

    s = data.get("swarm", {})
    cfg.swarm = SwarmConfig(
        enabled=s.get("enabled", True),
        use_gateway_synapse=s.get("use_gateway_synapse", True),
    )

    m = data.get("metrics", {})
    cfg.metrics = MetricsConfig(
        enabled=m.get("enabled", True),
        export_interval=m.get("export_interval", 300),
        export_path=m.get("export_path", cfg.metrics.export_path),
    )

    l = data.get("logging", {})  # noqa: E741
    cfg.logging = LoggingConfig(
        level=l.get("level", "INFO"),
        format=l.get("format", "console"),
    )

    return cfg


def load_config(path: str | Path | None = None) -> AetherForgeConfig:
    """Load configuration from file, env, or defaults.

    Args:
        path: Optional explicit config path. If not provided, searches
              in order: ``./aetherforge.yaml`` → ``~/.aetherforge/config.yaml``.

    Returns:
        An ``AetherForgeConfig`` instance populated with merged settings.
    """
    import yaml  # requires pyyaml

    # Start with defaults
    defaults = yaml.safe_load(_DEFAULT_CONFIG_YAML) or {}

    # Load file
    config_file = Path(path) if path else _find_config_file()
    file_data: dict = {}
    if config_file and config_file.is_file():
        try:
            with open(config_file) as f:
                file_data = yaml.safe_load(f) or {}
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Failed to load config %s: %s", config_file, exc)

    # Merge: defaults ← file
    merged = _merge_dict(defaults, file_data)

    # Environment overrides
    env_overrides = {
        "AETHERFORGE_GATEWAY_DEFAULT_MODEL": ("gateway", "default_model"),
        "AETHERFORGE_LOG_LEVEL": ("logging", "level"),
        "AETHERFORGE_RATE_LIMIT_TPM": ("rate_limiter", "default_tpm"),
        "AETHERFORGE_RATE_LIMIT_RPM": ("rate_limiter", "default_rpm"),
    }
    for env_key, (section, field) in env_overrides.items():
        val = os.environ.get(env_key, "")
        if val:
            if section not in merged:
                merged[section] = {}
            merged[section][field] = val

    return _dict_to_config(merged)


def write_default_config(path: str | Path) -> Path:
    """Write the default config to *path*."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_DEFAULT_CONFIG_YAML.lstrip())
    return p
