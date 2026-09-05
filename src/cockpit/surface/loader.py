"""Declarative Card Extension SDK & Manifest Loader (DCE SDK v1).

Enables subprojects and external domains to declare UI cards and actions
via surface.manifest.yaml without modifying Cockpit core code.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from cockpit.surface.cards import (
    ActionButton,
    ActionPanelCard,
    DagEdge,
    DagGraphCard,
    DagNode,
    DataTableCard,
    LogStreamCard,
    MetricCell,
    MetricGridCard,
    TableColumn,
)
from cockpit.surface.protocol import CardType, RefreshMode, SurfaceDomain, SurfaceEnvelope

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "surface-manifest/v1"

# Domain alias normalizer
DOMAIN_ALIASES: dict[str, SurfaceDomain] = {
    "governance": SurfaceDomain.GOVERNANCE,
    "agent": SurfaceDomain.AGENT,
    "swarm": SurfaceDomain.AGENT,
    "knowledge": SurfaceDomain.KNOWLEDGE,
    "memory": SurfaceDomain.KNOWLEDGE,
    "delivery": SurfaceDomain.DELIVERY,
    "workflow": SurfaceDomain.DELIVERY,
    "execution": SurfaceDomain.DELIVERY,
    "compute": SurfaceDomain.COMPUTE,
    "observability": SurfaceDomain.OBSERVABILITY,
    "overview": SurfaceDomain.OBSERVABILITY,
    "system": SurfaceDomain.SYSTEM,
    "user": SurfaceDomain.UNKNOWN,
    "business": SurfaceDomain.UNKNOWN,
}


class ManifestError(ValueError):
    """Raised when a surface manifest is invalid or malformed."""


@dataclass
class CardManifest:
    """Parsed representation of a single card declared in a manifest."""

    id: str
    type: CardType
    title: str
    refresh_interval_ms: int = 5000
    source_uri: str = ""
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtensionManifest:
    """Top-level manifest representing a declarative card extension."""

    schema_version: str
    extension_id: str
    domain: str
    title: str
    description: str = ""
    refresh_interval_ms: int = 10000
    cards: list[CardManifest] = field(default_factory=list)
    source_path: Path | None = None


def normalize_domain(domain_str: str) -> SurfaceDomain:
    """Normalize a domain string to a SurfaceDomain enum value."""
    key = domain_str.strip().lower()
    if key in DOMAIN_ALIASES:
        return DOMAIN_ALIASES[key]
    try:
        return SurfaceDomain(key)
    except ValueError:
        return SurfaceDomain.UNKNOWN


def parse_manifest_dict(data: dict[str, Any], source_path: Path | None = None) -> ExtensionManifest:
    """Parse and validate a dictionary against surface-manifest/v1 schema."""
    if not isinstance(data, dict):
        raise ManifestError("Manifest root must be a mapping/dict")

    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ManifestError(
            f"Unsupported schema_version: '{version}'. Expected '{SCHEMA_VERSION}'"
        )

    extension_id = data.get("extension_id")
    if not extension_id or not isinstance(extension_id, str):
        raise ManifestError("Manifest missing required non-empty string 'extension_id'")

    domain = data.get("domain")
    if not domain or not isinstance(domain, str):
        raise ManifestError("Manifest missing required non-empty string 'domain'")

    title = data.get("title") or extension_id
    description = data.get("description", "")
    refresh_interval_ms = int(data.get("refresh_interval_ms", 10000))

    raw_cards = data.get("cards")
    if raw_cards is None or not isinstance(raw_cards, list):
        raise ManifestError("Manifest missing required 'cards' list")

    parsed_cards: list[CardManifest] = []
    for idx, card_item in enumerate(raw_cards):
        if not isinstance(card_item, dict):
            raise ManifestError(f"Card item at index {idx} must be a dict")

        card_id = card_item.get("id")
        if not card_id or not isinstance(card_id, str):
            raise ManifestError(f"Card item at index {idx} missing required string 'id'")

        type_str = card_item.get("type")
        if not type_str or not isinstance(type_str, str):
            raise ManifestError(f"Card '{card_id}' missing required string 'type'")

        try:
            card_type = CardType(type_str.lower().strip())
        except ValueError:
            raise ManifestError(
                f"Card '{card_id}' has unsupported type '{type_str}'. Allowed: {[t.value for t in CardType]}"
            )

        card_title = card_item.get("title") or card_id
        card_refresh = int(card_item.get("refresh_interval_ms", refresh_interval_ms))
        source_uri = card_item.get("source_uri", "")

        raw_data = {
            k: v for k, v in card_item.items()
            if k not in ("id", "type", "title", "refresh_interval_ms", "source_uri")
        }

        parsed_cards.append(
            CardManifest(
                id=card_id,
                type=card_type,
                title=card_title,
                refresh_interval_ms=card_refresh,
                source_uri=source_uri,
                raw_data=raw_data,
            )
        )

    return ExtensionManifest(
        schema_version=version,
        extension_id=extension_id,
        domain=domain,
        title=title,
        description=description,
        refresh_interval_ms=refresh_interval_ms,
        cards=parsed_cards,
        source_path=source_path,
    )


def load_manifest_file(path: Path | str) -> ExtensionManifest:
    """Load and parse a surface.manifest.yaml file."""
    p = Path(path)
    if not p.exists():
        raise ManifestError(f"Manifest file not found: {p}")
    try:
        content = p.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
    except Exception as exc:
        raise ManifestError(f"Failed to read or parse YAML from {p}: {exc}") from exc

    return parse_manifest_dict(data, source_path=p)


def manifest_card_to_envelope(
    card: CardManifest,
    domain: SurfaceDomain | str,
    extension_id: str = "",
) -> SurfaceEnvelope:
    """Convert a CardManifest into a canonical SurfaceEnvelope."""
    surf_domain = domain if isinstance(domain, SurfaceDomain) else normalize_domain(domain)
    envelope_id = f"ext::{extension_id}::{card.id}" if extension_id else f"ext::{card.id}"

    card_data = card.raw_data.get("static_data") or card.raw_data

    payload: dict[str, Any] = {}
    if card.type == CardType.METRIC_GRID:
        metrics_raw = card_data.get("metrics", [])
        cells = [
            MetricCell(
                label=m.get("label", ""),
                value=m.get("value", "-"),
                unit=m.get("unit", ""),
                trend=m.get("trend", "neutral"),
                warn_threshold=m.get("warn_threshold"),
                description=m.get("description", ""),
            )
            for m in metrics_raw
            if isinstance(m, dict)
        ]
        grid = MetricGridCard(cells=cells)
        payload = grid.to_dict()

    elif card.type == CardType.DATA_TABLE:
        cols_raw = card_data.get("columns", [])
        cols = [
            TableColumn(
                key=c.get("key", f"col_{i}"),
                label=c.get("label", c.get("key", f"col_{i}")),
                sortable=bool(c.get("sortable", True)),
                width=int(c.get("width", 0)),
                align=c.get("align", "left"),
            )
            if isinstance(c, dict) else TableColumn(key=str(c), label=str(c))
            for i, c in enumerate(cols_raw)
        ]
        rows = card_data.get("rows", [])
        table = DataTableCard(columns=cols, rows=rows)
        payload = table.to_dict()

    elif card.type == CardType.ACTION_PANEL:
        actions_raw = card_data.get("actions", [])
        buttons = [
            ActionButton(
                id=a.get("id", f"btn-{idx}"),
                label=a.get("label", "Action"),
                variant=a.get("variant", "secondary"),
                description=a.get("description", ""),
                confirm=bool(a.get("confirm", False)),
                payload=a.get("payload", {}),
                disabled=bool(a.get("disabled", False)),
                disabled_reason=a.get("disabled_reason", ""),
            )
            for idx, a in enumerate(actions_raw)
            if isinstance(a, dict)
        ]
        panel = ActionPanelCard(
            actions=buttons,
            title=card.title,
            description=card_data.get("description", ""),
        )
        payload = panel.to_dict()

    elif card.type == CardType.LOG_STREAM:
        lines = card_data.get("lines", [])
        stream = LogStreamCard(lines=lines, title=card.title)
        payload = stream.to_dict()

    elif card.type == CardType.DAG_GRAPH:
        nodes = [DagNode(**n) for n in card_data.get("nodes", [])]
        edges = [DagEdge(**e) for e in card_data.get("edges", [])]
        graph = DagGraphCard(nodes=nodes, edges=edges, title=card.title)
        payload = graph.to_dict()

    else:
        payload = card_data

    return SurfaceEnvelope(
        envelope_id=envelope_id,
        domain=surf_domain,
        card_type=card.type,
        refresh_mode=RefreshMode.POLL if card.refresh_interval_ms > 0 else RefreshMode.STATIC,
        title=card.title,
        payload=payload,
        tags={"extension_id": extension_id, "source_uri": card.source_uri},
    )


def scan_manifests(
    search_dirs: list[Path | str],
    filename_patterns: tuple[str, ...] = ("surface.manifest.yaml", "surface.manifest.yml"),
) -> list[ExtensionManifest]:
    """Scan directories for surface manifests with fail-safe circuit breaker."""
    discovered: list[ExtensionManifest] = []
    for s_dir in search_dirs:
        root_path = Path(s_dir)
        if not root_path.is_dir():
            continue
        for pattern in filename_patterns:
            for manifest_file in root_path.glob(f"**/{pattern}"):
                parts = manifest_file.parts
                if any(p.startswith(".") or p in ("node_modules", "vendor", "dist", "build") for p in parts[:-1]):
                    continue
                try:
                    ext = load_manifest_file(manifest_file)
                    discovered.append(ext)
                    logger.info("Loaded surface manifest: %s from %s", ext.extension_id, manifest_file)
                except Exception as exc:
                    logger.warning("Failed to load manifest at %s (skipped): %s", manifest_file, exc)
    return discovered


class ExtensionRegistry:
    """In-memory registry managing loaded declarative surface extensions."""

    _instance: ExtensionRegistry | None = None

    def __init__(self) -> None:
        self._extensions: dict[str, ExtensionManifest] = {}

    @classmethod
    def default(cls) -> ExtensionRegistry:
        if cls._instance is None:
            cls._instance = ExtensionRegistry()
        return cls._instance

    def register(self, manifest: ExtensionManifest) -> None:
        self._extensions[manifest.extension_id] = manifest

    def get_extension(self, extension_id: str) -> ExtensionManifest | None:
        return self._extensions.get(extension_id)

    def get_all(self) -> list[ExtensionManifest]:
        return list(self._extensions.values())

    def get_envelopes_for_domain(self, domain: SurfaceDomain | str) -> list[SurfaceEnvelope]:
        target_domain = domain if isinstance(domain, SurfaceDomain) else normalize_domain(domain)
        envelopes: list[SurfaceEnvelope] = []
        for ext in self._extensions.values():
            ext_norm_domain = normalize_domain(ext.domain)
            if ext_norm_domain == target_domain or ext.domain.lower() == str(domain).lower():
                for card in ext.cards:
                    envelopes.append(
                        manifest_card_to_envelope(card, target_domain, extension_id=ext.extension_id)
                    )
        return envelopes

    def discover(self, search_paths: list[Path | str]) -> int:
        manifests = scan_manifests(search_paths)
        for m in manifests:
            self.register(m)
        return len(manifests)

    def clear(self) -> None:
        self._extensions.clear()
