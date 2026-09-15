"""Tests for kairon_pipeline — importability and basic smoke tests."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false


class TestImports:
    """Verify all pipeline modules are importable."""

    def test_import_source_connectors(self):
        from kairon_pipeline.source_connectors import RawContent

        content = RawContent(uri="http://example.com", data=b"test", content_type="text/html")  # type: ignore[reportArgumentType]
        assert content.uri == "http://example.com"

    def test_import_source_registry(self):
        from kairon_pipeline.source_registry import SourceRegistry

        registry = SourceRegistry()
        assert registry is not None

    def test_import_source_priority(self):
        from kairon_pipeline.source_priority import HarvestPriorityQueue

        queue = HarvestPriorityQueue()
        assert queue is not None

    def test_import_extract_base(self):
        from kairon_pipeline.extract_base import StructuredKnowledge

        knowledge = StructuredKnowledge(uri="test", title="Test", body="content")
        assert knowledge.title == "Test"

    def test_import_quality_gate(self):
        from kairon_pipeline.quality_gate import QualityGate

        gate = QualityGate()
        assert gate is not None
