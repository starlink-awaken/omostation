"""Tests for SSOT Reporter module (reporter.py).

Covers: to_markdown, to_json, summary_line.
"""

import json

from sot_bridge.ssot_kernel.patterns.base import CheckResult, DerivationReport
from sot_bridge.ssot_kernel.reporter import Reporter


class TestReporter:
    def test_summary_line_all_passed(self):
        report = DerivationReport(
            engine_version="2.0",
            executed_at="2024-01-01",
            domain_name="test",
            total_rules=5,
            passed=5,
            blocker=0,
            error=0,
            warn=0,
            all_passed=True,
        )
        line = Reporter.summary_line(report)
        assert "test" in line
        assert "5" in line

    def test_summary_line_with_failures(self):
        report = DerivationReport(
            domain_name="test",
            total_rules=3,
            passed=1,
            blocker=1,
            error=1,
            warn=0,
            all_passed=False,
        )
        line = Reporter.summary_line(report)
        assert "1/3" in line

    def test_to_markdown_empty_report(self):
        report = DerivationReport()
        md = Reporter.to_markdown(report)
        assert isinstance(md, str)
        assert len(md) > 0
        assert "SSOT 推导报告" in md

    def test_to_markdown_with_results(self):
        report = DerivationReport(
            engine_version="2.0",
            executed_at="2024-01-01T00:00:00",
            domain_name="test",
            total_rules=2,
            passed=1,
            all_passed=False,
            results=[
                CheckResult(
                    protocol_id="R-001",
                    name="Rule 1",
                    passed=True,
                    severity="INFO",
                    details=["OK"],
                ),
                CheckResult(
                    protocol_id="R-002",
                    name="Rule 2",
                    passed=False,
                    severity="ERROR",
                    details=["Failed"],
                    fixes=["Fix it"],
                ),
            ],
        )
        md = Reporter.to_markdown(report)
        assert "R-001" in md
        assert "R-002" in md
        assert "Fix it" in md
        assert "全部通过" not in md

    def test_to_markdown_all_passed(self):
        report = DerivationReport(
            total_rules=1,
            passed=1,
            all_passed=True,
            results=[CheckResult(protocol_id="R-001", name="R1", passed=True, severity="INFO")],
        )
        md = Reporter.to_markdown(report)
        assert "全部通过" in md

    def test_to_json(self):
        report = DerivationReport(
            engine_version="2.0",
            executed_at="2024-01-01",
            domain_name="test",
            total_rules=1,
            passed=1,
            results=[
                CheckResult(protocol_id="R-001", name="R1", passed=True, severity="INFO"),
            ],
        )
        json_str = Reporter.to_json(report)
        data = json.loads(json_str)
        assert data["engine_version"] == "2.0"
        assert data["summary"]["total"] == 1
        assert data["summary"]["passed"] == 1
        assert len(data["results"]) == 1
        assert data["results"][0]["protocol_id"] == "R-001"

    def test_to_json_empty(self):
        report = DerivationReport()
        json_str = Reporter.to_json(report)
        data = json.loads(json_str)
        assert data["summary"]["total"] == 0
        assert data["results"] == []

    def test_report_property_summary_line(self):
        """Test DerivationReport.summary_line property."""
        report = DerivationReport(passed=3, blocker=1, error=2, warn=0)
        line = report.summary_line
        assert "3" in line
        assert "1" in line
