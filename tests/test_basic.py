"""cockpit 基础测试 — 包导入、CLI 入口与帮助文本。"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch


class TestPackageImport:
    """验证 cockpit 包及其核心模块可正常导入。"""

    def test_import_cockpit(self):
        """包本身可导入。"""
        import cockpit

        assert hasattr(cockpit, "__version__") or hasattr(cockpit, "__file__")

    def test_import_cli(self):
        """CLI 入口模块可导入。"""
        from cockpit import cli

        assert hasattr(cli, "main")
        assert callable(cli.main)

    def test_import_storage(self):
        """storage 模块可导入。"""
        from cockpit import storage

        assert hasattr(storage, "get_data_access")
        assert hasattr(storage, "set_data_access")
        assert hasattr(storage, "IDataAccess")
        assert hasattr(storage, "SQLiteDataAccess")

    def test_import_data_index(self):
        """data_index 模块可导入。"""
        from cockpit import data_index

        assert callable(getattr(data_index, "build_data_index", None))

    def test_import_commands(self):
        """commands 子包可导入。"""

    def test_import_research_commands(self):
        """重要命令模块可导入。"""
        from cockpit.commands import research

        assert hasattr(research, "cmd_research")
        assert hasattr(research, "cmd_research_list")
        assert hasattr(research, "cmd_research_search")
        assert hasattr(research, "cmd_research_open")
        assert hasattr(research, "cmd_research_ask")

    def test_import_status_commands(self):
        """状态命令模块可导入。"""
        from cockpit.commands import status

        assert hasattr(status, "cmd_status")
        assert hasattr(status, "cmd_dashboard")
        assert hasattr(status, "cmd_demo")
        assert hasattr(status, "cmd_help")
        assert hasattr(status, "cmd_daily")

    def test_import_data_commands(self):
        """数据命令模块可导入。"""
        from cockpit.commands import data

        assert hasattr(data, "cmd_data_index")
        assert hasattr(data, "cmd_data_types")
        assert hasattr(data, "cmd_data_gc")

    def test_import_contracts_commands(self):
        """契约命令模块可导入。"""
        from cockpit.commands import contracts

        assert hasattr(contracts, "cmd_contracts_validate")
        assert hasattr(contracts, "cmd_contracts_list")

    def test_import_importer(self):
        """导入命令模块可导入。"""
        from cockpit.commands import importer

        assert hasattr(importer, "cmd_import")

    def test_import_quickstart(self):
        """快速启动命令模块可导入。"""
        from cockpit.commands import quickstart

        assert hasattr(quickstart, "cmd_quickstart")

    def test_import_mcp(self):
        """MCP 命令模块可导入。"""
        from cockpit.commands import mcp

        assert hasattr(mcp, "cmd_mcp")

    def test_import_profile(self):
        """身份档案模块可导入。"""
        from cockpit.commands import profile

        assert hasattr(profile, "cmd_profile")

    def test_import_governance(self):
        """治理命令模块可导入。"""
        from cockpit.commands import governance

        assert hasattr(governance, "cmd_governance")

    def test_import_base(self):
        """base 模块可导入。"""
        from cockpit.commands import base

        assert hasattr(base, "_SCRIPT_DIR")

    def test_cli_main_no_args(self):
        """CLI 的 main 函数无参数时返回 0（显示欢迎面板）。"""
        from cockpit.cli import main

        with patch.object(sys, "argv", ["workspace"]):
            result = main()
            assert result == 0


class TestEntryPoint:
    """验证 python -m cockpit 可运行并 --help 输出预期内容。"""

    def test_module_runs_without_error(self):
        """python -m cockpit 退码为 0。"""
        root = Path(__file__).resolve().parent.parent  # packages/cockpit/
        result = subprocess.run(
            [sys.executable, "-m", "cockpit"],
            capture_output=True,
            text=True,
            cwd=root / "src",
        )
        assert result.returncode == 0

    def test_help_contains_expected_commands(self):
        """--help 输出应包含核心命令。"""
        root = Path(__file__).resolve().parent.parent  # packages/cockpit/
        result = subprocess.run(
            [sys.executable, "-m", "cockpit", "--help"],
            capture_output=True,
            text=True,
            cwd=root / "src",
        )
        assert result.returncode == 0
        output = result.stdout
        assert "research" in output
        assert "status" in output
        assert "import" in output
        assert "demo" in output
        assert "daily" in output
        assert "dashboard" in output
        assert "help" in output
        assert "quickstart" in output
        assert "contracts" in output
        assert "profile" in output
        assert "mcp" in output
        assert "governance" in output
        assert "data" in output


class TestCLIEntryPoints:
    """验证关键子命令的 --help 可正常输出。"""

    def test_research_help(self):
        """research --help 显示研究相关选项。"""
        root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "cockpit", "research", "--help"],
            capture_output=True,
            text=True,
            cwd=root / "src",
        )
        assert result.returncode == 0
        output = result.stdout
        assert "--list" in output
        assert "--open" in output
        assert "--search" in output
        assert "--publish" in output
        assert "--ask" in output
        assert "--dossier" in output
        assert "--timeline" in output
        assert "--tag" in output
        assert "--compare" in output
        assert "--merge" in output
        assert "--digest" in output

    def test_status_help(self):
        """status --help 可正常输出。"""
        root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "cockpit", "status", "--help"],
            capture_output=True,
            text=True,
            cwd=root / "src",
        )
        assert result.returncode == 0

    def test_help_command(self):
        """help 命令可正常输出帮助内容。"""
        root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "cockpit", "help"],
            capture_output=True,
            text=True,
            cwd=root / "src",
        )
        assert result.returncode == 0

    def test_demo_help(self):
        """demo --help 可正常输出。"""
        root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "cockpit", "demo", "--help"],
            capture_output=True,
            text=True,
            cwd=root / "src",
        )
        assert result.returncode == 0

    def test_quickstart_help(self):
        """quickstart --help 可正常输出。"""
        root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "cockpit", "quickstart", "--help"],
            capture_output=True,
            text=True,
            cwd=root / "src",
        )
        assert result.returncode == 0
