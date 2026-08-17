"""Tests for Formalizer — 符号化引擎 (Phase 1+2)"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from ontoderive.reasoners.formalize import (
    Formalizer,
    FormalKnowledge,
    SymbolicEntity,
    SymbolicFact,
    SymbolicInference,
)


class TestSymbolicTypes:
    def test_fact_create(self):
        f = SymbolicFact(id="D-F1", description="测试", value="100")
        assert f.id == "D-F1"
        assert f.confidence == 0.90
        assert f.category == "data"

    def test_entity_create(self):
        e = SymbolicEntity(id="ORG-Test", name="测试组织", entity_type="ORG")
        assert e.id == "ORG-Test"
        assert e.meta_type == "DOMAIN"

    def test_inference_create(self):
        inf = SymbolicInference(id="INF-L1", title="测试推论", derives_from=["D-F1"])
        assert inf.id == "INF-L1"
        assert inf.derives_from == ["D-F1"]

    def test_knowledge_create(self):
        kb = FormalKnowledge()
        assert kb.facts == []
        assert kb.entities == []
        assert kb.inferences == []


SAMPLE_MD = """
中关村科技园区有120家企业入驻，80次技术对接。
与30所高校合作，转化率15%。50名技术经理人。
清华大学与北京创新平台合作。
成立于2015年，投资5亿元。
"""


class TestFormalizer:
    def test_create(self):
        fz = Formalizer()
        assert fz is not None

    def test_extract_rule_only(self):
        fz = Formalizer()
        kb = fz.extract_from_text(SAMPLE_MD, mode="rule_only")
        assert isinstance(kb, FormalKnowledge)

    def test_extract_empty(self):
        fz = Formalizer()
        kb = fz.extract_from_text("", mode="rule_only")
        assert isinstance(kb, FormalKnowledge)

    def test_to_markdown(self):
        fz = Formalizer()
        kb = fz.extract_from_text(SAMPLE_MD, mode="rule_only")
        md = fz.to_markdown(kb)
        assert isinstance(md, str)
        assert len(md) > 0

    def test_smart_chunk(self):
        fz = Formalizer()
        chunks = fz._smart_chunk("a" * 5000, max_chars=2000)
        assert len(chunks) >= 2

    def test_smart_chunk_small(self):
        fz = Formalizer()
        chunks = fz._smart_chunk("测试文本", max_chars=2000)
        assert len(chunks) == 1

    def test_validate_empty(self):
        fz = Formalizer()
        kb = FormalKnowledge()
        result = fz._validate(kb)
        assert result is None or isinstance(result, list)

    def test_build_abox_tbox(self):
        fz = Formalizer()
        kb = fz._rule_extract(SAMPLE_MD)
        fz._build_abox_tbox(kb)
        assert hasattr(kb, "abox")
        assert hasattr(kb, "tbox")
