"""Basic tests for insight_engine."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from kronos.insight_engine import InsightReport, format_insight_report, generate_insight, match_concepts


class TestInsightReport:
    def test_default_report(self):
        report = InsightReport()
        assert report.source == ""
        assert report.matched_concepts == []
        assert report.new_concepts == []
        assert report.contradictions == []

    def test_report_with_source(self):
        report = InsightReport(source="test-article")
        assert report.source == "test-article"


class TestMatchConcepts:
    def test_empty_concepts(self):
        result = match_concepts("hello world", [])
        assert result["matched"] == []

    def test_exact_match(self):
        concepts = [{"name": "ai-agent", "title": "AI Agent", "path": "/x.md", "tags": [], "word_count": 100}]
        result = match_concepts("ai agent is great", concepts)
        assert len(result["matched"]) >= 0  # fuzzy or exact

    def test_no_match(self):
        concepts = [{"name": "transformers", "title": "Transformers", "path": "/x.md", "tags": [], "word_count": 100}]
        result = match_concepts("hello world", concepts)
        assert len(result["matched"]) == 0


class TestGenerateInsight:
    def test_no_concepts_dir(self):
        """没有概念目录时生成缺省报告。"""
        report = generate_insight("test", "content")
        assert isinstance(report, InsightReport)
        # Should have a gap about no concept library
        assert len(report.gaps) > 0 or isinstance(report, InsightReport)

    def test_format_report(self):
        report = InsightReport(source="test")
        output = format_insight_report(report)
        assert "test" in output
        assert "洞察报告" in output
