"""测试零覆盖的 5 个命令：list/export/agent/heatmap/governance。"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from unittest import mock

from rich.console import Console

from cockpit import cli
from cockpit.tests.conftest import MockDataAccess

# ═══════════════════════════════════════════════════════════════════════════════
# cmd_research_list — research.py:150
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdResearchList:
    """cmd_research_list 测试（空列表 / 正常渲染 / follow-up 计数）。"""

    def test_empty_list(self, monkeypatch):
        """无记录→提示文本"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr(cli, "err", capture)
        mock_da = MockDataAccess()
        mock_da.list_research = lambda limit=10, include_archived=False: []
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

        code = cli.cmd_research_list(argparse.Namespace(limit=10, status="all"))

        output = capture.export_text()
        assert code == 0
        assert "还没有研究记录" in output

    def test_normal_list(self, monkeypatch):
        """有记录→渲染表格"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr(cli, "err", capture)
        mock_da = MockDataAccess()
        mock_da.list_research = lambda limit=10, include_archived=False: [
            {
                "id": 1,
                "topic": "AI Safety",
                "created_at": 1710000000.0,
                "source_count": 3,
                "summary": "Important research",
                "agent": "minerva",
            },
            {
                "id": 2,
                "topic": "LLM Theory",
                "created_at": 1710000100.0,
                "source_count": 2,
                "summary": "Deep dive",
                "agent": "",
            },
        ]
        mock_da.get_research = lambda rid: {
            "id": rid,
            "topic": {1: "AI Safety", 2: "LLM Theory"}.get(rid, ""),
            "follow_ups": {1: [{"question": "q1", "answer": "a1", "timestamp": 1710000200.0}]}.get(rid, []),
        }
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

        code = cli.cmd_research_list(argparse.Namespace(limit=10, status="all"))

        output = capture.export_text()
        assert code == 0
        assert "AI Safety" in output
        assert "LLM Theory" in output
        assert "research" in output or "研究" in output  # table title
        assert "1" in output  # follow-ups count for ID=1
        assert "minerva" in output

    def test_via_main_research_list(self):
        """--list 路由确认（cli.main 直接返回，不 exit）"""
        # 不 mock sys.argv，只确认符号存在
        assert hasattr(cli, "cmd_research_list")

    def test_list_json(self, monkeypatch):
        """--list --json 输出 JSON"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr(cli, "err", capture)
        mock_da = MockDataAccess()
        mock_da.list_research = lambda limit=10, include_archived=False: [
            {
                "id": 1,
                "topic": "AI Safety",
                "created_at": 1710000000.0,
                "source_count": 3,
                "summary": "Important",
                "agent": "minerva",
            },
        ]
        mock_da.get_research = lambda rid: {"id": rid, "topic": "AI Safety", "follow_ups": []}
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

        code = cli.cmd_research_list(argparse.Namespace(limit=10, json=True, status="all"))

        output = capture.export_text()
        assert code == 0
        assert '"id": 1' in output
        assert '"topic": "AI Safety"' in output

    def test_list_status_active(self, monkeypatch):
        """--status active 仅显示未归档"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        mock_da = MockDataAccess()
        mock_da.list_research = lambda limit=10, include_archived=True: [
            {
                "id": 1,
                "topic": "Active",
                "created_at": 1710000000.0,
                "source_count": 1,
                "summary": "s",
                "agent": "",
                "archived_at": None,
            },
            {
                "id": 2,
                "topic": "Archived",
                "created_at": 1710000000.0,
                "source_count": 1,
                "summary": "s",
                "agent": "",
                "archived_at": 1711000000.0,
            },
        ]
        mock_da.get_research = lambda rid: {
            "id": rid,
            "topic": {1: "Active", 2: "Archived"}.get(rid, ""),
            "follow_ups": [],
        }
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)
        code = cli.cmd_research_list(argparse.Namespace(limit=10, status="active", json=True))
        output = capture.export_text()
        assert code == 0
        assert '"Active"' in output
        assert '"Archived"' not in output

    def test_list_status_archived(self, monkeypatch):
        """--status archived 仅显示已归档"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        mock_da = MockDataAccess()
        mock_da.list_research = lambda limit=10, include_archived=True: [
            {
                "id": 1,
                "topic": "Active",
                "created_at": 1710000000.0,
                "source_count": 1,
                "summary": "s",
                "agent": "",
                "archived_at": None,
            },
            {
                "id": 2,
                "topic": "Archived",
                "created_at": 1710000000.0,
                "source_count": 1,
                "summary": "s",
                "agent": "",
                "archived_at": 1711000000.0,
            },
        ]
        mock_da.get_research = lambda rid: {
            "id": rid,
            "topic": {1: "Active", 2: "Archived"}.get(rid, ""),
            "follow_ups": [],
        }
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)
        code = cli.cmd_research_list(argparse.Namespace(limit=10, status="archived", json=True))
        output = capture.export_text()
        assert code == 0
        assert '"Archived"' in output
        assert '"Active"' not in output


