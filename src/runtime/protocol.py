"""L0 Protocol Registry — load protocol definitions from the YAML SSOT."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml


ProtocolCategory = Literal[
    "agent-communication",
    "model-access",
    "service-discovery",
    "state-sync",
    "identity-auth",
    "data-exchange",
    "orchestration",
]

ProtocolStatus = Literal["active", "draft", "deprecated", "planned"]


@dataclass
class ProtocolEntry:
    """A single protocol in the L0 weave."""

    name: str
    version: str
    category: ProtocolCategory
    status: ProtocolStatus
    description: str
    spec_url: str | None = None
    port_range: str | None = None
    transport: list[str] = field(default_factory=lambda: ["stdio", "http"])
    implementations: list[str] = field(default_factory=list)
    notes: str = ""


def registry_path() -> Path:
    """Path to the YAML protocol registry file."""
    return Path(__file__).parent.parent.parent / "protocols" / "L0-registry.yaml"


def _normalize_protocol(raw: dict) -> ProtocolEntry:
    """Map a YAML protocol entry into a typed runtime object."""
    implementations = raw.get("implementations") or []
    transport = raw.get("transport") or ["stdio", "http"]
    notes = raw.get("notes") or ""
    port_range = raw.get("port_range")
    if port_range in ("", None):
        port_range = None

    return ProtocolEntry(
        name=str(raw["name"]),
        version=str(raw["version"]),
        category=raw["category"],
        status=raw["status"],
        description=str(raw["description"]),
        spec_url=raw.get("spec_url"),
        port_range=port_range,
        transport=[str(item) for item in transport],
        implementations=[str(item) for item in implementations if item],
        notes=str(notes),
    )


def load_protocols(path: Path | None = None) -> list[ProtocolEntry]:
    """Load protocols from the YAML SSOT."""
    path = path or registry_path()
    with path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f) or {}

    protocols = payload.get("protocols")
    if not isinstance(protocols, list):
        raise ValueError(f"Invalid L0 protocol registry: missing protocol list in {path}")

    return [_normalize_protocol(raw) for raw in protocols]


L0_PROTOCOLS: list[ProtocolEntry] = load_protocols()


def get_protocol(name: str) -> ProtocolEntry | None:
    """Find a protocol by name."""
    for protocol in L0_PROTOCOLS:
        if protocol.name.lower() == name.lower():
            return protocol
    return None


def by_category(cat: ProtocolCategory) -> list[ProtocolEntry]:
    """Filter protocols by category."""
    return [protocol for protocol in L0_PROTOCOLS if protocol.category == cat]


def active_protocols() -> list[ProtocolEntry]:
    """Return only active protocols."""
    return [protocol for protocol in L0_PROTOCOLS if protocol.status == "active"]
