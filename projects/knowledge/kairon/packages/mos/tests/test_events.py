from mos.events import (
    CANONICAL_CARD_UPDATED,
    CARD_UPDATED_BRAIN,
    CARD_UPDATED_MEMORY,
    is_card_updated_event,
    normalize_card_updated_uri,
)


def test_dual_accept_card_events():
    assert is_card_updated_event(CARD_UPDATED_MEMORY)
    assert is_card_updated_event(CARD_UPDATED_BRAIN)
    assert not is_card_updated_event("bos://memory/events/other")
    assert not is_card_updated_event("")
    assert normalize_card_updated_uri(CARD_UPDATED_BRAIN) == CANONICAL_CARD_UPDATED
    assert normalize_card_updated_uri(CARD_UPDATED_MEMORY) == CANONICAL_CARD_UPDATED
