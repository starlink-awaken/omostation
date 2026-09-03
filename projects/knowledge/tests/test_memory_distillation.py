"""Tests for Memory Self-Distillation and Conflict Resolution (ADR-0200)."""

import pytest
from knowledge import KnowledgeComplex, get_knowledge_facade
from knowledge.distillation import ConflictResolver, MemoryDistillationEngine
from knowledge.models import KnowledgeDocument


def test_conflict_resolver_temporal_staleness():
    """Verify newer document overrides older document on temporal conflict."""
    resolver = ConflictResolver(similarity_threshold=0.5)
    doc_old = KnowledgeDocument(
        doc_id="card-weijian-v1",
        title="良乡医院信息化规范 (2024版)",
        body="网络安全等级保护标准为二级要求，机房温度保持在25度。",
        zone="work-weijian",
        updated_at="2024-01-01T00:00:00Z",
    )
    doc_new = KnowledgeDocument(
        doc_id="card-weijian-v2",
        title="良乡医院信息化规范 (2026版)",
        body="网络安全等级保护标准升级为三级要求，机房温度严格保持在22度以下。",
        zone="work-weijian",
        updated_at="2026-08-01T00:00:00Z",
    )

    prop = resolver.analyze_pair(doc_old, doc_new)
    assert prop is not None
    assert prop.conflict_type == "temporal_staleness"
    assert prop.target_doc_id == "card-weijian-v2"
    assert prop.conflicting_doc_id == "card-weijian-v1"
    assert prop.recommended_action == "keep_newer"


def test_conflict_resolver_trust_override():
    """Verify higher trust level document overrides lower trust level."""
    resolver = ConflictResolver(similarity_threshold=0.5)
    doc_draft = KnowledgeDocument(
        doc_id="draft-policy",
        title="科技成果转化收益分配草案",
        body="转化所得收益70%归研发团队所有，30%归单位所有。",
        zone="work-transfer",
        trust_level=1,
    )
    doc_official = KnowledgeDocument(
        doc_id="official-policy",
        title="科技成果转化收益分配正式规定",
        body="转化所得收益85%归研发团队所有，15%归单位统筹。",
        zone="work-transfer",
        trust_level=5,
    )

    prop = resolver.analyze_pair(doc_draft, doc_official)
    assert prop is not None
    assert prop.conflict_type == "policy_override"
    assert prop.target_doc_id == "official-policy"
    assert prop.conflicting_doc_id == "draft-policy"


def test_distillation_engine_batch_pipeline():
    """Verify batch memory distillation generates golden truth cards."""
    engine = MemoryDistillationEngine()
    docs = [
        KnowledgeDocument(
            doc_id="doc-1",
            title="数据资产入表规程",
            body="医疗数据资产入表需经第三方资产评估机构进行价值估算。",
            zone="work-weijian",
            trust_level=2,
            updated_at="2025-01-01T00:00:00Z",
        ),
        KnowledgeDocument(
            doc_id="doc-2",
            title="数据资产入表最新指引",
            body="医疗数据资产入表需经国家认证第三方机构与卫健委专家联合审查评估。",
            zone="work-weijian",
            trust_level=2,
            updated_at="2026-08-10T00:00:00Z",
        ),
        KnowledgeDocument(
            doc_id="doc-3",
            title="独立科研立项指南",
            body="临床科研立项需通过伦理委员会审核与学术委员会双重答辩。",
            zone="work-weijian",
            trust_level=3,
        ),
    ]

    report = engine.distill_documents(docs, auto_apply=True)
    assert report["status"] == "completed"
    assert report["scanned_docs"] == 3
    assert report["conflicts_detected"] >= 1
    # 验证提纯后的黄金卡片数量
    assert report["golden_cards_generated"] >= 2


def test_knowledge_facade_distill():
    """Verify KnowledgeComplex facade distill helper."""
    facade = get_knowledge_facade()
    docs = [
        KnowledgeDocument(doc_id="f-1", title="A", body="相同内容测试", zone="work-weijian", updated_at="2024-01-01T00:00:00Z"),
        KnowledgeDocument(doc_id="f-2", title="A", body="相同内容测试", zone="work-weijian", updated_at="2026-01-01T00:00:00Z"),
    ]
    res = facade.distill(docs)
    assert res["conflicts_detected"] == 1
