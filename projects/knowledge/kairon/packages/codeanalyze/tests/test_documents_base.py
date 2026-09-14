"""Tests for codeanalyze.documents.base — DocumentAnalysis, DocAnalyzer."""

from pathlib import Path

import pytest
from codeanalyze.documents.base import DocAnalyzer, DocumentAnalysis


class TestDocumentAnalysis:
    def test_defaults(self):
        da = DocumentAnalysis(path=Path("/test/doc.md"))
        assert da.format == "unknown"
        assert da.pages == 0
        assert da.word_count == 0
        assert da.sections == []
        assert da.tables == []
        assert da.entities == []
        assert da.relations == []
        assert da.error is None

    def test_custom_values(self):
        da = DocumentAnalysis(
            path=Path("/doc.pdf"),
            format="pdf",
            pages=5,
            word_count=1000,
            sections=[{"title": "Intro"}],
            error=None,
        )
        assert da.format == "pdf"
        assert da.pages == 5
        assert da.word_count == 1000


class TestDocAnalyzer:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            DocAnalyzer()  # type: ignore[abstract]
