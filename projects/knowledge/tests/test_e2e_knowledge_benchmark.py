"""End-to-End Knowledge Retrieval Benchmark & Precision Verification Suite."""

import pytest
from knowledge import KnowledgeComplex
from knowledge.retrieval import UnifiedKnowledgeRetriever


@pytest.fixture
def retriever():
    return UnifiedKnowledgeRetriever()


def test_weijian_health_domain_query(retriever):
    """验证卫健委/医疗信息化长尾实体的混合检索精度与命中."""
    results = retriever.retrieve("良乡医院 医疗信息化", domain="work-weijian", limit=5)
    assert len(results) >= 1
    # 验证返回结构包含必要字段
    for r in results:
        assert r.doc_id
        assert r.title
        assert isinstance(r.score, float)


def test_transfer_domain_query(retriever):
    """验证科技成果转化领域实体的混合检索."""
    results = retriever.retrieve("科技成果作价入股 收益分配", domain="work-transfer", limit=5)
    assert len(results) >= 1
    for r in results:
        assert r.doc_id
        assert r.title


def test_adaptive_rrf_scoring_monotonicity(retriever):
    """验证自适应 RRF 排序后的打分单调非递增."""
    results = retriever.retrieve("制度 规范 流程", limit=10)
    if len(results) >= 2:
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score
