"""Topology scanner — discovers compute nodes via multiple backends.

Discovery methods:
  - **Static config**: Loads from L0 M1 compute_engine YAML
  - **Local probe**: Discovers local daemons (Ollama, etc.)
  - **Environment**: Detects configured cloud API providers
  - **mDNS** (future): LAN discovery
  - **SSH** (future): Remote probe
"""

from __future__ import annotations

import json
import logging
import os
import socket
from datetime import datetime
from pathlib import Path
from typing import Any

from .node import ComputeNode, NodeEngineType, NodeStatus
from .registry import NodeRegistry

_log = logging.getLogger(__name__)

# Default paths for L0 M1 compute_engine config
M1_ENGINE_DIR = Path.home() / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "compute_engine"

# Well-known local daemons to probe
LOCAL_DAEMONS: list[dict[str, Any]] = [
    {
        "name": "ollama",
        "base_url": "http://localhost:11434",
        "protocols": ["openai"],
        "capabilities": ["chat", "embedding"],
        "engine_type": NodeEngineType.LOCAL_DAEMON,
    },
]

# Cloud API providers detectable from env vars
CLOUD_PROVIDERS: list[dict[str, Any]] = [
    {
        "name": "openai",
        "env_var": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "protocols": ["openai"],
        "capabilities": ["chat", "embedding", "vision", "tools"],
        "engine_type": NodeEngineType.CLOUD_API,
        "network_zone": "cloud",
    },
    {
        "name": "anthropic",
        "env_var": "ANTHROPIC_API_KEY",
        "base_url": "https://api.anthropic.com/v1",
        "protocols": ["anthropic"],
        "capabilities": ["chat", "vision", "tools"],
        "engine_type": NodeEngineType.CLOUD_API,
        "network_zone": "cloud",
    },
    {
        "name": "gemini",
        "env_var": "GOOGLE_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1",
        "protocols": ["gemini"],
        "capabilities": ["chat", "embedding", "vision"],
        "engine_type": NodeEngineType.CLOUD_API,
        "network_zone": "cloud",
    },
    {
        "name": "deepseek",
        "env_var": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1",
        "protocols": ["deepseek"],
        "capabilities": ["chat"],
        "engine_type": NodeEngineType.CLOUD_API,
        "network_zone": "cloud",
    },
]


