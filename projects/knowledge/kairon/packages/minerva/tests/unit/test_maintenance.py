"""Tests for knowledge maintenance — contradiction, staleness, gap analysis."""


class TestContradictionDetection:
    """Tests for contradiction detector."""

    def test_rule_based_no_contradictions(self):
        """Test rule-based detection with no opposing claims."""
        from minerva.maintenance.contradiction import detect_contradictions_rule_based

        entries = [
            {"claim": "AI is improving rapidly", "source": "src1", "file": "test1.md"},
            {"claim": "Machine learning advances continue", "source": "src2", "file": "test2.md"},
        ]
        result = detect_contradictions_rule_based(entries)
        assert len(result) == 0

    def test_rule_based_detects_opposites(self):
        """Test rule-based detection finds increase vs decrease."""
        from minerva.maintenance.contradiction import detect_contradictions_rule_based

        entries = [
            {"claim": "GPU performance increases yearly", "source": "src1", "file": "test1.md"},
            {"claim": "GPU performance decreases yearly", "source": "src2", "file": "test2.md"},
        ]
        result = detect_contradictions_rule_based(entries)
        assert len(result) >= 1
        assert result[0].severity == "MEDIUM"

    def test_rule_based_detects_supports_refutes(self):
        """Test rule-based detection finds supports vs refutes."""
        from minerva.maintenance.contradiction import detect_contradictions_rule_based

        entries = [
            {"claim": "Study supports the hypothesis", "source": "src1", "file": "test1.md"},
            {"claim": "Study refutes the hypothesis", "source": "src2", "file": "test2.md"},
        ]
        result = detect_contradictions_rule_based(entries)
        assert len(result) >= 1

    def test_contradiction_report_empty(self):
        """Test ContradictionReport with no contradictions."""
        from minerva.maintenance.contradiction import ContradictionReport

        report = ContradictionReport(total_reports_scanned=5, total_claims_checked=20)
        assert "No contradictions" in report.summary
        assert report.high_severity_count == 0

    def test_contradiction_report_with_findings(self):
        """Test ContradictionReport with contradictions."""
        from minerva.maintenance.contradiction import Contradiction, ContradictionReport

        c1 = Contradiction(
            claim_a="A increases",
            source_a="s1",
            claim_b="A decreases",
            source_b="s2",
            topic="test",
            severity="HIGH",
        )
        c2 = Contradiction(
            claim_a="B is good",
            source_a="s3",
            claim_b="B is bad",
            source_b="s4",
            topic="test2",
            severity="MEDIUM",
        )
        report = ContradictionReport(
            contradictions=[c1, c2],
            total_reports_scanned=10,
            total_claims_checked=50,
        )
        assert report.high_severity_count == 1
        assert "2 contradictions" in report.summary


class TestStalenessChecker:
    """Tests for staleness/recency checker."""

    def test_stale_entry_dataclass(self):
        """Test StaleEntry creation."""
        from minerva.maintenance.staleness import StaleEntry

        entry = StaleEntry(
            path="/tmp/test.md",
            title="Test Report",
            last_updated="2026-01-01",
            age_days=130,
            reason="Old report",
            source_count=5,
            newest_source_date="2026-01-01",
        )
        assert entry.age_days == 130
        assert entry.title == "Test Report"

    def test_staleness_report_summary(self):
        """Test StalenessReport summary generation."""
        from minerva.maintenance.staleness import StaleEntry, StalenessReport

        e1 = StaleEntry(
            path="/tmp/old.md",
            title="Old",
            last_updated="2025-06-01",
            age_days=200,
            reason="Very old",
            source_count=3,
        )
        report = StalenessReport(
            stale_entries=[e1],
            total_reports_scanned=50,
            total_stale=1,
        )
        assert "1 stale" in report.summary
        assert report.critical_count == 1  # >180d
        assert report.warning_count == 0

    def test_staleness_scanner_no_reports(self):
        """Test staleness scan with empty directory."""
        from minerva.maintenance.staleness import StalenessChecker

        checker = StalenessChecker(report_dir="/tmp/nonexistent_dir_xyz")
        report = checker.scan()
        assert report.total_reports_scanned == 0
        assert report.total_stale == 0
        assert "All up to date" in report.summary


class TestGapAnalyzer:
    """Tests for gap analyzer."""

    def test_gap_dataclass(self):
        """Test Gap creation."""
        from minerva.maintenance.gap_analyzer import Gap

        g = Gap(
            topic="test_topic",
            gap_type="source_diversity",
            description="No academic sources",
            severity="HIGH",
            recommendation="Enable arXiv",
        )
        assert g.severity == "HIGH"
        assert g.gap_type == "source_diversity"

    def test_gap_report_summary(self):
        """Test GapReport summary."""
        from minerva.maintenance.gap_analyzer import Gap, GapReport

        g1 = Gap(
            topic="t1",
            gap_type="source_diversity",
            description="Low academic ratio",
            severity="MEDIUM",
            recommendation="Add academic sources",
        )
        g2 = Gap(
            topic="t2",
            gap_type="depth",
            description="Single report",
            severity="LOW",
            recommendation="Follow up",
        )
        report = GapReport(
            gaps=[g1, g2],
            total_reports_scanned=10,
        )
        assert "2 gaps" in report.summary
        assert "source_diversity" in report.summary

    def test_source_classification(self):
        """Test source URL classification."""
        from minerva.maintenance.gap_analyzer import GapAnalyzer

        analyzer = GapAnalyzer()
        urls = [
            "https://arxiv.org/abs/1706.03762",
            "https://en.wikipedia.org/wiki/Transformer",
            "https://medium.com/some-blog/post",
            "https://github.com/user/repo",
            "https://zhuanlan.zhihu.com/p/12345",
            "https://www.example.com/page",
        ]
        dist = analyzer._classify_sources(urls)
        assert dist["academic_paper"] == 1
        assert dist["encyclopedia"] == 1
        assert dist["tech_blog"] == 1
        assert dist["code"] == 1
        assert dist["chinese_platform"] == 1
        assert dist["web"] == 1

    def test_empty_directory_no_gaps(self):
        """Test gap analysis with empty directory."""
        from minerva.maintenance.gap_analyzer import GapAnalyzer

        analyzer = GapAnalyzer(report_dir="/tmp/nonexistent_xyz")
        report = analyzer.scan()
        assert report.total_reports_scanned == 0
