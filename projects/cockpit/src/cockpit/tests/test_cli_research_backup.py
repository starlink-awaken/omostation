"""Research backup/restore CLI 命令单元测试。"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from unittest import mock

from rich.console import Console
from cockpit.commands.research import cmd_research_backup, cmd_research_backup_restore

# ═══════════════════════════════════════════════════════════════════════════════
# cmd_research_backup — 3 条路径
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdResearchBackup:
    def test_default_output(self, monkeypatch, tmp_path):
        """默认输出路径（~/Desktop/workspace_backup.json）→ 成功"""
        desktop = tmp_path / "Desktop"
        desktop.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.research._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.research._get_err", lambda: capture)

        mock_da = mock.Mock()
        mock_da.export_backup.return_value = {
            "version": 1,
            "exported_at": time.time(),
            "research": [{"id": 1, "topic": "t1"}],
            "relations": [],
            "published_reports": [],
            "events": [],
        }
        monkeypatch.setattr("cockpit.commands.research._get_data_access", lambda: mock_da)

        code = cmd_research_backup(argparse.Namespace(output=None))
        output = capture.export_text()

        assert code == 0
        assert "备份完成" in output
        assert "1 条" in output

    def test_custom_output(self, monkeypatch, tmp_path):
        """指定输出路径 → 写入指定文件"""
        out_file = tmp_path / "my_backup.json"

        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.research._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.research._get_err", lambda: capture)

        mock_da = mock.Mock()
        mock_da.export_backup.return_value = {
            "version": 1,
            "exported_at": 0.0,
            "research": [],
            "relations": [],
            "published_reports": [],
            "events": [],
        }
        monkeypatch.setattr("cockpit.commands.research._get_data_access", lambda: mock_da)

        code = cmd_research_backup(argparse.Namespace(output=str(out_file)))
        assert code == 0
        assert out_file.exists()

    def test_write_error(self, monkeypatch):
        """写入失败（只读目录）→ 返回 1"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.research._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.research._get_err", lambda: capture)
        monkeypatch.setattr("cockpit.commands.research.Path.write_text", mock.Mock(side_effect=PermissionError("denied")))

        mock_da = mock.Mock()
        mock_da.export_backup.return_value = {
            "version": 1,
            "exported_at": 0.0,
            "research": [],
            "relations": [],
            "published_reports": [],
            "events": [],
        }
        monkeypatch.setattr("cockpit.commands.research._get_data_access", lambda: mock_da)

        code = cmd_research_backup(argparse.Namespace(output="/nonexistent/backup.json"))
        assert code == 1


# ═══════════════════════════════════════════════════════════════════════════════
# cmd_research_backup_restore — 5 条路径
# ═══════════════════════════════════════════════════════════════════════════════


class TestCmdResearchBackupRestore:
    def test_no_path(self, monkeypatch):
        """未指定路径 → 返回 1"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.research._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.research._get_err", lambda: capture)

        code = cmd_research_backup_restore(argparse.Namespace(backup_restore=None))
        assert code == 1

    def test_file_not_found(self, monkeypatch):
        """文件不存在 → 返回 1"""
        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.research._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.research._get_err", lambda: capture)

        code = cmd_research_backup_restore(argparse.Namespace(backup_restore="/nonexistent/backup.json"))
        assert code == 1

    def test_invalid_json(self, monkeypatch, tmp_path):
        """无效 JSON → 返回 1"""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json", encoding="utf-8")

        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.research._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.research._get_err", lambda: capture)

        code = cmd_research_backup_restore(argparse.Namespace(backup_restore=str(bad_file)))
        assert code == 1

    def test_missing_version(self, monkeypatch, tmp_path):
        """缺少 version 字段 → 返回 1"""
        bad_file = tmp_path / "no_version.json"
        bad_file.write_text(json.dumps({"research": []}), encoding="utf-8")

        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.research._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.research._get_err", lambda: capture)

        code = cmd_research_backup_restore(argparse.Namespace(backup_restore=str(bad_file)))
        assert code == 1

    def test_success(self, monkeypatch, tmp_path):
        """有效备份文件 → 成功导入"""
        backup_file = tmp_path / "good_backup.json"
        data = {
            "version": 1,
            "exported_at": time.time(),
            "research": [
                {
                    "id": 1,
                    "topic": "恢复测试",
                    "summary": "s",
                    "full_text": "",
                    "created_at": time.time(),
                    "source_count": 0,
                    "follow_ups": [],
                    "tags": [],
                    "archived_at": None,
                    "archive_reason": None,
                    "quarantined_at": None,
                    "quarantine_reason": None,
                    "agent": "",
                }
            ],
            "relations": [],
            "published_reports": [],
            "events": [],
        }
        backup_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        capture = Console(record=True, force_terminal=True, width=140)
        monkeypatch.setattr("cockpit.commands.research._get_console", lambda: capture)
        monkeypatch.setattr("cockpit.commands.research._get_err", lambda: capture)

        mock_da = mock.Mock()
        mock_da.import_backup.return_value = {
            "research": 1,
            "relations": 0,
            "published_reports": 0,
            "events": 0,
            "skipped": 0,
        }
        monkeypatch.setattr("cockpit.commands.research._get_data_access", lambda: mock_da)

        code = cmd_research_backup_restore(argparse.Namespace(backup_restore=str(backup_file)))
        output = capture.export_text()
        assert code == 0
        assert "恢复完成" in output
        assert "1 条导入" in output


# ═══════════════════════════════════════════════════════════════════════════════
# CLI dispatch — 2 条路径
# ═══════════════════════════════════════════════════════════════════════════════


class TestBackupCliDispatch:
    def test_cli_has_backup_commands(self):
        """cli 模块导出 backup 相关函数"""
        from cockpit import cli

        assert hasattr(cli, "cmd_research_backup")
        assert hasattr(cli, "cmd_research_backup_restore")

    def test_backup_route_via_main(self, monkeypatch):
        """--backup 通过 cli.main() 正确路由到 cmd_research_backup"""
        from cockpit import cli as _cli

        monkeypatch.setattr("cockpit.commands.research._get_data_access", mock.Mock())
        monkeypatch.setattr(_cli, "cmd_research_backup", mock.Mock(return_value=0))
        monkeypatch.setattr(sys, "argv", ["workspace", "research", "--backup"])
        code = _cli.main()
        assert code == 0

    def test_backup_restore_route_via_main(self, monkeypatch):
        """--backup-restore 通过 cli.main() 正确路由到 cmd_research_backup_restore"""
        from cockpit import cli as _cli

        monkeypatch.setattr("cockpit.commands.research._get_data_access", mock.Mock())
        monkeypatch.setattr(_cli, "cmd_research_backup_restore", mock.Mock(return_value=0))
        monkeypatch.setattr(sys, "argv", ["workspace", "research", "--backup-restore", "/tmp/bk.json"])
        code = _cli.main()
        assert code == 0
