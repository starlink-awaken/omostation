"""Unified Surface Protocol (USP) v1 — core protocol types.

Design principles:
  - Pure data classes (no I/O, no side-effects)
  - JSON-serialisable out of the box (via .to_dict() / from_dict())
  - Strict enum vocabulary — surfaces must not accept unknown values
  - Forward-compatible: unknown extra keys in from_dict() are silently ignored

Schema version: usp/v1
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class SurfaceDomain(StrEnum):
    """Originating business domain for a surface card payload."""

    GOVERNANCE = "governance"
    AGENT = "agent"
    KNOWLEDGE = "knowledge"
    DELIVERY = "delivery"
    COMPUTE = "compute"
    OBSERVABILITY = "observability"
    SYSTEM = "system"
    # Catch-all for future domains — surface renderers should display as-is
    UNKNOWN = "unknown"


class CardType(StrEnum):
    """Enumeration of supported card primitive types."""

    METRIC_GRID = "metric_grid"
    DATA_TABLE = "data_table"
    LOG_STREAM = "log_stream"
    DAG_GRAPH = "dag_graph"
    ACTION_PANEL = "action_panel"


class RefreshMode(StrEnum):
    """How the receiving surface should handle subsequent updates."""

    # Render once, surface stays static until next full push
    STATIC = "static"
    # Surface polls the origin for updates at its own cadence
    POLL = "poll"
    # Origin will push incremental diffs via streaming channel
    STREAM = "stream"
    # Surface decides autonomously
    AUTO = "auto"


# ---------------------------------------------------------------------------
# SurfaceEnvelope
# ---------------------------------------------------------------------------


class SurfaceEnvelope:
    """Top-level container exchanged between domain logic and surface renderers.

    Every domain that wants to push data to any surface (TUI, Web, API, MCP)
    must wrap its payload in a SurfaceEnvelope.  Surfaces must not accept raw
    domain objects directly.

    Attributes:
        schema:       Protocol schema version (always "usp/v1" for this module).
        envelope_id:  UUID4 assigned at creation time (or supplied).
        domain:       Originating SurfaceDomain.
        card_type:    Which card primitive to render.
        refresh_mode: How the surface should refresh after receiving this.
        title:        Human-readable title shown in all surface renderers.
        payload:      Domain-specific structured payload (card primitive instance
                      serialised to dict, or raw dict for forward-compat).
        ts:           Unix epoch (float) when the envelope was created.
        ttl:          Optional time-to-live in seconds (None = no expiry).
        tags:         Optional free-form key/value labels.
    """

    SCHEMA = "usp/v1"

    __slots__ = (
        "schema",
        "envelope_id",
        "domain",
        "card_type",
        "refresh_mode",
        "title",
        "payload",
        "ts",
        "ttl",
        "tags",
    )

    def __init__(
        self,
        *,
        domain: SurfaceDomain | str,
        card_type: CardType | str,
        title: str,
        payload: dict[str, Any],
        refresh_mode: RefreshMode | str = RefreshMode.STATIC,
        envelope_id: str | None = None,
        ts: float | None = None,
        ttl: float | None = None,
        tags: dict[str, str] | None = None,
    ) -> None:
        self.schema = self.SCHEMA
        self.envelope_id = envelope_id or str(uuid.uuid4())
        self.domain = SurfaceDomain(domain) if isinstance(domain, str) else domain
        self.card_type = CardType(card_type) if isinstance(card_type, str) else card_type
        self.refresh_mode = RefreshMode(refresh_mode) if isinstance(refresh_mode, str) else refresh_mode
        self.title = title
        self.payload = payload
        self.ts = ts if ts is not None else time.time()
        self.ttl = ttl
        self.tags = dict(tags) if tags else {}

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of this envelope."""
        out: dict[str, Any] = {
            "schema": self.schema,
            "envelope_id": self.envelope_id,
            "domain": self.domain.value,
            "card_type": self.card_type.value,
            "refresh_mode": self.refresh_mode.value,
            "title": self.title,
            "payload": self.payload,
            "ts": self.ts,
            "tags": self.tags,
        }
        if self.ttl is not None:
            out["ttl"] = self.ttl
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SurfaceEnvelope:
        """Reconstruct an envelope from a dict (e.g. from JSON.loads()).

        Unknown extra keys are silently ignored for forward-compatibility.
        Raises ValueError if required keys are absent or enums are invalid.
        """
        required = ("domain", "card_type", "title", "payload")
        missing = [k for k in required if k not in data]
        if missing:
            raise ValueError(f"SurfaceEnvelope.from_dict: missing required keys: {missing}")
        return cls(
            domain=data["domain"],
            card_type=data["card_type"],
            refresh_mode=data.get("refresh_mode", RefreshMode.STATIC),
            title=data["title"],
            payload=data["payload"],
            envelope_id=data.get("envelope_id"),
            ts=data.get("ts"),
            ttl=data.get("ttl"),
            tags=data.get("tags"),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def is_expired(self, now: float | None = None) -> bool:
        """Return True if this envelope has a TTL and it has elapsed."""
        if self.ttl is None:
            return False
        t = now if now is not None else time.time()
        return (t - self.ts) > self.ttl

    def __repr__(self) -> str:
        return (
            f"SurfaceEnvelope("
            f"id={self.envelope_id!r}, "
            f"domain={self.domain.value!r}, "
            f"card_type={self.card_type.value!r}, "
            f"title={self.title!r}"
            f")"
        )

    def __eq__(self, other: object) -> bool:
        if not hasattr(other, "envelope_id"):
            return NotImplemented
        return self.envelope_id == other.envelope_id  # type: ignore[union-attr]

    def __hash__(self) -> int:
        return hash(self.envelope_id)
