"""M1Loader — Unified L0 MOF M1 YAML loader.

Loads all M1 namespaces and resolves cross-references:

  compute_engine ──node_ref──▶ compute_node ──has──▶ hardware_asset
                                                  ──in──▶ network_zone

Usage::

    from compute_mesh.topology.m1_loader import M1Loader

    loader = M1Loader()
    engine_nodes = loader.load_engines()       # list[ComputeNode]
    machine_info = loader.get_machine("NODE-MACMINI")  # MachineInfo | None
    zone_info = loader.get_zone("ZONE-LOCALHOST")       # NetworkZoneInfo | None
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

# Default M1 root
try:
    from aetherforge.config import get_m1_dir
    M1_DIR = get_m1_dir("").parent  # get_m1_dir("") → m1/, .parent → mof/
except ImportError:
    M1_DIR = Path.home() / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1"


# ── Data models ──────────────────────────────────────────────────────────────


@dataclass
class MachineInfo:
    """Physical machine information from compute_node + hardware_asset."""

    node_id: str = ""
    device_type: str = ""        # mac_mini, laptop, desktop, cloud_vm, ...
    os: str = ""                 # macOS 15, ubuntu 24.04, ...
    hostname: str = ""           # macmini.local
    cpu_model: str = ""          # Intel Core i7-13500H
    cpu_cores: int = 0
    ram_gb: int = 0
    gpu_model: str = ""          # NVIDIA RTX 4060 Laptop, Apple M2
    gpu_vram_gb: int = 0
    disk_gb: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "device_type": self.device_type,
            "os": self.os,
            "hostname": self.hostname,
            "cpu": f"{self.cpu_model} ({self.cpu_cores} cores)" if self.cpu_model else "",
            "ram": f"{self.ram_gb} GB",
            "gpu": f"{self.gpu_model} ({self.gpu_vram_gb} GB)" if self.gpu_model else "",
        }

    @property
    def summary(self) -> str:
        """Compact one-line summary."""
        parts = []
        if self.cpu_model:
            parts.append(self.cpu_model.split()[-1] if " " in self.cpu_model else self.cpu_model)
        if self.ram_gb:
            parts.append(f"{self.ram_gb}GB")
        if self.gpu_model:
            gpu_short = self.gpu_model.split()[-1] if " " in self.gpu_model else self.gpu_model
            parts.append(gpu_short)
        return " · ".join(parts) if parts else self.device_type


@dataclass
class NetworkZoneInfo:
    """Network zone definition from network_zone/ YAMLs."""

    zone_id: str = ""
    zone_type: str = ""            # localhost, lan, vpn, proxy, wan
    latency_profile: str = ""      # ultra_low, low, medium, high, unpredictable
    description: str = ""

    @property
    def latency_ms(self) -> float:
        """Estimated round-trip latency in ms."""
        return {
            "ultra_low": 0.5,
            "low": 5.0,
            "medium": 30.0,
            "high": 150.0,
            "unpredictable": 500.0,
        }.get(self.latency_profile, 50.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "zone_type": self.zone_type,
            "latency_profile": self.latency_profile,
            "estimated_latency_ms": self.latency_ms,
        }


# ── M1 Loader ────────────────────────────────────────────────────────────────


class M1Loader:
    """Loads and resolves L0 M1 YAML definitions.

    Caches loaded data so repeated calls are cheap.
    """

    def __init__(self, m1_dir: str | Path = M1_DIR) -> None:
        self._m1_dir = Path(m1_dir)
        self._raw: dict[str, list[dict[str, Any]]] = {}  # namespace → [entries]

        # Resolved data
        self._machines: dict[str, MachineInfo] = {}
        self._zones: dict[str, NetworkZoneInfo] = {}
        self._engine_to_node: dict[str, str] = {}  # engine_id → node_id
        self._loaded = False

    # ── Loading ──────────────────────────────────────────────────────────────

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._load_all()
        self._resolve()
        self._loaded = True

    def _load_all(self) -> None:
        """Load all YAML files from each M1 namespace directory."""
        if not self._m1_dir.is_dir():
            _log.warning("M1 dir not found: %s", self._m1_dir)
            return

        import yaml

        for ns_dir in self._m1_dir.iterdir():
            if not ns_dir.is_dir():
                continue
            namespace = ns_dir.name
            entries: list[dict[str, Any]] = []
            for yaml_file in sorted(ns_dir.glob("*.yaml")):
                try:
                    with open(yaml_file) as f:
                        data = yaml.safe_load(f)
                    if data:
                        data["_source"] = str(yaml_file)
                        entries.append(data)
                except Exception as exc:
                    _log.debug("Failed to load %s: %s", yaml_file, exc)
            if entries:
                self._raw[namespace] = entries

        _log.info("M1Loader: loaded %d namespaces", len(self._raw))

    def _resolve(self) -> None:
        """Resolve cross-references between namespaces."""
        # 1. Load compute_node → MachineInfo
        for entry in self._raw.get("compute_node", []):
            node_id = entry.get("id", "")
            if not node_id:
                continue
            self._machines[node_id] = self._parse_machine(entry)

        # 2. Load hardware_asset → enrich machines
        for entry in self._raw.get("hardware_asset", []):
            node_ref = entry.get("node_ref", "")
            machine = self._machines.get(node_ref)
            if machine is None:
                continue
            self._enrich_hardware(machine, entry)

        # 3. Load network_zone → NetworkZoneInfo
        for entry in self._raw.get("network_zone", []):
            zone_id = entry.get("id", "")
            if not zone_id:
                continue
            self._zones[zone_id] = self._parse_zone(entry)

        # 4. Build engine → node mapping
        for entry in self._raw.get("compute_engine", []):
            engine_id = entry.get("id", "")
            node_ref = entry.get("node_ref", "")
            if engine_id and node_ref:
                self._engine_to_node[engine_id] = node_ref

    # ── Parsing ──────────────────────────────────────────────────────────────

    def _parse_machine(self, entry: dict[str, Any]) -> MachineInfo:
        return MachineInfo(
            node_id=entry.get("id", ""),
            device_type=entry.get("device_type", entry.get("type", "")),
            os=entry.get("os", ""),
            hostname=entry.get("hostname", ""),
            metadata=entry,
        )

    def _enrich_hardware(self, machine: MachineInfo, entry: dict[str, Any]) -> None:
        """Enrich a MachineInfo with a hardware_asset entry."""
        dtype = entry.get("device_type", "")
        model = entry.get("model", "")
        spec = entry.get("spec", entry.get("specification", ""))

        if dtype == "cpu":
            machine.cpu_model = model
            cores = entry.get("cores", entry.get("core_count", 0))
            machine.cpu_cores = int(cores) if cores else 0
        elif dtype in ("ram", "memory"):
            size_gb = entry.get("size_gb", entry.get("capacity_gb", 0))
            if isinstance(size_gb, (int, float)):
                machine.ram_gb = int(size_gb)
        elif dtype in ("gpu", "graphics"):
            machine.gpu_model = model
            vram = entry.get("vram_gb", entry.get("memory_gb", 0))
            if isinstance(vram, (int, float)):
                machine.gpu_vram_gb = int(vram)
        elif dtype in ("disk", "storage"):
            size = entry.get("size_gb", 0)
            if isinstance(size, (int, float)):
                machine.disk_gb = int(size)

    def _parse_zone(self, entry: dict[str, Any]) -> NetworkZoneInfo:
        return NetworkZoneInfo(
            zone_id=entry.get("id", ""),
            zone_type=entry.get("zone_type", ""),
            latency_profile=entry.get("latency_profile", ""),
            description=entry.get("description", ""),
        )

    # ── Public API ───────────────────────────────────────────────────────────

    def get_machine(self, engine_id: str) -> MachineInfo | None:
        """Get machine info for a compute engine by its ID."""
        self._ensure_loaded()
        node_id = self._engine_to_node.get(engine_id)
        if node_id is None:
            return None
        return self._machines.get(node_id)

    def get_machine_by_node(self, node_id: str) -> MachineInfo | None:
        """Get machine info by node ID."""
        self._ensure_loaded()
        return self._machines.get(node_id)

    def get_zone(self, zone_id: str) -> NetworkZoneInfo | None:
        """Get network zone info by zone ID."""
        self._ensure_loaded()
        return self._zones.get(zone_id)

    def get_engine_node_ref(self, engine_id: str) -> str | None:
        """Get the compute_node reference for an engine."""
        self._ensure_loaded()
        return self._engine_to_node.get(engine_id)

    def list_machines(self) -> dict[str, MachineInfo]:
        """All resolved machines."""
        self._ensure_loaded()
        return dict(self._machines)

    def list_zones(self) -> dict[str, NetworkZoneInfo]:
        """All network zones."""
        self._ensure_loaded()
        return dict(self._zones)

    @property
    def stats(self) -> dict[str, int]:
        self._ensure_loaded()
        return {
            "namespaces": len(self._raw),
            "engines": len(self._raw.get("compute_engine", [])),
            "machines": len(self._machines),
            "zones": len(self._zones),
            "hardware_assets": len(self._raw.get("hardware_asset", [])),
        }
