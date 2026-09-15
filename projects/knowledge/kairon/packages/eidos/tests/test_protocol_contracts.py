# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false
from __future__ import annotations

from eidos.protocols.contracts import validate_contract_payload
from eidos.types import Fact, KnowledgeCard


def test_knowledge_card_payload_contract_accepts_serialized_knowledge_card():
    card = KnowledgeCard(
        id="kc-1",
        title="Title",
        content="Body",
        source="unit-test",
        source_type="test",
        schema_type="KnowledgeCard",
        tags=["alpha", "beta"],
    )

    assert validate_contract_payload("knowledge-card-v0.3", card.to_dict()) == []


def test_fact_payload_contract_accepts_serialized_fact():
    fact = Fact(id="f-1", subject="A", predicate="relates_to", object="B", confidence=0.9)

    assert validate_contract_payload("fact-v0.3", fact.to_dict()) == []
