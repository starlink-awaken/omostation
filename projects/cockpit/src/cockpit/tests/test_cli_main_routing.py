"""CLI 路由测试 — 验证 main() 正确分发到对应 cmd_* 函数。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from cockpit import cli

# Sentinel values for special-case routes
_NO_DISPATCH = "NODISPATCH"
_SYSEXIT = "SYSEXIT"

RouteCase = tuple[list[str], str | None, int | None, int | str]


@pytest.mark.parametrize(
    "argv,target,expected_code_or_signal,expected_note",
    [
        # ── research 路由 (22) ──
        (["workspace", "research", "--search", "AI"], "cmd_research_search", 0, ""),
        (["workspace", "research", "--compare", "1", "2"], "cmd_research_compare", 0, ""),
        (["workspace", "research", "--merge", "1", "2"], "cmd_research_merge", 0, ""),
        (["workspace", "research", "--digest", "1", "2"], "cmd_research_digest", 0, ""),
        (["workspace", "research", "--audit"], "cmd_research_audit", 0, ""),
        (["workspace", "research", "--quarantine", "1"], "cmd_research_quarantine", 0, ""),
        (["workspace", "research", "--restore", "1"], "cmd_research_restore", 0, ""),
        (["workspace", "research", "--heatmap"], "cmd_research_heatmap", 0, ""),
        (["workspace", "research", "--agent", "Alice"], "cmd_research_agent", 0, ""),
        (["workspace", "research", "--list"], "cmd_research_list", 0, ""),
        (["workspace", "research", "--dossier", "1"], "cmd_research_dossier", 0, ""),
        (["workspace", "research", "--timeline", "1"], "cmd_research_timeline", 0, ""),
        (["workspace", "research", "--tag", "1", "--labels", "AI"], "cmd_research_tag", 0, ""),
        (["workspace", "research", "--rename", "1", "--new-title", "New"], "cmd_research_rename", 0, ""),
        (["workspace", "research", "--archive", "1"], "cmd_research_archive", 0, ""),
        (["workspace", "research", "--unarchive", "1"], "cmd_research_unarchive", 0, ""),
        (["workspace", "research", "--publish", "1"], "cmd_research_publish", 0, ""),
        (["workspace", "research", "--export", "markdown", "--open", "1"], "cmd_research_export", 0, ""),
        (["workspace", "research", "--export", "markdown"], None, 1, "export 缺 --open"),
        (["workspace", "research", "--open", "1"], "cmd_research_open", 0, ""),
        (["workspace", "research", "--ask", "1", "追问"], "cmd_research_ask", 0, ""),
        (["workspace", "research", "我的主题"], "cmd_research", 0, ""),
        (["workspace", "research", "--backup"], "cmd_research_backup", 0, ""),
        (["workspace", "research", "--backup-restore", "bk.json"], "cmd_research_backup_restore", 0, ""),
        # ── contracts 路由 (7) ──
        (["workspace", "contracts", "validate"], "cmd_contracts_validate", 0, ""),
        (["workspace", "contracts", "list"], "cmd_contracts_list", 0, ""),
        (["workspace", "contracts", "export-research", "1"], "cmd_contracts_export_research", 0, ""),
        (["workspace", "contracts", "export", "identity"], "cmd_contracts_export_identity", 0, ""),
        (["workspace", "contracts", "export", "event", "--id", "1"], "cmd_contracts_export_event", 0, ""),
        (["workspace", "contracts", "export"], None, 1, "contracts export 无子命令"),
        (["workspace", "contracts", "unknown"], _SYSEXIT, 2, "未知子命令报错"),
        (["workspace", "contracts"], None, 1, "contracts 无子命令"),
        # ── 顶级命令 (8) ──
        (["workspace", "import", "file.md"], "cmd_import", 0, ""),
        (["workspace", "status"], "cmd_status", 0, ""),
        (["workspace", "demo"], "cmd_demo", 0, ""),
        (["workspace", "daily"], "cmd_daily", 0, ""),
        (["workspace", "dashboard"], "cmd_dashboard", 0, ""),
        (["workspace", "help"], "cmd_help", 0, ""),
        (["workspace", "profile"], "cmd_profile", 0, ""),
        (["workspace", "governance"], "cmd_governance", 0, ""),
        # ── 特殊路由 (2) ──
        (["workspace", "product-health"], None, 0, "product-health 直调 subprocess"),
        (["workspace"], _NO_DISPATCH, 0, "无命令 → 欢迎面板"),
    ],
)
def test_main_routing(
    monkeypatch,
    argv: list[str],
    target: str | None,
    expected_code_or_signal: int | None,
    expected_note: str,
) -> None:
    monkeypatch.setattr(sys, "argv", argv)

    if target == _NO_DISPATCH:
        # 无命令 → 打印欢迎面板并返回 0
        code = cli.main()
        assert code == expected_code_or_signal

    elif target == _SYSEXIT:
        # argparse 未知子命令 → sys.exit(code)
        with pytest.raises(SystemExit) as exc:
            cli.main()
        assert exc.value.code == expected_code_or_signal

    elif target is None and expected_note == "export 缺 --open":
        # --export 缺 --open → 直接 return 1
        code = cli.main()
        assert code == 1

    elif target is None and expected_note == "contracts 无子命令":
        # contracts 无子命令 → 直接 return 1
        code = cli.main()
        assert code == 1

    elif target is None and expected_note == "contracts export 无子命令":
        # contracts export 无子命令 → 直接 return 1
        code = cli.main()
        assert code == 1

    elif target is None and expected_note == "product-health 直调 subprocess":
        # product-health → subprocess.run → return 0
        mock_run = MagicMock()
        monkeypatch.setattr(subprocess, "run", mock_run)
        code = cli.main()
        assert code == 0
        mock_run.assert_called_once()

    else:
        # 普通路由 → mock cmd_* → 验证被调用
        mock_fn = MagicMock(return_value=expected_code_or_signal)
        monkeypatch.setattr(cli, target, mock_fn)
        code = cli.main()
        assert code == expected_code_or_signal
        mock_fn.assert_called_once()


def test_cli_module_entry_point():
    """测试 `if __name__ == "__main__":` (cli.py:290) — 作为模块运行 --help"""
    # cockpit 是 /Workspace/cockpit/，需要父目录找到包
    package_root = str(Path(__file__).resolve().parent.parent)
    env = {**os.environ, "PYTHONPATH": str(Path(package_root).parent)}
    result = subprocess.run(
        [sys.executable, "-m", "cockpit.cli", "--help"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"


def test_product_health_returns_subprocess_exit_code(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["workspace", "product-health"])
    monkeypatch.setattr(
        subprocess,
        "run",
        MagicMock(return_value=subprocess.CompletedProcess(["product-health"], 3, stdout="", stderr="boom")),
    )

    assert cli.main() == 3


@pytest.mark.parametrize(
    "argv,target",
    [
        (["workspace", "data", "index"], "cmd_data_index"),
        (["workspace", "data", "types"], "cmd_data_types"),
        (["workspace", "data", "gc"], "cmd_data_gc"),
    ],
)
def test_data_routes_dispatch(monkeypatch, argv: list[str], target: str) -> None:
    monkeypatch.setattr(sys, "argv", argv)
    mock_fn = MagicMock(return_value=0)
    monkeypatch.setattr(cli, target, mock_fn, raising=False)

    code = cli.main()

    assert code == 0
    mock_fn.assert_called_once()
