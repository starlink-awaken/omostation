"""Card knowledge event URI dual-accept (ADR-0294 migration / ADR-0372 D5)."""

from __future__ import annotations

# New canonical + legacy transition
CARD_UPDATED_MEMORY = "bos://memory/events/card_updated"
CARD_UPDATED_BRAIN = "bos://brain/events/card_updated"
CARD_UPDATED_URIS: frozenset[str] = frozenset({CARD_UPDATED_MEMORY, CARD_UPDATED_BRAIN})

# Prefer memory-domain when emitting
CANONICAL_CARD_UPDATED = CARD_UPDATED_MEMORY


def is_card_updated_event(event_type: str | None) -> bool:
    """True if event_type is a recognized card_updated URI (memory or brain)."""
    if not event_type:
        return False
    return event_type.strip() in CARD_UPDATED_URIS


def normalize_card_updated_uri(event_type: str | None) -> str | None:
    """Return canonical URI if recognized, else None."""
    if is_card_updated_event(event_type):
        return CANONICAL_CARD_UPDATED
    return None