# ═══════════════════════════════════════════════════════════════════════════════
# cmd_research_export — research.py:688
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdResearchExport:
    """cmd_research_export 测试（找不到 / 不支持的格式 / markdown / text）。"""

    def test_not_found(self, monkeypatch):
        """研究不存在→错误 + return 1"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        mock_da = MockDataAccess()
        mock_da.get_research = lambda rid: None
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

        code = cli.cmd_research_export(argparse.Namespace(research_id=999, export="markdown"))

        output = capture.export_text()
        assert code == 1
        assert "not found" in output.lower()

    def test_unsupported_format(self, monkeypatch):
        """不支持的格式→错误 + return 1"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        mock_da = self._make_mock_da()
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

        code = cli.cmd_research_export(argparse.Namespace(research_id=1, export="pdf"))

        output = capture.export_text()
        assert code == 1
        assert "unsupported" in output.lower()

    def _make_mock_da(self):
        mock_da = MockDataAccess()
        mock_da.get_research = lambda rid: {
            "id": rid,
            "topic": "Test Topic",
            "created_at": 1700000000.0,
            "summary": "Test summary",
            "full_text": "Test full text content here.",
            "source_count": 3,
        }
        return mock_da

    def test_export_markdown(self, monkeypatch, tmp_path):
        """markdown 导出→写入文件 + 包含 Markdown 格式"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        # Use tmp_path as Desktop replacement
        with mock.patch.object(Path, "home", return_value=tmp_path):
            mock_da = self._make_mock_da()
            monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

            code = cli.cmd_research_export(argparse.Namespace(research_id=1, export="markdown"))

        output = capture.export_text()
        assert code == 0
        assert "Exported to" in output

        # Verify file was written (under Desktop subdir, extension = .markdown)
        exported_files = list(tmp_path.rglob("*.markdown"))
        assert len(exported_files) >= 1, f"No .markdown files under {tmp_path}"
        content = exported_files[0].read_text()
        assert "# Test Topic" in content
        assert "Sources: 3" in content

    def test_export_text(self, monkeypatch, tmp_path):
        """text 导出→写入文件 + 纯文本格式"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        with mock.patch.object(Path, "home", return_value=tmp_path):
            mock_da = self._make_mock_da()
            monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

            code = cli.cmd_research_export(argparse.Namespace(research_id=1, export="text"))

        output = capture.export_text()
        assert code == 0
        assert "Exported to" in output

        exported_files = list(tmp_path.rglob("*.text"))
        content = exported_files[0].read_text()
        assert "Title: Test Topic" in content
        assert "Date:" in content

    def test_export_json(self, monkeypatch):
        """json 导出→打印 JSON 到控制台"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        mock_da = self._make_mock_da()
        mock_da.get_research_dossier = lambda rid: {
            "record": {"id": rid, "topic": "Test"},
            "publications": [{"style": "brief", "output_path": "/tmp/out.md", "published_at": 1700000000.0}],
        }
        mock_da.compute_half_life = lambda rid: {"decay": 0.85}
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

        code = cli.cmd_research_export(argparse.Namespace(research_id=1, export="json"))

        output = capture.export_text()
        assert code == 0
        assert '"id": 1' in output
        assert '"topic": "Test Topic"' in output
        assert '"published_count": 1' in output
        assert '"decay": 0.85' in output
        assert '"follow_up_count": 0' in output


# ═══════════════════════════════════════════════════════════════════════════════
# cmd_research_agent — research.py:723
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdResearchAgent:
    """cmd_research_agent 测试（设置 Agent / 按 Agent 过滤 / 错误路径）。"""

    def test_set_agent_success(self, monkeypatch):
        """设置 Agent→成功提示"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        # MockDataAccess.set_research_agent 默认返回 True
        mock_da = MockDataAccess()
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

        code = cli.cmd_research_agent(argparse.Namespace(tag="42", agent="deepseek", limit=10))

        output = capture.export_text()
        assert code == 0
        assert "✅" in output
        assert "deepseek" in output

    def test_set_agent_not_found(self, monkeypatch):
        """设置 Agent 时研究不存在→错误"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        monkeypatch.setattr(cli, "err", capture)
        mock_da = MockDataAccess()
        mock_da.set_research_agent = lambda rid, name: False
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

        code = cli.cmd_research_agent(argparse.Namespace(tag="99", agent="deepseek", limit=10))

        output = capture.export_text()
        assert code == 1
        assert "未找到" in output

    def test_list_by_agent_found(self, monkeypatch):
        """按 Agent 列出→渲染表格"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        mock_da = MockDataAccess()
        mock_da.list_research = lambda limit=50: [
            {
                "id": 1,
                "topic": "Research A",
                "created_at": 1710000000.0,
                "source_count": 2,
                "summary": "summary a",
                "agent": "deepseek",
            },
            {
                "id": 2,
                "topic": "Research B",
                "created_at": 1710000100.0,
                "source_count": 3,
                "summary": "summary b",
                "agent": "gpt4",
            },
            {
                "id": 3,
                "topic": "Research C",
                "created_at": 1710000200.0,
                "source_count": 1,
                "summary": "summary c",
                "agent": "deepseek",
            },
        ]
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

        code = cli.cmd_research_agent(argparse.Namespace(tag=None, agent="deepseek", limit=50))

        output = capture.export_text()
        assert code == 0
        assert "Research A" in output
        assert "Research C" in output
        assert "Research B" not in output

    def test_list_by_agent_empty(self, monkeypatch):
        """按 Agent 列出无结果→提示"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        mock_da = MockDataAccess()
        mock_da.list_research = lambda limit=50: [
            {
                "id": 1,
                "topic": "Research A",
                "created_at": 1710000000.0,
                "source_count": 2,
                "summary": "summary a",
                "agent": "minerva",
            },
        ]
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

        code = cli.cmd_research_agent(argparse.Namespace(tag=None, agent="unknown_agent", limit=50))

        output = capture.export_text()
        assert code == 0
        assert "没有找到" in output

    def test_missing_both_tag_and_agent(self, monkeypatch):
        """既无 tag 也无 agent→return 1"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        mock_da = MockDataAccess()
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

        code = cli.cmd_research_agent(argparse.Namespace(tag=None, agent="", limit=10))

        assert code == 1


