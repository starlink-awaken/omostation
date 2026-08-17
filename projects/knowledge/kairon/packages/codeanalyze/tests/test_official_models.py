"""Tests for codeanalyze.documents.official.models — PolicyDocument, PolicyGraph."""

from pathlib import Path

from codeanalyze.documents.official.models import PolicyDocument, PolicyGraph


class TestPolicyDocument:
    def test_defaults(self):
        doc = PolicyDocument(path=Path("/test/doc.pdf"))
        assert doc.level == "其他"
        assert doc.domain == "通用政策"
        assert doc.byte_size == 0
        assert doc.error is None

    def test_custom_values(self):
        doc = PolicyDocument(
            path=Path("/policy/123.pdf"),
            filename="123.pdf",
            title="Test Policy",
            doc_number="POL-001",
            issuing_org="MOE",
            level="国家级",
            domain="教育政策",
            byte_size=2048,
        )
        assert doc.title == "Test Policy"
        assert doc.level == "国家级"
        assert doc.domain == "教育政策"


class TestPolicyGraph:
    def test_empty(self):
        g = PolicyGraph()
        assert g.total_count == 0
        assert g.summary.startswith("✅")
        assert "0" in g.summary

    def test_with_documents(self):
        docs = [
            PolicyDocument(path=Path("/a.pdf"), level="国家级", domain="教育"),
            PolicyDocument(path=Path("/b.pdf"), level="省级", domain="教育"),
        ]
        g = PolicyGraph(
            documents=docs,
            level_groups={"国家级": [docs[0]], "省级": [docs[1]]},
            domain_groups={"教育": docs},
        )
        assert g.total_count == 2
        assert "国家级" in g.summary
        assert "省级" in g.summary

    def test_summary_with_relationships(self):
        g = PolicyGraph(relationships=[{"source": "a", "target": "b"}])
        assert "1 条" in g.summary
