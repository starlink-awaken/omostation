"""Tests for KnowledgeIngester."""

import pytest


class TestIngestResult:
    """Tests for IngestResult."""

    def test_ingest_result_success(self):
        from minerva.knowledge.ingest import IngestResult

        r = IngestResult(
            source="https://example.com",
            source_type="url",
            entities_extracted=5,
            relations_found=2,
            content_saved=True,
        )
        assert r.success is True
        assert r.entities_extracted == 5

    def test_ingest_result_with_errors(self):
        from minerva.knowledge.ingest import IngestResult

        r = IngestResult(
            source="invalid://",
            source_type="url",
            errors=["Extraction failed"],
        )
        assert r.success is False


class TestKnowledgeIngester:
    """Tests for KnowledgeIngester."""

    @pytest.fixture
    def ingester(self):
        from minerva.knowledge.ingest import KnowledgeIngester

        return KnowledgeIngester(
            knowledge_store=None,
            nlp_pipeline=None,
            report_dir="/tmp/minerva-test-ingest",
        )

    def test_detect_type_url(self, ingester):
        assert ingester._detect_type("https://example.com/doc") == "url"

    def test_detect_type_markdown(self, ingester):
        assert ingester._detect_type("/tmp/doc.md") == "markdown"

    def test_detect_type_pdf(self, ingester):
        assert ingester._detect_type("/tmp/doc.pdf") == "pdf"

    @pytest.mark.asyncio
    async def test_ingest_auto_detect_url(self, ingester):
        result = await ingester.ingest("https://example.com", source_type="auto")
        assert result.source_type == "url"

    @pytest.mark.asyncio
    async def test_ingest_invalid_source(self, ingester):
        result = await ingester.ingest("invalid://source", source_type="url")
        assert not result.success
        assert len(result.errors) > 0

    def test_spacy_to_entity_type(self, ingester):
        assert ingester._spacy_to_entity_type("ORG") == "Organization"
        assert ingester._spacy_to_entity_type("PERSON") == "Person"
        assert ingester._spacy_to_entity_type("UNKNOWN") == "Concept"

    @pytest.mark.asyncio
    async def test_ingest_markdown_file(self, ingester, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test Doc\n\nThis is a test document about OpenAI and Google.")
        result = await ingester.ingest(str(md_file), source_type="markdown")
        # May fail extraction since nlp is None, but shouldn't error
        assert result.source_type == "markdown"
