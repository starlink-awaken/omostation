"""Tests for UnifiedKnowledgeRetriever facade."""

import pytest
from knowledge.retrieval import UnifiedKnowledgeRetriever
from knowledge import KnowledgeComplex, get_knowledge_facade


def test_unified_retriever_query():
    """Verify retriever query returning structured RetrievalResult."""
    retriever = UnifiedKnowledgeRetriever()
    results = retriever.retrieve("卫健委信息化等保三级方案", domain="work-weijian", limit=5)
    assert len(results) >= 1
    assert results[0].doc_id is not None
    assert results[0].zone == "work-weijian"


def test_knowledge_complex_facade_search():
    """Verify KnowledgeComplex high-level search facade."""
    complex_obj = get_knowledge_facade()
    status = complex_obj.status()
    assert status["status"] == "healthy"
    assert status["subengines"]["kairon"]["exists"] is True

    results = complex_obj.search("科技成果作价入股", domain="work-transfer")
    assert len(results) >= 1
    assert results[0].zone == "work-transfer"