# ── Static config loader ────────────────────────────────────────────────────


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file, returning {} on failure."""
    import yaml  # pyyaml is a dep of aetherforge-gateway

    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except Exception as exc:
        _log.debug("Failed to load YAML %s: %s", path, exc)
        return {}


def load_static_nodes(m1_dir: str | Path = M1_ENGINE_DIR) -> list[ComputeNode]:
    """Load compute nodes from L0 M1 compute_engine YAML files.

    Reads all ``.yaml`` files under *m1_dir* and converts them to
    :class:`ComputeNode` objects. Returns an empty list if the
    directory doesn't exist.
    """
    m1_path = Path(m1_dir)
    if not m1_path.is_dir():
        _log.info("M1 engine dir not found: %s", m1_path)
        return []

    nodes: list[ComputeNode] = []
    for yaml_file in sorted(m1_path.glob("*.yaml")):
        data = _load_yaml(yaml_file)
        if not data:
            continue

        node = _yaml_to_node(data)
        if node:
            nodes.append(node)

    _log.info("Loaded %d static nodes from %s", len(nodes), m1_path)
    return nodes


def _yaml_to_node(data: dict[str, Any]) -> ComputeNode | None:
    """Convert a YAML M1 node entry to a ComputeNode."""
    node_id = data.get("node_id", data.get("id", ""))
    if not node_id:
        return None

    engine_type_str = data.get("engine_type", "cloud_api")
    try:
        engine_type = NodeEngineType(engine_type_str)
    except ValueError:
        engine_type = NodeEngineType.CLOUD_API

    network_zone = data.get("network_zone", "cloud")
    protocols = data.get("protocols", [])
    if isinstance(protocols, str):
        protocols = [protocols]
    protocols = [p.lower() for p in protocols]

    cost = data.get("cost_per_1k_tokens", data.get("cost", {}))
    if isinstance(cost, (int, float)):
        cost = {"input": float(cost), "output": float(cost)}

    return ComputeNode(
        node_id=node_id,
        name=data.get("name", data.get("label", node_id)),
        engine_type=engine_type,
        base_url=data.get("base_url", ""),
        network_zone=network_zone,
        protocols=protocols,
        capabilities=data.get("capabilities", []),
        priority=data.get("priority", 5),
        max_concurrency=data.get("max_concurrency", 4),
        cost_per_1k_tokens=cost if isinstance(cost, dict) else {"input": 0.0, "output": 0.0},
        tags=data.get("tags", {}),
        metadata=data,
    )


# ── Local daemon probes ─────────────────────────────────────────────────────


def _check_tcp_port(host: str, port: int, timeout: float = 2.0) -> bool:
    """Check if a TCP port is open on *host*."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def _extract_port(url: str) -> tuple[str, int]:
    """Extract host and port from a URL."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return host, port


def probe_local_daemons() -> list[ComputeNode]:
    """Probe well-known local daemons and return discovered nodes."""
    discovered: list[ComputeNode] = []
    now = datetime.now().timestamp()

    for cfg in LOCAL_DAEMONS:
        host, port = _extract_port(cfg["base_url"])
        is_alive = _check_tcp_port(host, port)

        node_id = f"{cfg['name']}-local"
        node = ComputeNode(
            node_id=node_id,
            name=f"Local {cfg['name'].title()}",
            engine_type=cfg["engine_type"],
            base_url=cfg["base_url"],
            network_zone="local",
            protocols=cfg["protocols"],
            capabilities=cfg["capabilities"],
            status=NodeStatus.ONLINE if is_alive else NodeStatus.OFFLINE,
            priority=3 if is_alive else 10,
            last_seen=now if is_alive else 0,
            max_concurrency=1,
            tags={"discovery": "probe", "auto": "true"},
        )
        discovered.append(node)

    return discovered


# ── Cloud provider detection ────────────────────────────────────────────────


def detect_cloud_nodes() -> list[ComputeNode]:
    """Detect cloud API providers from environment variables."""
    discovered: list[ComputeNode] = []
    now = datetime.now().timestamp()

    for cfg in CLOUD_PROVIDERS:
        env_val = os.environ.get(cfg["env_var"], "").strip()
        if not env_val:
            continue

        node_id = f"{cfg['name']}-cloud"
        node = ComputeNode(
            node_id=node_id,
            name=f"{cfg['name'].title()} API",
            engine_type=cfg["engine_type"],
            base_url=cfg["base_url"],
            network_zone=cfg["network_zone"],
            protocols=cfg["protocols"],
            capabilities=cfg["capabilities"],
            status=NodeStatus.ONLINE,
            priority=1 if cfg["name"] == "openai" else 2,
            last_seen=now,
            max_concurrency=8,
            tags={"discovery": "env", "provider": cfg["name"]},
        )
        discovered.append(node)

    return discovered


# ── Orchestrator ────────────────────────────────────────────────────────────


class TopologyScanner:
    """Orchestrates topology discovery across multiple backends.

    Usage::

        scanner = TopologyScanner()
        nodes = scanner.scan_all()
        registry.merge(nodes)
    """

    def __init__(self, registry: NodeRegistry | None = None) -> None:
        self._registry = registry or NodeRegistry()

    @property
    def registry(self) -> NodeRegistry:
        return self._registry

    def scan_all(self) -> list[ComputeNode]:
        """Run all discovery methods and merge results into the registry."""
        all_nodes: list[ComputeNode] = []

        # 1. Static config (L0 M1)
        all_nodes.extend(load_static_nodes())

        # 2. Local daemon probes
        all_nodes.extend(probe_local_daemons())

        # 3. Cloud env detection
        all_nodes.extend(detect_cloud_nodes())

        # Deduplicate by node_id (last writer wins)
        seen: dict[str, ComputeNode] = {}
        for node in all_nodes:
            seen[node.node_id] = node

        unique = list(seen.values())
        self._registry.merge(unique)
        _log.info("Topology scan: %d nodes discovered (%d unique)", len(all_nodes), len(unique))
        return unique

    def scan_static(self) -> list[ComputeNode]:
        """Only static config discovery."""
        nodes = load_static_nodes()
        self._registry.merge(nodes)
        return nodes

    def scan_local(self) -> list[ComputeNode]:
        """Only local daemon probe."""
        nodes = probe_local_daemons()
        self._registry.merge(nodes)
        return nodes

    def scan_cloud(self) -> list[ComputeNode]:
        """Only cloud env detection."""
        nodes = detect_cloud_nodes()
        self._registry.merge(nodes)
        return nodes
