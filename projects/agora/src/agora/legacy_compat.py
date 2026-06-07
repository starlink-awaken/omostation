"""Centralized compatibility constants for historical route and URI aliases."""

from __future__ import annotations

LEGACY_PERSONA_BRIDGE_SERVICE = "sot-bridge-persona"
LEGACY_PERSONA_BRIDGE_ALIASES = {
    "sharedbrain-bridge": LEGACY_PERSONA_BRIDGE_SERVICE,
    "sot-bridge": LEGACY_PERSONA_BRIDGE_SERVICE,
}

LEGACY_PERSONA_BRIDGE_URI_PREFIX = "bos://persona/sharedbrain-bridge/"
CANONICAL_PERSONA_BRIDGE_URI_PREFIX = f"bos://persona/{LEGACY_PERSONA_BRIDGE_SERVICE}/"
