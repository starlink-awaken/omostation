"""Tests for Brief generator."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch


from ecos.services.core.brief import (
    check_claude_guards,
    check_freshness,
    format_brief,
    get_event_count_since,
    get_protocol_risks,
    get_sla,
    get_top_cards,
    main,
    run_script,
)


# ── run_script ──


class TestRunScript:
    @patch("ecos.services.core.brief.SCRIPTS")
    @patch("ecos.services.core.brief.subprocess.run")
    def test_runs_script(self, mock_run, mock_scripts):
        mock_scripts.__truediv__.return_value.exists.return_value = True
        mock_result = MagicMock()
        mock_result.stdout = "output"
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        out, code = run_script("test.py")
        assert out == "output"
        assert code == 0

    @patch("ecos.services.core.brief.SCRIPTS")
    def test_script_not_found(self, mock_scripts):
        mock_scripts.__truediv__.return_value.exists.return_value = False
        out, code = run_script("nonexistent.py")
        assert "脚本缺失" in out
        assert code == 2

    @patch("ecos.services.core.brief.SCRIPTS")
    @patch("ecos.services.core.brief.subprocess.run")
    def test_timeout(self, mock_run, mock_scripts):
        mock_scripts.__truediv__.return_value.exists.return_value = True
        from subprocess import TimeoutExpired

        mock_run.side_effect = TimeoutExpired("test.py", 1)
        out, code = run_script("test.py", timeout=1)
        assert "超时" in out
        assert code == 1


# ── get_sla ──


class TestGetSla:
    @patch("ecos.services.core.brief.run_script")
    def test_parses_json(self, mock_run):
        mock_run.return_value = (
            json.dumps({"uptime": 95.0, "consecutive_passes": 10, "total": 100}),
            0,
        )
        sla = get_sla()
        assert sla["uptime"] == 95.0
        assert sla["consecutive_passes"] == 10

    @patch("ecos.services.core.brief.run_script")
    def test_fallback_on_bad_json(self, mock_run):
        mock_run.return_value = ("not json", 0)
        sla = get_sla()
        assert sla["uptime"] is None


# ── get_top_cards ──


class TestGetTopCards:
    @patch("ecos.services.core.brief.CARDS_DB")
    def test_db_not_exists(self, mock_db):
        mock_db.exists.return_value = False
        assert get_top_cards() == []

    @patch("ecos.services.core.brief.CARDS_DB")
    @patch("ecos.services.core.brief.sqlite3.connect")
    def test_returns_cards(self, mock_connect, mock_db):
        mock_db.exists.return_value = True
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("C-1", "Fix bug", "active", "core", "P0"),
            ("C-2", "Add feature", "identified", "infra", "P1"),
        ]
        mock_conn.execute.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        cards = get_top_cards(2)
        assert len(cards) == 2
        assert cards[0]["id"] == "C-1"
        assert cards[0]["priority"] == "P0"

    @patch("ecos.services.core.brief.CARDS_DB")
    @patch("ecos.services.core.brief.sqlite3.connect")
    def test_handles_error(self, mock_connect, mock_db):
        mock_db.exists.return_value = True
        mock_connect.side_effect = ValueError("bad db")
        cards = get_top_cards()
        assert cards[0]["id"] == "error"


# ── check_claude_guards ──


class TestCheckClaudeGuards:
    @patch("ecos.services.core.brief.DOCS")
    def test_all_fresh(self, mock_docs):
        mock_docs.rglob.return_value = []
        result = check_claude_guards()
        assert result["fresh"] == 0
        assert result["stale"] == 0
        assert result["action_required"] is False

    @patch("ecos.services.core.brief.DOCS")
    def test_detects_stale(self, mock_docs):
        fresh_file = MagicMock()
        fresh_file.is_file.return_value = True
        fresh_file.is_symlink.return_value = False
        fresh_file.stat.return_value = MagicMock(st_mtime=datetime.now().timestamp())
        fresh_file.__str__.return_value = "/Users/xm/Documents/fresh/CLAUDE.md"  # type: ignore[reportAttributeAccessIssue]

        stale_file = MagicMock()
        stale_file.is_file.return_value = True
        stale_file.is_symlink.return_value = False
        stale_file.stat.return_value = MagicMock(st_mtime=0)  # very old
        stale_file.__str__.return_value = "/Users/xm/Documents/stale/CLAUDE.md"  # type: ignore[reportAttributeAccessIssue]

        # Need parent.relative_to and relative_to
        stale_file.parent.relative_to.return_value = Path("stale")
        stale_file.relative_to.return_value = Path("stale/CLAUDE.md")

        mock_docs.rglob.return_value = [fresh_file, stale_file]
        mock_docs.__str__.return_value = "/Users/xm/Documents"
        mock_docs.__truediv__.return_value = Path("/Users/xm/Documents")

        # Make DOCS in parents of stale_file
        stale_file.parents.__contains__.return_value = True

        result = check_claude_guards()
        assert result["total"] == 2
        assert result["fresh"] == 1
        assert result["stale"] == 1
        assert result["action_required"] is True


# ── get_protocol_risks ──


class TestGetProtocolRisks:
    @patch("ecos.services.core.brief.run_script")
    def test_no_risks(self, mock_run):
        mock_run.return_value = (json.dumps({"protocols": []}), 0)
        assert get_protocol_risks() == []

    @patch("ecos.services.core.brief.run_script")
    def test_high_risk_detected(self, mock_run):
        data = {
            "protocols": [
                {
                    "id": "OLD",
                    "version": "1.0",
                    "introduced": "2020-01-01",
                    "half_life_days": 30,
                }
            ]
        }
        mock_run.return_value = (json.dumps(data), 0)
        risks = get_protocol_risks()
        assert len(risks) >= 1
        assert risks[0]["protocol"] == "OLD"

    @patch("ecos.services.core.brief.run_script")
    def test_bad_json(self, mock_run):
        mock_run.return_value = ("not json", 0)
        assert get_protocol_risks() == []


# ── get_event_count_since ──


class TestGetEventCountSince:
    @patch("ecos.services.core.brief.Path.home")
    def test_file_not_exists(self, mock_home):
        mock_file = MagicMock()
        mock_file.exists.return_value = False
        mock_home.return_value.__truediv__.return_value.__truediv__.return_value.__truediv__.return_value = mock_file
        assert get_event_count_since() == 0

    @patch("ecos.services.core.brief.Path.home")
    def test_recent_activity(self, mock_home):
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.stat.return_value = MagicMock(st_mtime=datetime.now().timestamp())
        mock_home.return_value.__truediv__.return_value.__truediv__.return_value.__truediv__.return_value = mock_file
        assert get_event_count_since() == 1

    @patch("ecos.services.core.brief.Path.home")
    def test_old_activity(self, mock_home):
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.stat.return_value = MagicMock(st_mtime=0)
        mock_home.return_value.__truediv__.return_value.__truediv__.return_value.__truediv__.return_value = mock_file
        assert get_event_count_since() == 0


# ── check_freshness ──


class TestCheckFreshness:
    def test_file_not_exists(self):
        with patch("ecos.services.core.brief.Path.exists", return_value=False):
            assert check_freshness("/fake/path") is False

    def test_recent_file(self):
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.stat.return_value = MagicMock(st_mtime=datetime.now().timestamp())
        with patch("ecos.services.core.brief.Path", return_value=mock_file):
            assert check_freshness("/fake/path") is True

    def test_old_file(self):
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.stat.return_value = MagicMock(st_mtime=0)
        with patch("ecos.services.core.brief.Path", return_value=mock_file):
            assert check_freshness("/fake/path") is False


# ── format_brief ──


class TestFormatBrief:
    def test_minimal(self):
        text = format_brief(
            sla={"uptime": None, "consecutive_passes": 0, "total": 0},
            cards=[],
            risks=[],
            health_pass=True,
            health_output="",
            event_count=0,
        )
        assert "会话简报" in text
        assert "系统健康" in text
        assert "SLA 数据累积中" in text
        assert "CARDS 数据库不可读" in text
        assert "无重大风险" in text
        assert "无新活动" in text

    def test_with_data(self):
        text = format_brief(
            sla={
                "uptime": 95.0,
                "consecutive_passes": 10,
                "total": 100,
                "last_failure": None,
            },
            cards=[
                {
                    "id": "C-1",
                    "title": "Fix bug",
                    "status": "active",
                    "domain": "core",
                    "priority": "P0",
                }
            ],
            risks=[
                {
                    "protocol": "SSB",
                    "version": "2.1",
                    "remaining": 15.0,
                    "age_days": 300,
                    "half_life": 365,
                }
            ],
            health_pass=True,
            health_output="✅ all good",
            event_count=5,
            claude_guards={
                "total": 5,
                "fresh": 5,
                "stale": 0,
                "stale_files": [],
                "warning": "✅ 全部新鲜",
                "action_required": False,
            },
        )
        assert "95.0%" in text
        assert "Fix bug" in text
        assert "SSB" in text
        assert "全部" in text
        assert "新鲜" in text
        assert "有活动" in text

    def test_health_fail(self):
        text = format_brief(
            sla={"uptime": 50.0, "consecutive_passes": 0, "total": 10},
            cards=[],
            risks=[],
            health_pass=False,
            health_output="❌ something failed",
            event_count=0,
        )
        assert "系统异常" in text
        assert "存在告警" in text

    def test_claude_stale(self):
        text = format_brief(
            sla={"uptime": None, "consecutive_passes": 0, "total": 0},
            cards=[],
            risks=[],
            health_pass=True,
            health_output="",
            event_count=0,
            claude_guards={
                "total": 3,
                "fresh": 1,
                "stale": 2,
                "stale_files": [{"file": "x/CLAUDE.md", "domain": "x", "age_days": 90}],
                "warning": "⚠️ 2 个过期",
                "action_required": True,
            },
        )
        assert "保鲜告警" in text
        assert "2 个过期" in text

    def test_with_risks(self):
        text = format_brief(
            sla={"uptime": None, "consecutive_passes": 0, "total": 0},
            cards=[],
            risks=[
                {
                    "protocol": "OLD",
                    "version": "1.0",
                    "remaining": 5.0,
                    "age_days": 400,
                    "half_life": 365,
                }
            ],
            health_pass=True,
            health_output="",
            event_count=0,
        )
        assert "🔴" in text  # low remaining value

    def test_with_health_output_on_fail(self):
        text = format_brief(
            sla={"uptime": None, "consecutive_passes": 0, "total": 0},
            cards=[],
            risks=[],
            health_pass=False,
            health_output="line1\n⚠️ warning line\nline3",
            event_count=0,
        )
        assert "warning line" in text


# ── main ──


class TestMain:
    @patch("ecos.services.core.brief.argparse.ArgumentParser.parse_args")
    @patch("ecos.services.core.brief.check_freshness")
    @patch("ecos.services.core.brief.Path")
    def test_skip_if_fresh(self, mock_path, mock_freshness, mock_args):
        mock_freshness.return_value = True
        mock_args.return_value = MagicMock(
            output="/fake/brief.md", json=False, force=False
        )
        mock_path.return_value.stat.return_value = MagicMock(
            st_mtime=datetime.now().timestamp()
        )
        main()  # should not raise

    @patch("ecos.services.core.brief.argparse.ArgumentParser.parse_args")
    @patch("ecos.services.core.brief.check_freshness")
    @patch("ecos.services.core.brief.check_claude_guards")
    @patch("ecos.services.core.brief.get_sla")
    @patch("ecos.services.core.brief.get_top_cards")
    @patch("ecos.services.core.brief.get_protocol_risks")
    @patch("ecos.services.core.brief.get_event_count_since")
    @patch("ecos.services.core.brief.run_script")
    @patch("ecos.services.core.brief.Path.write_text")
    def test_generates_brief(
        self,
        mock_write,
        mock_run,
        mock_event,
        mock_risks,
        mock_cards,
        mock_sla,
        mock_claude,
        mock_freshness,
        mock_args,
    ):
        mock_freshness.return_value = False
        mock_args.return_value = MagicMock(
            output="/fake/brief.md", json=False, force=False
        )
        mock_claude.return_value = {
            "total": 0,
            "fresh": 0,
            "stale": 0,
            "stale_files": [],
            "warning": "ok",
            "action_required": False,
        }
        mock_sla.return_value = {"uptime": None, "consecutive_passes": 0, "total": 0}
        mock_cards.return_value = []
        mock_risks.return_value = []
        mock_event.return_value = 0
        mock_run.return_value = (json.dumps({"results": [{"pass": True}]}), 0)
        main()
        mock_write.assert_called_once()

    @patch("ecos.services.core.brief.argparse.ArgumentParser.parse_args")
    @patch("ecos.services.core.brief.check_freshness")
    @patch("ecos.services.core.brief.check_claude_guards")
    @patch("ecos.services.core.brief.get_sla")
    @patch("ecos.services.core.brief.get_top_cards")
    @patch("ecos.services.core.brief.get_protocol_risks")
    @patch("ecos.services.core.brief.get_event_count_since")
    @patch("ecos.services.core.brief.run_script")
    def test_json_output(
        self,
        mock_run,
        mock_event,
        mock_risks,
        mock_cards,
        mock_sla,
        mock_claude,
        mock_freshness,
        mock_args,
    ):
        mock_freshness.return_value = False
        mock_args.return_value = MagicMock(
            output="/fake/brief.md", json=True, force=False
        )
        mock_claude.return_value = {
            "total": 0,
            "fresh": 0,
            "stale": 0,
            "stale_files": [],
            "warning": "ok",
            "action_required": False,
        }
        mock_sla.return_value = {"uptime": None, "consecutive_passes": 0, "total": 0}
        mock_cards.return_value = []
        mock_risks.return_value = []
        mock_event.return_value = 0
        mock_run.return_value = (json.dumps({"results": [{"pass": True}]}), 0)
        main()  # should not raise
