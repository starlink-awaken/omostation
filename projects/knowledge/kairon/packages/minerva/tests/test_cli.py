"""Tests for minerva.cli — entry point for deep research commands.

Covers build_parser() (argparse), main() command dispatch, _run_results
sub-commands (list/show/delete/stats), and _run_audit (JSON + text output).
Heavy sub-commands (_run_research, _run_init, _run_check, _run_maintenance)
are tested lightly via main() mocking since they require external services.
"""

from __future__ import annotations

import argparse
import json
import sys
from unittest.mock import MagicMock, patch

import pytest
from minerva.cli import (
    _run_audit,
    _run_results,
    build_parser,
    main,
)


def _run_main(argv):
    """Helper: run main() with patched sys.argv."""
    with patch.object(sys, "argv", ["minerva"] + argv):
        return main()


# ── build_parser ────────────────────────────────────────────────


class TestBuildParser:
    def test_returns_argument_parser(self):
        parser = build_parser()
        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.prog == "minerva"

    def test_top_level_json_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--json", "init"])
        assert args.json is True

    def test_research_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["research", "what is AI?"])
        assert args.command == "research"
        assert args.query == "what is AI?"

    def test_research_level_default(self):
        parser = build_parser()
        args = parser.parse_args(["research", "test"])
        assert args.level == "auto"

    def test_research_level_choices(self):
        parser = build_parser()
        for level in ("auto", "L0", "L1", "L2", "L3", "L4"):
            args = parser.parse_args(["research", "test", "--level", level])
            assert args.level == level

    def test_research_max_cost_default(self):
        parser = build_parser()
        args = parser.parse_args(["research", "test"])
        assert args.max_cost == 1.0

    def test_research_max_cost_override(self):
        parser = build_parser()
        args = parser.parse_args(["research", "test", "--max-cost", "2.5"])
        assert args.max_cost == 2.5

    def test_research_to_kos(self):
        parser = build_parser()
        args = parser.parse_args(["research", "test", "--to-kos"])
        assert args.to_kos is True

    def test_research_template_choices(self):
        parser = build_parser()
        for tpl in ("competitor-analysis", "literature-review", "policy-audit"):
            args = parser.parse_args(["research", "--template", tpl, "--target", "X"])
            assert args.template == tpl

    def test_research_eidos_output(self):
        parser = build_parser()
        args = parser.parse_args(["research", "test", "--eidos-output", "/tmp/out"])
        assert args.eidos_output == "/tmp/out"

    def test_research_vault_sink(self):
        parser = build_parser()
        args = parser.parse_args(["research", "test", "--vault-sink"])
        assert args.vault_sink is True

    def test_init_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["init"])
        assert args.command == "init"

    def test_mcp_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["mcp"])
        assert args.command == "mcp"

    def test_check_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["check"])
        assert args.command == "check"

    def test_daemon_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["daemon"])
        assert args.command == "daemon"

    def test_web_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["web"])
        assert args.command == "web"

    def test_results_list_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["results", "list"])
        assert args.command == "results"
        assert args.results_cmd == "list"

    def test_results_show_requires_id(self):
        parser = build_parser()
        args = parser.parse_args(["results", "show", "abc123"])
        assert args.results_cmd == "show"
        assert args.result_id == "abc123"

    def test_results_delete_requires_id(self):
        parser = build_parser()
        args = parser.parse_args(["results", "delete", "xyz789"])
        assert args.results_cmd == "delete"
        assert args.result_id == "xyz789"

    def test_results_stats(self):
        parser = build_parser()
        args = parser.parse_args(["results", "stats"])
        assert args.results_cmd == "stats"

    def test_audit_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["audit"])
        assert args.command == "audit"
        assert args.limit == 20
        assert args.action == ""
        assert args.json is False

    def test_audit_limit(self):
        parser = build_parser()
        args = parser.parse_args(["audit", "--limit", "50"])
        assert args.limit == 50

    def test_audit_action_filter(self):
        parser = build_parser()
        args = parser.parse_args(["audit", "--action", "research.run"])
        assert args.action == "research.run"

    def test_maintenance_action_default(self):
        parser = build_parser()
        args = parser.parse_args(["maintenance"])
        assert args.command == "maintenance"
        assert args.action == "all"
        assert args.path == "."
        assert args.older_than_hours == 24

    def test_maintenance_action_choices(self):
        parser = build_parser()
        for action in ("all", "staleness", "gaps", "contradictions", "cleanup-temp"):
            args = parser.parse_args(["maintenance", "--action", action])
            assert args.action == action

    def test_maintenance_path_override(self):
        parser = build_parser()
        args = parser.parse_args(["maintenance", "--path", "/tmp/reports"])
        assert args.path == "/tmp/reports"

    def test_maintenance_older_than_hours(self):
        parser = build_parser()
        args = parser.parse_args(["maintenance", "--older-than-hours", "48"])
        assert args.older_than_hours == 48


