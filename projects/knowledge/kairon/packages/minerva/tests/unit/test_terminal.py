"""Tests for terminal output utilities."""

from unittest.mock import patch


class TestPrintBanner:
    """Tests for print_banner()."""

    @patch("minerva.utils.terminal.RICH_AVAILABLE", True)
    def test_print_banner_rich_available(self):
        """print_banner renders a rich Panel when RICH_AVAILABLE is True."""
        from minerva.utils.terminal import console, print_banner

        # Mock console to avoid actual terminal output and verify it was called
        with patch.object(console, "print") as mock_print:
            print_banner()
            # console.print is called at least twice: empty line, panel, empty line
            assert mock_print.call_count >= 2

    @patch("minerva.utils.terminal.RICH_AVAILABLE", False)
    def test_print_banner_rich_unavailable(self, capsys):
        """print_banner falls back to plain print when RICH_AVAILABLE is False."""
        from minerva.utils.terminal import print_banner

        print_banner()
        captured = capsys.readouterr()
        assert "Minerva Deep Research" in captured.out


class TestPrintSummaryTable:
    """Tests for print_summary_table()."""

    @patch("minerva.utils.terminal.RICH_AVAILABLE", False)
    def test_print_summary_table_fallback(self, capsys):
        """print_summary_table prints plain text summary when rich unavailable."""
        from minerva.utils.terminal import print_summary_table

        print_summary_table(
            stage_timings={"search": 1.5, "analyze": 2.0},
            quality_score="85",
            source_count=12,
            entity_count=5,
            total_time=3.5,
        )
        captured = capsys.readouterr()
        assert "Total: 3.5s" in captured.out
        assert "Sources: 12" in captured.out
        assert "Entities: 5" in captured.out

    @patch("minerva.utils.terminal.RICH_AVAILABLE", True)
    def test_print_summary_table_rich_available(self):
        """print_summary_table renders a rich Table when RICH_AVAILABLE is True."""
        from minerva.utils.terminal import console, print_summary_table

        with patch.object(console, "print") as mock_print:
            print_summary_table(
                stage_timings={"search": 1.5, "analyze": 2.0},
                quality_score="85",
                source_count=12,
                entity_count=5,
                total_time=3.5,
            )
            # console.print should be called (table + header + footer)
            assert mock_print.call_count >= 1