# ═══════════════════════════════════════════════════════════════════════════════
# cmd_research_heatmap — research.py:751
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdResearchHeatmap:
    """cmd_research_heatmap 测试（空 / 正常渲染）。"""

    def test_empty(self, monkeypatch):
        """无记录→提示"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        mock_da = MockDataAccess()
        mock_da.list_research = lambda limit=100, include_archived=True: []
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

        code = cli.cmd_research_heatmap(argparse.Namespace())

        output = capture.export_text()
        assert code == 0
        assert "暂无研究记录" in output

    def test_normal(self, monkeypatch):
        """有记录→渲染热力图表格"""
        import time

        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)
        now = time.time()
        mock_da = MockDataAccess()
        mock_da.list_research = lambda limit=100, include_archived=True: [
            {
                "id": 1,
                "topic": "Recent",
                "created_at": now - 86400,
                "source_count": 2,
                "summary": "s",
                "follow_ups": [],
            },
            {
                "id": 2,
                "topic": "Recent with fup",
                "created_at": now - 2 * 86400,
                "source_count": 3,
                "summary": "s2",
                "follow_ups": [{"question": "q", "answer": "a", "timestamp": now - 86400}],
            },
        ]
        monkeypatch.setattr(cli, "get_data_access", lambda: mock_da)

        code = cli.cmd_research_heatmap(argparse.Namespace())

        output = capture.export_text()
        assert code == 0
        assert "活跃度热力图" in output or "heat" in output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# cmd_governance — governance.py:11
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdGovernance:
    """cmd_governance 测试（无子命令 / 未知子命令 / 子命令执行）。"""

    def test_no_subcommand(self, monkeypatch):
        """无子命令→显示帮助列表"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)

        from cockpit.commands.governance import cmd_governance

        code = cmd_governance(argparse.Namespace(subcommand="", extra_args=None))

        output = capture.export_text()
        assert code == 0
        assert "可用治理子命令" in output or "calibrate" in output

    def test_unknown_subcommand(self, monkeypatch):
        """未知子命令→错误"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)

        from cockpit.commands.governance import cmd_governance

        code = cmd_governance(argparse.Namespace(subcommand="nonexistent_cmd_123", extra_args=None))

        output = capture.export_text()
        assert code == 1
        assert "未知治理命令" in output

    def test_subcommand_found(self, monkeypatch):
        """子命令存在→运行脚本"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr(cli, "console", capture)

        with (
            mock.patch("shutil.which") as mock_which,
            mock.patch("cockpit.commands.governance.subprocess.run") as mock_run,
            mock.patch("pathlib.Path.exists", return_value=True),
        ):
            mock_which.return_value = None  # fallback to Path.home()/.hermes/scripts/
            mock_run.return_value.returncode = 0

            from cockpit.commands.governance import cmd_governance

            code = cmd_governance(argparse.Namespace(subcommand="calibrate", extra_args=["--check"]))

        assert code == 0
        mock_run.assert_called_once()
        args, _ = mock_run.call_args
        # The called command should contain "calibrate"
        cmd_str = " ".join(args[0]) if isinstance(args[0], list) else str(args[0])
        assert "calibrate" in cmd_str


