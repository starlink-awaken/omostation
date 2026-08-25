"""并行入口退役测试 (t1-12) — daemon 与 governance auto-fix 入口必须不可达。

背景: d8af11c2 上的 `cockpit daemon` 与 `cockpit governance auto-fix` 是
未绑定能力的并行入口（绕过既有 omo/resident 路由），予以退役。
本文件锁定退役状态，防止回归；同时保护 cartridge 等无关入口不受牵连。
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import inspect


def _build_parser() -> argparse.ArgumentParser:
    """以与 cli.main() 相同的方式构建 cockpit 顶层 parser。"""
    parser = argparse.ArgumentParser(prog="cockpit")
    sub = parser.add_subparsers(dest="command")
    from cockpit._subcommands import register_subcommands

    register_subcommands(sub, argparse.ArgumentParser)
    return parser


# ── daemon 入口退役 ────────────────────────────────────────


def test_daemon_subcommand_absent_from_parser() -> None:
    parser = _build_parser()
    action = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    assert "daemon" not in action.choices, "`cockpit daemon` 子命令应已退役"


def test_daemon_argv_unparseable() -> None:
    parser = _build_parser()
    try:
        parser.parse_args(["daemon"])
    except SystemExit as e:
        assert e.code == 2
    else:
        raise AssertionError("`cockpit daemon` 应无法解析 (expected SystemExit 2)")


def test_daemon_module_absent() -> None:
    assert importlib.util.find_spec("cockpit.commands.daemon") is None, "cockpit/commands/daemon.py 应已删除"


def test_cli_has_no_daemon_route() -> None:
    from cockpit import cli

    src = inspect.getsource(cli)
    assert "commands.daemon" not in src, "cli.py 不应再 import cockpit.commands.daemon"
    assert '"daemon"' not in src, "cli.py handlers 不应再注册 daemon 路由"


# ── governance auto-fix 分支退役 ───────────────────────────


def test_governance_auto_fix_unparseable() -> None:
    parser = _build_parser()
    try:
        parser.parse_args(["governance", "auto-fix"])
    except SystemExit as e:
        assert e.code == 2
    else:
        raise AssertionError("`cockpit governance auto-fix` 应无法解析 (expected SystemExit 2)")


def test_governance_module_has_no_auto_fix_branch() -> None:
    from cockpit.commands import governance

    src = inspect.getsource(governance)
    assert '"auto-fix"' not in src and "'auto-fix'" not in src, "governance.py 不应再保留 auto-fix 分支"
    assert "auto-fix-loop.py" not in src, "governance.py 不应再调用 bin/gac/auto-fix-loop.py"


# ── TUI 采集/顶栏 daemon 布线退役 ─────────────────────────


def test_swarm_collector_has_no_daemon_probe() -> None:
    from cockpit.tui import swarm_collector

    src = inspect.getsource(swarm_collector)
    assert "collect_daemon" not in src, "SwarmStateCollector 不应再探测 Agora daemon"
    field_names = [f.name for f in dataclasses.fields(swarm_collector.SwarmGlobalState)]
    assert "daemon" not in field_names, "SwarmGlobalState 不应再携带 daemon 字段"


def test_swarm_cli_top_bar_has_no_bus_indicator() -> None:
    from cockpit.tui import swarm_cli

    src = inspect.getsource(swarm_cli)
    assert "BUS :7432" not in src, "swarm 顶栏不应再渲染 BUS :7432 daemon 指示灯"
    assert "state.daemon" not in src, "swarm_cli 不应再读取 SwarmGlobalState.daemon"


# ── 无关入口保护 (cartridge 等) ───────────────────────────


def test_cartridge_subcommand_still_present() -> None:
    parser = _build_parser()
    action = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    assert "cartridge" in action.choices, "退役不得牵连 `cockpit cartridge` (ADR-0198/0203)"


def test_governance_core_subcommands_still_present() -> None:
    parser = _build_parser()
    action = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    gov = action.choices["governance"]
    subcommand_choices = next(a.choices for a in gov._actions if a.dest == "subcommand")
    for kept in ("surfaces", "report", "verify", "drift-check"):
        assert kept in subcommand_choices, f"退役不得牵连 `cockpit governance {kept}`"