# ── _run_results ──────────────────────────────────────────────


class TestRunResultsList:
    def test_empty(self, monkeypatch, capsys):
        monkeypatch.setattr("minerva.persistence.list_results", lambda limit=20: [])
        args = MagicMock()
        args.results_cmd = "list"
        args.json = False
        result = _run_results(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "No saved research results found." in captured.out

    def test_list_text(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "minerva.persistence.list_results",
            lambda limit=20: [
                {
                    "id": "123_q",
                    "query": "What is AI?",
                    "has_report": True,
                    "timestamp": "2026-07-26T00:00:00Z",
                    "level": "L2",
                    "quality_score": 85,
                    "source_count": 10,
                    "cost_usd": 0.5,
                }
            ],
        )
        args = MagicMock()
        args.results_cmd = "list"
        args.json = False
        result = _run_results(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "123_q" in captured.out
        assert "What is AI?" in captured.out
        assert "L2" in captured.out
        assert "📄" in captured.out  # has_report=True

    def test_list_json(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "minerva.persistence.list_results",
            lambda limit=20: [
                {
                    "id": "x",
                    "query": "q",
                    "has_report": False,
                    "timestamp": "t",
                    "level": "L0",
                    "quality_score": "A",
                    "source_count": 1,
                    "cost_usd": 0.1,
                }
            ],
        )
        args = MagicMock()
        args.results_cmd = "list"
        args.json = True
        result = _run_results(args)
        assert result == 0
        captured = capsys.readouterr()
        # Output may include ANSI codes; find JSON portion
        import re

        json_matches = re.findall(r'\{[^{]*"id":[^}]*\}', captured.out)
        assert json_matches, f"no JSON found in output: {captured.out!r}"
        # First match should be parseable
        json.loads(json_matches[0])


class TestRunResultsShow:
    def test_not_found(self, monkeypatch, capsys):
        monkeypatch.setattr("minerva.persistence.get_result", lambda rid: None)
        args = MagicMock()
        args.results_cmd = "show"
        args.result_id = "nonexistent"
        result = _run_results(args)
        assert result == 1
        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_found(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "minerva.persistence.get_result",
            lambda rid: {"id": rid, "query": "q", "level": "L1", "report": "## Report"},
        )
        args = MagicMock()
        args.results_cmd = "show"
        args.result_id = "abc"
        result = _run_results(args)
        assert result == 0
        captured = capsys.readouterr()
        # JSON metadata
        assert '"id": "abc"' in captured.out or '"id":"abc"' in captured.out
        # Report content
        assert "## Report" in captured.out

    def test_long_report_truncated(self, monkeypatch, capsys):
        long_report = "x" * 3000
        monkeypatch.setattr("minerva.persistence.get_result", lambda rid: {"id": rid, "report": long_report})
        args = MagicMock()
        args.results_cmd = "show"
        args.result_id = "abc"
        result = _run_results(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "more chars" in captured.out


class TestRunResultsDelete:
    def test_success(self, monkeypatch, capsys):
        monkeypatch.setattr("minerva.persistence.delete_result", lambda rid: True)
        args = MagicMock()
        args.results_cmd = "delete"
        args.result_id = "abc"
        result = _run_results(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "Deleted: abc" in captured.out

    def test_not_found(self, monkeypatch, capsys):
        monkeypatch.setattr("minerva.persistence.delete_result", lambda rid: False)
        args = MagicMock()
        args.results_cmd = "delete"
        args.result_id = "missing"
        result = _run_results(args)
        assert result == 1
        captured = capsys.readouterr()
        assert "not found" in captured.out


class TestRunResultsStats:
    def test_text(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "minerva.persistence.get_storage_stats",
            lambda: {
                "total_results": 5,
                "total_size_mb": 1.5,
                "storage_dir": "/tmp/storage",
            },
        )
        args = MagicMock()
        args.results_cmd = "stats"
        args.json = False
        result = _run_results(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "5" in captured.out
        assert "1.5" in captured.out

    def test_json(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "minerva.persistence.get_storage_stats",
            lambda: {"total_results": 1, "total_size_mb": 0.1, "storage_dir": "/x"},
        )
        args = MagicMock()
        args.results_cmd = "stats"
        args.json = True
        result = _run_results(args)
        assert result == 0
        captured = capsys.readouterr()
        # Output may include header text; find JSON portion
        import re

        json_matches = re.findall(r'\{[^{]*"total_results":[^}]*\}', captured.out)
        assert json_matches, f"no JSON in output: {captured.out!r}"
        json.loads(json_matches[0])


# ── _run_audit ───────────────────────────────────────────────


class TestRunAudit:
    def test_no_entries(self, monkeypatch, capsys):
        fake_logger = MagicMock()
        fake_logger.query.return_value = []
        monkeypatch.setattr("minerva.audit_store.get_logger", lambda: fake_logger)
        args = MagicMock()
        args.json = False
        args.limit = 20
        args.action = ""
        result = _run_audit(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "No audit entries" in captured.out

    def test_text(self, monkeypatch, capsys):
        fake_logger = MagicMock()
        fake_logger.query.return_value = [
            {"timestamp": "2026-07-26T00:00:00Z", "action": "research.run", "result": "success", "resource": "test"},
        ]
        fake_logger.stats.return_value = {"total_entries": 1}
        monkeypatch.setattr("minerva.audit_store.get_logger", lambda: fake_logger)
        args = MagicMock()
        args.json = False
        args.limit = 20
        args.action = ""
        result = _run_audit(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "research.run" in captured.out
        assert "success" in captured.out
        assert "1 total entries" in captured.out

    def test_json(self, monkeypatch, capsys):
        fake_logger = MagicMock()
        fake_logger.query.return_value = [{"timestamp": "t", "action": "x", "result": "ok", "resource": "r"}]
        monkeypatch.setattr("minerva.audit_store.get_logger", lambda: fake_logger)
        args = MagicMock()
        args.json = True
        args.limit = 10
        args.action = "x"
        result = _run_audit(args)
        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert data[0]["action"] == "x"


# ── main (command dispatch) ────────────────────────────────


class TestMain:
    def test_no_command_prints_help(self, capsys):
        result = _run_main([])
        assert result == 0
        captured = capsys.readouterr()
        # No command = prints help
        assert "usage" in captured.out.lower() or "minerva" in captured.out.lower()

    def test_init_dispatch(self, monkeypatch, capsys):
        monkeypatch.setattr("minerva.cli._run_init", lambda: 0)
        result = _run_main(["init"])
        assert result == 0

    def test_research_dispatch(self, monkeypatch):
        async def fake_run_research(args):
            return 0

        monkeypatch.setattr("minerva.cli._run_research", fake_run_research)
        # Patch asyncio.run
        with patch("asyncio.run", return_value=0):
            result = _run_main(["research", "test query"])
        assert result == 0

    def test_mcp_dispatch(self, monkeypatch):
        fake_main = MagicMock(return_value=0)
        with patch.dict(sys.modules, {"minerva.mcp_server.server": MagicMock(main=fake_main)}):
            # Direct import path
            import importlib

            mcp_module = importlib.import_module("minerva.mcp_server.server")
            mcp_module.main = fake_main  # type: ignore[reportAttributeAccessIssue]
            result = _run_main(["mcp"])
        assert result == 0

    def test_check_dispatch(self, monkeypatch, capsys):
        monkeypatch.setattr("minerva.cli._run_check", lambda: 0)
        result = _run_main(["check"])
        assert result == 0

    def test_web_dispatch(self, monkeypatch):
        with patch("uvicorn.run") as fake_run:
            with patch.dict(sys.modules, {"minerva.web.app": MagicMock(app="fake_app")}):
                result = _run_main(["web"])
        assert result == 0
        fake_run.assert_called_once()

    def test_daemon_dispatch(self, monkeypatch):
        fake_main = MagicMock(return_value=0)
        with patch.dict(sys.modules, {"minerva.executor.daemon": MagicMock(main=fake_main)}):
            import importlib

            daemon_module = importlib.import_module("minerva.executor.daemon")
            daemon_module.main = fake_main  # type: ignore[reportAttributeAccessIssue]
            result = _run_main(["daemon"])
        assert result == 0

    def test_maintenance_dispatch(self, monkeypatch, capsys):
        monkeypatch.setattr("minerva.cli._run_maintenance", lambda args: 0)
        result = _run_main(["maintenance"])
        assert result == 0

    def test_results_dispatch(self, monkeypatch, capsys):
        monkeypatch.setattr("minerva.cli._run_results", lambda args: 0)
        result = _run_main(["results", "list"])
        assert result == 0

    def test_audit_dispatch(self, monkeypatch, capsys):
        monkeypatch.setattr("minerva.cli._run_audit", lambda args: 0)
        result = _run_main(["audit"])
        assert result == 0

    def test_unknown_command_raises_systemexit(self, monkeypatch, capsys):
        """argparse exits with SystemExit(2) on unknown commands."""
        with pytest.raises(SystemExit) as exc_info:
            _run_main(["nonexistent_command"])
        assert exc_info.value.code == 2


class TestMainStderrWarning:
    def test_writes_deprecation_warning(self, capsys):
        _run_main([])  # no command, just help
        captured = capsys.readouterr()
        # Should have printed deprecation warning to stderr
        assert "⚠️" in captured.err or "弃用" in captured.err or "cockpit" in captured.err