# ═══════════════════════════════════════════════════════════════════════════════
# cmd_research_follow_up
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdResearchFollowUp:
    """cmd_research_follow_up 测试。"""

    def test_no_pending(self, monkeypatch):
        """无待追问→提示信息"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.research._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.research._get_err", lambda: capture)

        mock_da = MockDataAccess()
        mock_da.list_research = lambda limit=100: [
            {
                "id": 1,
                "topic": "Active",
                "created_at": 1000.0,
                "archived_at": None,
                "follow_ups": [{"question": "q1", "answer": "a1"}],
            },
            {"id": 2, "topic": "No Fups", "created_at": 2000.0, "archived_at": None, "follow_ups": []},
        ]
        monkeypatch.setattr("cockpit.commands.research._get_data_access", lambda: mock_da)

        from cockpit.commands.research import cmd_research_follow_up

        code = cmd_research_follow_up(argparse.Namespace())
        assert code == 0
        output = capture.export_text()
        assert "追问都已处理" in output

    def test_with_pending(self, monkeypatch):
        """有待追问→显示表格"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.research._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.research._get_err", lambda: capture)

        mock_da = MockDataAccess()
        mock_da.list_research = lambda limit=100: [
            {
                "id": 1,
                "topic": "Pending",
                "created_at": 1000.0,
                "archived_at": None,
                "follow_ups": [{"question": "why?", "answer": ""}],
            },
            {
                "id": 2,
                "topic": "Answered",
                "created_at": 2000.0,
                "archived_at": None,
                "follow_ups": [{"question": "q", "answer": "a"}],
            },
        ]
        monkeypatch.setattr("cockpit.commands.research._get_data_access", lambda: mock_da)

        from cockpit.commands.research import cmd_research_follow_up

        code = cmd_research_follow_up(argparse.Namespace())
        assert code == 0
        output = capture.export_text()
        assert "待追问" in output
        assert "Pending" in output
        assert "why?" in output

    def test_archived_excluded(self, monkeypatch):
        """已归档研究不显示"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.research._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.research._get_err", lambda: capture)

        mock_da = MockDataAccess()
        mock_da.list_research = lambda limit=100: [
            {
                "id": 1,
                "topic": "Archived",
                "created_at": 1000.0,
                "archived_at": 2000.0,
                "follow_ups": [{"question": "q", "answer": ""}],
            },
            {
                "id": 2,
                "topic": "Active",
                "created_at": 3000.0,
                "archived_at": None,
                "follow_ups": [{"question": "q2", "answer": ""}],
            },
        ]
        monkeypatch.setattr("cockpit.commands.research._get_data_access", lambda: mock_da)

        from cockpit.commands.research import cmd_research_follow_up

        code = cmd_research_follow_up(argparse.Namespace())
        assert code == 0
        output = capture.export_text()
        assert "Archived" not in output
        assert "Active" in output


# ═══════════════════════════════════════════════════════════════════════════════
# cmd_research_health — research.py（research health 报告）
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdResearchHealth:
    """cmd_research_health 测试（空 / 全健康 / 混合 / 归档排除）。"""

    def test_no_active(self, monkeypatch):
        """无活跃研究→提示"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.research._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.research._get_err", lambda: capture)
        mock_da = MockDataAccess()
        mock_da.list_research = lambda limit=100: []
        monkeypatch.setattr("cockpit.commands.research._get_data_access", lambda: mock_da)

        from cockpit.commands.research import cmd_research_health

        code = cmd_research_health(argparse.Namespace())

        output = capture.export_text()
        assert code == 0
        assert "暂无活跃" in output
        assert "研究健康报告" in output

    def test_all_good(self, monkeypatch):
        """全部健康→仅显示健康组"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.research._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.research._get_err", lambda: capture)

        now = time.time()
        mock_da = MockDataAccess()
        mock_da.list_research = lambda limit=100: [
            {"id": 1, "topic": "Healthy A", "created_at": now - 86400, "source_count": 2, "summary": "s"},
        ]
        mock_da.compute_half_life = lambda rid: {
            "decay": 0.85,
            "half_life_days": 14,
            "days_since_active": 2.0,
            "follow_up_count": 1,
            "published_count": 0,
        }
        monkeypatch.setattr("cockpit.commands.research._get_data_access", lambda: mock_da)

        from cockpit.commands.research import cmd_research_health

        code = cmd_research_health(argparse.Namespace())

        output = capture.export_text()
        assert code == 0
        assert "健康" in output
        assert "状态良好" in output
        # 不应出现保鲜建议（全部健康）
        assert "保鲜建议" not in output

    def test_mixed_health(self, monkeypatch):
        """混合状态→三组均显示"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.research._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.research._get_err", lambda: capture)

        now = time.time()
        hl_map = {
            1: {
                "decay": 0.9,
                "half_life_days": 14,
                "days_since_active": 1.0,
                "follow_up_count": 2,
                "published_count": 0,
            },
            2: {
                "decay": 0.5,
                "half_life_days": 14,
                "days_since_active": 10.0,
                "follow_up_count": 0,
                "published_count": 1,
            },
            3: {
                "decay": 0.1,
                "half_life_days": 14,
                "days_since_active": 45.0,
                "follow_up_count": 0,
                "published_count": 0,
            },
        }
        mock_da = MockDataAccess()
        mock_da.list_research = lambda limit=100: [
            {"id": 1, "topic": "Good One", "created_at": now - 86400, "source_count": 2, "summary": "s"},
            {"id": 2, "topic": "Fair One", "created_at": now - 10 * 86400, "source_count": 1, "summary": "s"},
            {"id": 3, "topic": "Stale One", "created_at": now - 45 * 86400, "source_count": 1, "summary": "s"},
        ]
        mock_da.compute_half_life = lambda rid: hl_map.get(rid, {"decay": 0.0, "days_since_active": 999})
        monkeypatch.setattr("cockpit.commands.research._get_data_access", lambda: mock_da)

        from cockpit.commands.research import cmd_research_health

        code = cmd_research_health(argparse.Namespace())

        output = capture.export_text()
        assert code == 0
        assert "健康 1" in output or "健康（" in output
        assert "待关注 1" in output or "待关注（" in output
        assert "已衰减 1" in output or "已衰减（" in output
        assert "保鲜建议" in output
        # 验证具体研究名出现在输出中
        assert "Good One" in output
        assert "Fair One" in output
        assert "Stale One" in output

    def test_archived_excluded(self, monkeypatch):
        """已归档研究不计入健康报告"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.research._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.research._get_err", lambda: capture)

        now = time.time()
        mock_da = MockDataAccess()
        mock_da.list_research = lambda limit=100: [
            {
                "id": 1,
                "topic": "Active",
                "created_at": now - 86400,
                "source_count": 2,
                "summary": "s",
                "archived_at": None,
            },
            {
                "id": 2,
                "topic": "Archived",
                "created_at": now - 86400,
                "source_count": 1,
                "summary": "s",
                "archived_at": now - 1000,
            },
        ]
        hl_map = {1: {"decay": 0.9, "days_since_active": 1.0, "follow_up_count": 0, "published_count": 0}}
        mock_da.compute_half_life = lambda rid: hl_map.get(rid, {"decay": 0.0, "days_since_active": 999})
        monkeypatch.setattr("cockpit.commands.research._get_data_access", lambda: mock_da)

        from cockpit.commands.research import cmd_research_health

        code = cmd_research_health(argparse.Namespace())

        output = capture.export_text()
        assert code == 0
        assert "共 1 条" in output or "共 1 活跃" in output or "健康 1" in output
        assert "Archived" not in output
