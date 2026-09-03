#!/usr/bin/env python3
"""cockpit — eCOS v6 L3 入口层。"""

from __future__ import annotations

import argparse
import os
import sys
import time as _time_mod
from urllib import request as urlrequest

from rich import box
from rich.console import Console
from rich.panel import Panel

# ── Shared singletons (defined here so tests can monkeypatch cli.xxx) ──
console = Console()
err = Console(stderr=True)
from .storage import get_data_access

time = _time_mod

# ── Command modules ──
# ── Compatibility re-exports (tests monkeypatch these via cli.xxx) ──
from .commands.agora import cmd_agora
from .commands.audit import cmd_audit
from .commands.base import (
    _SCRIPT_DIR,
    _find_cli,
)
from .commands.bos import (
    cmd_bos_backends,
    cmd_bos_capability,
    cmd_bos_discover,
    cmd_bos_health,
    cmd_bos_list,
    cmd_bos_mutate,
    cmd_bos_read,
    cmd_bos_register,
    cmd_bos_reload,
    cmd_bos_resolve,
    cmd_bos_status,
    cmd_bos_workflow,
)
from .commands.brain import cmd_brain
from .commands.brief import _cmd_brief, _cmd_brief_morning
from .commands.bus import cmd_bus
from .commands.capabilities import cmd_capabilities
from .commands.contracts import (
    cmd_contracts_export_event,
    cmd_contracts_export_identity,
    cmd_contracts_export_research,
    cmd_contracts_list,
    cmd_contracts_validate,
)
from .commands.data import cmd_data_gc, cmd_data_index, cmd_data_types
from .commands.discover import _cmd_discover
from .commands.family_hub import cmd_family_hub
from .commands.gbrain import cmd_gbrain
from .commands.governance import cmd_governance
from .commands.health import _cmd_health
from .commands.importer import cmd_import
from .commands.kairon import cmd_kairon
from .commands.mcp import cmd_mcp
from .commands.mesh import cmd_mesh
from .commands.model_driven import cmd_model_driven
from .commands.observe import cmd_observe
from .commands.profile import cmd_profile
from .commands.research import (
    _cmd_research_batch,
    _notify_research_complete,
    _research_progress,
    cmd_research,
    cmd_research_agent,
    cmd_research_archive,
    cmd_research_ask,
    cmd_research_audit,
    cmd_research_backup,
    cmd_research_backup_restore,
    cmd_research_compare,
    cmd_research_digest,
    cmd_research_dossier,
    cmd_research_export,
    cmd_research_follow_up,
    cmd_research_health,
    cmd_research_heatmap,
    cmd_research_list,
    cmd_research_merge,
    cmd_research_open,
    cmd_research_publish,
    cmd_research_quarantine,
    cmd_research_rename,
    cmd_research_restore,
    cmd_research_search,
    cmd_research_tag,
    cmd_research_timeline,
    cmd_research_unarchive,
)
from .commands.search import _cmd_search
from .commands.spine import cmd_spine
from .commands.status import (
    _render_workbench,
    cmd_daily,
    cmd_dashboard,
    cmd_demo,
    cmd_help,
    cmd_status,
)


def cmd_ssb(a):
    from cockpit.commands.ssb import cmd_ssb as _c

    return _c(a)


def cmd_mof(a):
    from cockpit.commands.mof import cmd_mof as _c

    return _c(a)


def cmd_gac(a):
    """GaC 治理健康检查 (ADR-0106, 调 bin/gac-healthcheck.py). cockpit GaC 集成入口 (第4项)."""
    import subprocess
    from pathlib import Path

    workspace = Path(__file__).resolve().parents[4]  # cli.py→src/cockpit→src→cockpit(proj)→projects→workspace
    r = subprocess.run(
        ["python3", str(workspace / "bin" / "gac" / "gac-healthcheck.py")],
        capture_output=True,
        text=True,
        cwd=str(workspace),
    )
    print(r.stdout or r.stderr or "(无输出)")
    return 0 if r.returncode == 0 else 1


def _c_context(a):
    from cockpit.commands.l4bridge import cmd_context as _c

    return _c(a)


def _c_cards(a):
    from cockpit.commands.l4bridge import cmd_cards as _c

    return _c(a)


def _c_vault(a):
    from cockpit.commands.l4bridge import cmd_vault as _c

    return _c(a)


def _c_domains(a):
    from cockpit.commands.l4bridge import cmd_domains as _c

    return _c(a)


def _c_domain_status(a):
    from cockpit.commands.l4bridge import cmd_domain_status as _c

    return _c(a)


def _c_facts_audit(a):
    from cockpit.commands.l4bridge import cmd_facts_audit as _c

    return _c(a)


def _c_facts_validation(a):
    from cockpit.commands.l4bridge import cmd_facts_validation as _c

    return _c(a)


def _c_model_freshness(a):
    from cockpit.commands.l4bridge import cmd_model_freshness as _c

    return _c(a)


def _c_sanyi_status(a):
    from cockpit.commands.l4bridge import cmd_sanyi_status as _c

    return _c(a)


def _c_controller_shadow(a):
    from cockpit.commands.l4bridge import cmd_controller_shadow as _c

    return _c(a)


def _c_skill(a):
    from cockpit.commands.l4bridge import cmd_skill as _c

    return _c(a)


def _c_events(a):
    from cockpit.commands.events import run_events_dashboard

    url = getattr(a, "url", "http://127.0.0.1:7431/v1/events")
    run_events_dashboard(url)
    return 0


def _c_version(a):
    from cockpit import __version__

    console.print(f"[bold cyan]cockpit[/] v[bold]{__version__}[/]")
    console.print("[dim]L3 统一入口 · 5+4+1+1 架构[/]")
    return 0


def create_parser() -> tuple[argparse.ArgumentParser, argparse._SubParsersAction, type]:
    """构建完整 CLI parser (含全部子命令注册), 供 main() 与 command-audit 共用.

    Returns:
        (parser, sub, WorkspaceParserClass)
    """
    class WorkspaceParser(argparse.ArgumentParser):
        def error(self, message):
            parser_console = Console()
            parser_console.print(f"\n[bold red]✗[/] {message}")
            parser_console.print("[yellow]试试:[/]")
            parser_console.print("  [cyan]cockpit help[/]              — 产品地图（分组目录）")
            parser_console.print("  [cyan]cockpit help memory[/]       — 搜命令/MCP/BOS")
            parser_console.print("  [cyan]cockpit quickstart[/]        — 上手向导")
            parser_console.print('  [cyan]cockpit research "主题"[/]   — 深度研究')
            parser_console.print("  [cyan]cockpit memory[/]            — Memory OS")
            parser_console.print("  [cyan]cockpit demo[/]              — 5 分钟演示")
            parser_console.print()
            sys.exit(2)

        def print_help(self, file=None):
            """Rich 紧凑帮助仅用于顶层; 子命令显示自身参数 (标准 argparse help).

            此前无条件渲染紧凑地图导致所有子命令 --help 都显示全局地图而非自身
            用法, 用户无法了解任何命令的参数/子命令。修复: 子 parser (prog 含
            空格, 如 "cockpit mcp") 回落到 argparse 默认 help。
            """
            if " " in self.prog:
                return super().print_help(file)
            from cockpit.commands.help_map import render_compact_help

            c = Console(file=file) if file is not None else console
            render_compact_help(c)
            # 仍打印全局 flags（output 等）
            c.print("[bold]全局选项[/]")
            c.print("  [cyan]-h, --help[/]                 显示本帮助")
            c.print("  [cyan]--output[/] {text,json,tui,markdown}  输出模式")
            c.print()
            c.print("[dim]完整分组目录: [cyan]cockpit help[/] · 搜能力: [cyan]cockpit help <关键词>[/][/dim]")

    parser = WorkspaceParser(
        prog="cockpit",
        description="Workspace — 产品级统一入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
快速入口:
  cockpit help              产品地图（推荐）
  cockpit help <关键词>     搜 CLI / MCP / BOS
  cockpit memory            Memory OS 控制面
  cockpit research "主题"   深度研究
  cockpit quickstart        上手向导
  cockpit demo              5 分钟演示

示例:
  cockpit research "attention mechanism"
  cockpit memory status --json
  cockpit memory recall "query" --as-of 2024-01-01T00:00:00Z
  cockpit bos resolve bos://memory/mos/status
  cockpit status
  cockpit gac
  cockpit agent status
  cockpit dashboard
  cockpit daily
  cockpit dashboard
        """,
    )
    parser.add_argument(
        "--output",
        "-o",
        dest="global_output",
        choices=["text", "json", "tui", "markdown"],
        default="text",
        help="控制全局输出模式 (传 tui 启动极客终端交互控制台)",
    )
    sub = parser.add_subparsers(dest="command", parser_class=WorkspaceParser)

    # Register all subcommands (extracted to cli/_subcommands.py for SRP, T6-10)
    from ._subcommands import register_subcommands

    register_subcommands(sub, WorkspaceParser)
    return parser, sub, WorkspaceParser


def main() -> int:
    try:
        from kairon_observability.tracing import setup_tracing  # type: ignore[import-not-found]

        setup_tracing("cockpit-cli")
    except ImportError:
        pass  # Skip if observability package isn't installed

    parser, sub, _workspace_parser_cls = create_parser()

    # ── Pre-process: research 默认 create 模式 ──────────────────
    # argparse 子 parser 会贪婪匹配首参为子命令名, 导致 `cockpit research "topic"`
    # 报错. 修复: 若 research 后首参不是已知子命令, 插入 "create" 子命令.
    _research_subcmds = {
        "create", "list", "open", "publish", "dossier", "timeline", "tag", "rename",
        "archive", "unarchive", "export", "ask", "search", "compare", "merge", "digest",
        "audit", "quarantine", "restore", "heatmap", "follow-up", "health", "batch",
        "backup", "backup-restore",
    }
    _argv = sys.argv[1:]
    if len(_argv) >= 2 and _argv[0] == "research":
        _next = _argv[1]
        # 若首参不是子命令也不是以 - 开头, 则插入 "create"
        if not _next.startswith("-") and _next not in _research_subcmds:
            _argv = [_argv[0], "create"] + _argv[1:]

    args, unknown = parser.parse_known_args(_argv)
    # Phase A1: argparse REMAINDER 不捕获前导 option (--help 落入 unknown),
    # 对委派命令拼回 REMAINDER 实现真正透传。
    from .commands.delegation import reclaim_unknown_for_delegation

    unknown = reclaim_unknown_for_delegation(args, unknown)

    # ── Phase 2: --output tui 全自动分流路由 ──
    if getattr(args, "global_output", None) == "tui":
        from cockpit.tui import is_tui_available, launch

        if is_tui_available():
            return launch(args)

    # ── Registry-Based Dispatch ──
    if not args.command:
        console.print(
            Panel.fit(
                "[bold bright_cyan]🛸 Cockpit · L3 统一入口[/bold bright_cyan]\n\n"
                "[bold]先看这里[/]\n"
                "  [cyan]cockpit help[/]               — 产品地图（分组全目录）\n"
                "  [cyan]cockpit help <关键词>[/]      — 搜 CLI / MCP / BOS\n"
                "  [cyan]cockpit quickstart[/]         — 上手向导\n"
                "  [cyan]cockpit memory[/]             — Memory OS 记忆控制面\n\n"
                "[bold]上下文[/]\n"
                "  [cyan]cockpit context[/]          — 系统上下文 (Phase/P0/约束)\n"
                "  [cyan]cockpit cards[/]            — CARDS 卡片列表\n"
                "  [cyan]cockpit cards --check[/]    — 操作合规检查\n"
                "  [cyan]cockpit vault KEY[/]        — 搜索知识库\n"
                "  [cyan]cockpit health[/]           — 一键系统健康\n"
                "  [cyan]cockpit brief[/]            — 会话简报\n\n"
                "[bold]研究对象[/]\n"
                '  [cyan]cockpit research "主题"[/]   — 发起研究\n'
                "  [cyan]cockpit research --list[/]   — 查看历史\n\n"
                "[bold]项目入口[/]\n"
                "  [cyan]cockpit agora[/]            — BOS 服务网关\n"
                "  [cyan]cockpit kairon[/]            — 知识引擎 monorepo\n"
                "  [cyan]cockpit gbrain[/]            — Postgres 知识库\n"
                "  [cyan]cockpit bus[/]               — Omni-Bus 三平面\n"
                "  [cyan]cockpit observe[/]           — Langfuse 可观测性\n"
                "  [cyan]cockpit family-hub[/]        — 家庭数字枢纽\n"
                "  [cyan]cockpit mesh[/]              — 算力网格路由\n"
                "  [cyan]cockpit bos capability[/]    — Toolbox 外部能力\n\n"
                "[bold]工具[/]\n"
                "  [cyan]cockpit search --all KEY[/]  — 跨源搜索 (本地+BOS)\n"
                "  [cyan]cockpit discover[/]           — 发现可用功能\n"
                '  [cyan]cockpit ask "问题"[/]        — 大模型终端问答\n'
                "  [cyan]cockpit proxy-env[/]         — 导出大模型代理环境变量\n"
                "  [cyan]cockpit status[/]            — 工作台\n"
                "  [cyan]cockpit agent-workflow[/]    — Agent 可执行治理流程\n"
                "  [cyan]cockpit agent-runtime[/]     — Agent Runtime 任务 / Server\n"
                "  [cyan]cockpit dashboard[/]         — Web 驾驶舱\n"
                "  [cyan]cockpit mcp[/]               — MCP Server\n"
                "  [cyan]cockpit demo[/]              — 5 分钟体验\n"
                "  [cyan]cockpit code analyze[/]      — 代码分析\n"
                "  [cyan]cockpit version[/]           — 版本信息\n\n"
                "[dim]快捷键: F1帮助 · Ctrl+C 退出[/]",
                border_style="cyan",
                box=box.ROUNDED,
            )
        )
        return 0

    def dispatch_research(a, unknown_args=None):
        """子命令路由: 优先 research_command, 否则回退到 topic (create 模式).

        unknown_args: parse_known_args 返回的未消费参数, 用于默认 create 模式.
        将新属性名映射回 handler 期望的旧属性名, 避免大规模修改 research.py.
        """
        cmd = getattr(a, "research_command", None)
        # 辅助: 将新 id 映射到旧属性名 (各 handler 用不同名)
        _id = getattr(a, "id", None)
        _ids = getattr(a, "ids", [])

        if cmd == "create":
            a.topic = getattr(a, "topic", [])
            return cmd_research(a)
        if cmd == "list":
            return cmd_research_list(a)
        if cmd == "open":
            a.open = _id
            return cmd_research_open(a)
        if cmd == "publish":
            a.publish = _id
            return cmd_research_publish(a)
        if cmd == "dossier":
            a.dossier = _id
            return cmd_research_dossier(a)
        if cmd == "timeline":
            a.timeline = _id
            return cmd_research_timeline(a)
        if cmd == "tag":
            a.tag = _id
            return cmd_research_tag(a)
        if cmd == "rename":
            a.rename = _id
            return cmd_research_rename(a)
        if cmd == "archive":
            a.archive = _ids or None
            a.all_active = getattr(a, "all_active", False)
            return cmd_research_archive(a)
        if cmd == "unarchive":
            a.unarchive = _ids or None
            a.all_active = getattr(a, "all_active", False)
            return cmd_research_unarchive(a)
        if cmd == "export":
            a.export = getattr(a, "format", "markdown")
            a.open = _id  # export 用 --open 传 id
            return cmd_research_export(a)
        if cmd == "ask":
            a.ask = _id
            return cmd_research_ask(a)
        if cmd == "search":
            a.search = getattr(a, "keyword", "")
            a.limit = getattr(a, "limit", 10)
            return cmd_research_search(a)
        if cmd == "compare":
            a.compare = _ids
            return cmd_research_compare(a)
        if cmd == "merge":
            a.merge = _ids
            return cmd_research_merge(a)
        if cmd == "digest":
            a.digest = _ids
            return cmd_research_digest(a)
        if cmd == "audit":
            return cmd_research_audit(a)
        if cmd == "quarantine":
            a.quarantine = _ids
            return cmd_research_quarantine(a)
        if cmd == "restore":
            a.restore = _ids
            return cmd_research_restore(a)
        if cmd == "heatmap":
            return cmd_research_heatmap(a)
        if cmd == "follow-up":
            a.follow_up = True
            return cmd_research_follow_up(a)
        if cmd == "health":
            a.health = True
            return cmd_research_health(a)
        if cmd == "batch":
            a.topic = getattr(a, "topics", [])
            a.batch = True
            return _cmd_research_batch(a)
        if cmd == "backup":
            a.backup = getattr(a, "output", None) or ""
            return cmd_research_backup(a)
        if cmd == "backup-restore":
            a.backup_restore = getattr(a, "path", None)
            return cmd_research_backup_restore(a)
        # 无子命令: 默认 create 模式 (unknown_args 即 topic)
        a.topic = unknown_args or getattr(a, "topic", [])
        return cmd_research(a)

    def dispatch_code(a):
        if getattr(a, "code_command", "") == "workflow":
            from cockpit.commands.code import cmd_code_workflow

            return cmd_code_workflow(a)
        elif getattr(a, "code_command", ""):
            from cockpit.commands.code import cmd_code_base

            return cmd_code_base(a)
        # Fallback: 给出用法提示
        console.print(
            "[yellow]缺少子命令。[/]\n"
            "[dim]用法: cockpit code {analyze|graph|pack|dashboard|workflow}[/]\n"
            "  [cyan]analyze[/]    运行全部分析工具\n"
            "  [cyan]graph[/]      运行语义图谱分析\n"
            "  [cyan]pack[/]       将代码库打包为 LLM 友好格式\n"
            "  [cyan]dashboard[/]  启动交互式知识图谱仪表盘\n"
            "  [cyan]workflow[/]   高级分析工作流 (impact/onboarding)\n"
            "[dim]详情: cockpit code --help[/]"
        )
        return 1

    def dispatch_cards(a):
        if getattr(a, "cards_command", None):
            from cockpit.commands.cards import cmd_cards as _cmd

            return _cmd(a)
        from cockpit.commands.l4bridge import cmd_cards as _cmd

        return _cmd(a)

    def dispatch_bos(a):
        sub = getattr(a, "bos_cmd", "")
        if sub == "list":
            return cmd_bos_list(a)
        elif sub == "discover":
            return cmd_bos_discover(a)
        elif sub == "resolve":
            return cmd_bos_resolve(a)
        elif sub == "read":
            return cmd_bos_read(a)
        elif sub == "capability":
            return cmd_bos_capability(a)
        elif sub == "inbox":
            from cockpit.commands.bos_inbox import cmd_bos_inbox

            return cmd_bos_inbox(a)
        elif sub == "health":
            return cmd_bos_health(a)
        elif sub == "backends":
            return cmd_bos_backends(a)
        elif sub == "reload":
            return cmd_bos_reload(a)
        elif sub == "register":
            return cmd_bos_register(a)
        elif sub == "workflow":
            return cmd_bos_workflow(a)
        elif sub == "mutate":
            return cmd_bos_mutate(a)
        else:
            return cmd_bos_status(a)

    def dispatch_bus(a):
        return cmd_bus(a)

    def dispatch_observe(a):
        return cmd_observe(a)

    def dispatch_family_hub(a):
        return cmd_family_hub(a)

    def dispatch_mesh(a):
        return cmd_mesh(a)

    def dispatch_spine(a):
        return cmd_spine(a)

    def dispatch_render(a):
        from cockpit.commands.render import cmd_render

        return cmd_render(a)

    def dispatch_im_triage(a):
        from cockpit.commands.im_triage import cmd_im_triage

        return cmd_im_triage(a)

    def dispatch_dlp_guard(a):
        from cockpit.commands.dlp_guard import cmd_dlp_guard

        return cmd_dlp_guard(a)

    def dispatch_scenario(a):
        from cockpit.commands.scenario import cmd_scenario

        return cmd_scenario(a)

    def dispatch_iterate(a):
        from cockpit.commands.iterate import cmd_iterate

        return cmd_iterate(a)

    def _dispatch_debt(a):
        """cockpit debt 子命令路由: score → 评分算法, 其他 → omo debt 委派."""
        sub = getattr(a, "debt_subcommand", None)
        if sub == "score" or sub is None:
            from cockpit.commands.debt_scoring import cmd_debt_score

            return cmd_debt_score(a)
        # 其他子命令 (list/summary/predict 等) 委派给 omo debt
        # 子命令名作为 omo debt 首参 (cockpit debt list → omo debt list)
        from cockpit.commands.omo import cmd_omo_debt

        a.omo_debt_args = [sub] + list(getattr(a, "omo_debt_args", []))

        return cmd_omo_debt(a)

    def dispatch_agent_runtime(a):
        from cockpit import agent_runtime_cli

        argv: list[str] = []
        if getattr(a, "prompt", None):
            argv.extend(["--prompt", a.prompt])
        if getattr(a, "task", None):
            argv.extend(["--task", a.task])
        if getattr(a, "model", None):
            argv.extend(["--model", a.model])
        if getattr(a, "tools", None):
            argv.extend(["--tools", *a.tools])
        if getattr(a, "server", None):
            argv.append("--server")
        if getattr(a, "port", None) is not None:
            argv.extend(["--port", str(a.port)])
        return agent_runtime_cli.run_agent_runtime(argv)

    def dispatch_compass(a):
        import subprocess

        workspace_root = _SCRIPT_DIR.parents[4].resolve()
        omo_project_path = (workspace_root / "projects" / "omo").resolve()
        cmd = [
            "uv",
            "run",
            "--project",
            str(omo_project_path),
            "c2g",
            "--adapter",
            "ecos",
            *getattr(a, "compass_args", []),
        ]
        # 清 VIRTUAL_ENV 避免 uv venv 冲突 (cockpit → c2g subprocess 继承父环境)
        env = {k: v for k, v in os.environ.items() if not k.startswith("VIRTUAL_ENV") and k != "PYTHONHOME"}
        return subprocess.call(cmd, cwd=str(workspace_root), env=env)

    def dispatch_bdsk(a):
        subcmd = getattr(a, "bdsk_subcmd", "debate")
        if subcmd == "simulate":
            import subprocess

            ws_root = (_SCRIPT_DIR.parent.parent.parent.parent.parent).resolve()
            script_path = ws_root / "bin" / "gac" / "bdsk-shadow-sandbox.py"
            return subprocess.call([sys.executable, str(script_path)], cwd=str(ws_root))

        from cockpit.commands.bdsk_engine import DynamicBDSKAdjudicator

        topic = getattr(a, "topic", "架构决策与技术选型")
        res = DynamicBDSKAdjudicator.adjudicate(topic)

        if res.get("proof_state") != "proven":
            print("=========================================================================")
            print(" 🧠 B.D.S.K. 虚拟董事会 ➔ NOT_PROVEN")
            print(" 🔗 bos://persona/bdsk/evaluate → bos://compute/aetherforge/infer")
            print(f" ⚠️ 评估未成立: {res.get('error_code', 'unknown')}")
            print("=========================================================================")
            return 4

        print("=========================================================================")
        print(" 🧠 B.D.S.K. 虚拟董事会 ➔ BOS/AetherForge PROVEN")
        print(f" 🔐 议题摘要: {res['topic_digest']}")
        print("=========================================================================")
        print("🧑‍💻 Builder (建造者/技术合伙人):")
        print(f"  • {res['builder']}")
        print("⚡️ Devil (批判者/风控官):")
        print(f"  • {res['devil']}")
        print("🧠 Sage (贤者/战略家):")
        print(f"  • {res['sage']}")
        print("👁️ Keeper (守夜人/观察者):")
        print(f"  • {res['keeper']}")
        print("=========================================================================")
        print(f"💡 4 角共识建议: {res['conclusion']}")
        print(f"📊 风险分: {res['risk_score']} | 状态: {res['verdict']}")
        print("=========================================================================")
        return 0

    def dispatch_journey(a):
        """Journey 状态图校验 — 直接运行 journey-runner."""
        import subprocess

        ws_root = (_SCRIPT_DIR.parent.parent.parent.parent.parent).resolve()
        runner = str(ws_root / "bin" / "ssot" / "journey-runner.py")
        # 无额外参数时跑 validate, 有参数则透传
        args = getattr(a, "journey_args", [])
        if not args:
            return subprocess.call(["python3", runner, "validate"])
        return subprocess.call(["python3", runner, *args])

    def dispatch_panorama(a):
        import subprocess

        omo_project = str((_SCRIPT_DIR.parent.parent.parent.parent / "omo").resolve())
        cmd = ["uv", "run", "--project", omo_project, "python", "-m", "omo.cli", "panorama"]
        if getattr(a, "json", False):
            cmd.append("--json")
        env = {k: v for k, v in os.environ.items() if not k.startswith("VIRTUAL_ENV") and k != "PYTHONHOME"}
        return subprocess.call(cmd, env=env)

    def dispatch_project(a):
        import subprocess

        omo_project = str((_SCRIPT_DIR.parent.parent.parent.parent / "omo").resolve())
        subcmd = getattr(a, "project_subcmd", "inspect")
        pname = getattr(a, "project_name", "")
        cmd = ["uv", "run", "--project", omo_project, "python", "-m", "omo.cli", "project", subcmd]
        if pname:
            cmd.append(pname)
        if getattr(a, "json", False):
            cmd.append("--json")
        env = {k: v for k, v in os.environ.items() if not k.startswith("VIRTUAL_ENV") and k != "PYTHONHOME"}
        return subprocess.call(cmd, env=env)

    def dispatch_wave2(a):
        from cockpit.commands.wave2 import cmd_wave2

        return cmd_wave2(a)

    def dispatch_workflow(a):
        wf_args = getattr(a, "workflow_args", [])
        # workflow mesh 子命令路由到 workflow_mesh 模块
        if wf_args and wf_args[0] == "mesh":
            from cockpit.commands.workflow_mesh import cmd_workflow_mesh

            # personal dogfood CLI (thin HTTP client)
            if len(wf_args) > 1 and wf_args[1] == "personal":
                from cockpit.commands.workflow_mesh import cmd_personal

                personal_args = argparse.Namespace(
                    personal_command=wf_args[2] if len(wf_args) > 2 else None,
                    rest=wf_args[3:] if len(wf_args) > 3 else [],
                )
                return cmd_personal(personal_args)

            mesh_args = argparse.Namespace(mesh_command=wf_args[1] if len(wf_args) > 1 else None)
            if len(wf_args) > 2 and wf_args[1] == "events":
                try:
                    mesh_args.limit = int(wf_args[2])
                except (ValueError, IndexError):
                    mesh_args.limit = 20
            return cmd_workflow_mesh(mesh_args)
        from cockpit.commands.workflow import handle_workflow

        return handle_workflow(wf_args)

    def dispatch_agent_workflow(a):
        from cockpit.commands.agent_workflow import cmd_agent_workflow

        return cmd_agent_workflow(a)

    def dispatch_agent_onboard(a):
        from cockpit.commands.agent_onboard import cmd_agent_onboard

        return cmd_agent_onboard(a)

    def dispatch_monitor(a):
        from cockpit.commands.monitor import cmd_monitor

        return cmd_monitor(a)

    def dispatch_data(a):
        if getattr(a, "data_command", "") == "index":
            return cmd_data_index(a)
        if getattr(a, "data_command", "") == "types":
            return cmd_data_types(a)
        if getattr(a, "data_command", "") == "gc":
            return cmd_data_gc(a)
        console.print(
            "[yellow]缺少子命令。[/]\n"
            "[dim]用法: cockpit data {index|types|gc}[/]\n"
            "  [cyan]index[/]  刷新 data/_index 元数据\n"
            "  [cyan]types[/]  查看已注册的数据类型\n"
            "  [cyan]gc[/]     清理 data/tmp 过期文件\n"
            "[dim]详情: cockpit data --help[/]"
        )
        return 1

    def dispatch_contracts(a):
        if getattr(a, "contracts_command", "") == "validate":
            return cmd_contracts_validate(a)
        if getattr(a, "contracts_command", "") == "list":
            return cmd_contracts_list(a)
        if getattr(a, "contracts_command", "") == "export-research":
            return cmd_contracts_export_research(a)
        if getattr(a, "contracts_command", "") == "export":
            if getattr(a, "contracts_export_type", "") == "identity":
                return cmd_contracts_export_identity(a)
            elif getattr(a, "contracts_export_type", "") == "event":
                return cmd_contracts_export_event(a)
        # 裸 `cockpit contracts` / 未知子命令: 给出用法而非静默 rc=1
        console.print(
            "[yellow]缺少子命令。[/]\n"
            "[dim]用法: cockpit contracts {validate|list|export-research|export}[/]\n"
            "  [cyan]validate[/]          验证 Workspace 契约\n"
            "  [cyan]list[/]              列出所有已注册 Schema\n"
            "  [cyan]export-research[/]   将研究对象导出为 WorkspaceObject JSON\n"
            "  [cyan]export identity[/]   导出身份封套\n"
            "  [cyan]export event[/]      导出事件封套\n"
            "[dim]详情: cockpit contracts --help[/]"
        )
        return 1

    def cmd_product_health(a):
        import subprocess as _sp
        import sys

        result = _sp.run([sys.executable, str(_SCRIPT_DIR / "product-health")])
        returncode = getattr(result, "returncode", 0)
        return returncode if isinstance(returncode, int) else 0

    def cmd_context(a):
        from cockpit.commands.l4bridge import cmd_context as _c

        return _c(a)

    def cmd_cards(a):
        from cockpit.commands.l4bridge import cmd_cards as _c

        return _c(a)

    def cmd_vault(a):
        from cockpit.commands.l4bridge import cmd_vault as _c

        return _c(a)

    def cmd_domains(a):
        from cockpit.commands.l4bridge import cmd_domains as _c

        return _c(a)

    def cmd_skill(a):
        from cockpit.commands.l4bridge import cmd_skill as _c

        return _c(a)

    def cmd_events(a):
        from cockpit.commands.events import run_events_dashboard

        run_events_dashboard(a.url)
        return 0

    def cmd_version(a):
        from cockpit import __version__

        console.print(f"[bold cyan]cockpit[/] v[bold]{__version__}[/]")
        console.print("[dim]L3 统一入口 · 5+4+1+1 架构[/]")
        return 0

    def cmd_compute(a):
        from cockpit.commands.compute import cmd_compute as _c

        return _c(a)

    handlers = {
        "import": cmd_import,
        "mcp": cmd_mcp,
        "daily": cmd_daily,
        "status": cmd_status,
        "context": _c_context,
        "version": _c_version,
        "health": _cmd_health,
        "brief": lambda a: _cmd_brief_morning(a) if getattr(a, "morning", False) else _cmd_brief(a),
        "discover": _cmd_discover,
        "capabilities": cmd_capabilities,
        "profile": cmd_profile,
        "cards": dispatch_cards,
        "audit": cmd_audit,
        "demo": cmd_demo,
        "search": _cmd_search,
        "dashboard": cmd_dashboard,
        "vault": _c_vault,
        "bos": dispatch_bos,
        "code": dispatch_code,
        "research": lambda a: dispatch_research(a, unknown),
        "scenario": dispatch_scenario,
        "iterate": dispatch_iterate,
        "compass": dispatch_compass,
        "bdsk": dispatch_bdsk,
        "journey": dispatch_journey,
        "panorama": dispatch_panorama,
        "project": dispatch_project,
        "wave2": dispatch_wave2,
        "workflow": dispatch_workflow,
        "agent-workflow": dispatch_agent_workflow,
        "agent": dispatch_agent_workflow,
        "agent-onboard": dispatch_agent_onboard,
        "agent-runtime": dispatch_agent_runtime,
        "monitor": dispatch_monitor,
        "data": dispatch_data,
        "contracts": dispatch_contracts,
        "product-health": cmd_product_health,
        "gongwen": lambda a: __import__("cockpit.commands.gongwen", fromlist=["cmd_gongwen"]).cmd_gongwen(a),
        "finance": lambda a: __import__("cockpit.commands.finance", fromlist=["cmd_finance"]).cmd_finance(a),
        "governance": cmd_governance,
        "domains": _c_domains,
        "domain-status": _c_domain_status,
        "facts-audit": _c_facts_audit,
        "facts-validation": _c_facts_validation,
        "model-freshness": _c_model_freshness,
        "sanyi-status": _c_sanyi_status,
        "controller-shadow": _c_controller_shadow,
        "skill": _c_skill,
        "events": _c_events,
        "ssb": cmd_ssb,
        "mof": cmd_mof,
        "agora": cmd_agora,
        "model-driven": cmd_model_driven,
        "brain": cmd_brain,
        "gbrain": cmd_gbrain,
        "kairon": cmd_kairon,
        "bus": dispatch_bus,
        "observe": dispatch_observe,
        "family-hub": dispatch_family_hub,
        "mesh": dispatch_mesh,
        "spine": dispatch_spine,
        "render": dispatch_render,
        "im-triage": dispatch_im_triage,
        "dlp-guard": dispatch_dlp_guard,
        "compute": cmd_compute,
        "intent": lambda a: __import__("cockpit.commands.intent", fromlist=["cmd_intent"]).cmd_intent(a),
        "decide": lambda a: __import__("cockpit.commands.decide", fromlist=["cmd_decide"]).cmd_decide(a),
        "challenge": lambda a: __import__("cockpit.commands.challenge", fromlist=["cmd_challenge"]).cmd_challenge(a),
        "cartridge": lambda a: __import__("cockpit.commands.cartridge", fromlist=["cmd_cartridge"]).cmd_cartridge(a),
        "cell": lambda a: __import__("cockpit.commands.cell", fromlist=["cmd_cell"]).cmd_cell(a),
        "fabric": lambda a: __import__("cockpit.commands.fabric", fromlist=["cmd_fabric"]).cmd_fabric(a),
        "gac": cmd_gac,
        "omo": lambda a: __import__("cockpit.commands.omo", fromlist=["cmd_omo"]).cmd_omo(a),
        "resident": lambda a: __import__("cockpit.commands.resident", fromlist=["cmd_resident"]).cmd_resident(a),
        "bcos": lambda a: __import__("cockpit.commands.bcos", fromlist=["cmd_bcos"]).cmd_bcos(a),
        "runtime": lambda a: __import__("cockpit.commands.runtime", fromlist=["cmd_runtime"]).cmd_runtime(a),
        "help": cmd_help,
        "quickstart": lambda a: __import__("cockpit.commands.quickstart", fromlist=["cmd_quickstart"]).cmd_quickstart(
            a
        ),
        "init": lambda a: __import__("cockpit.commands.quickstart", fromlist=["cmd_quickstart"]).cmd_quickstart(a),
        # P66 增: readiness dashboard 子命令 (升级自 P65 wrapper)
        "readiness": lambda a: __import__("cockpit.commands.readiness", fromlist=["cmd_readiness"]).cmd_readiness(a),
        "debt": lambda a: _dispatch_debt(a),
        "knowledge": lambda a: __import__("cockpit.commands.knowledge", fromlist=["cmd_knowledge"]).cmd_knowledge(a),
        "memory": lambda a: __import__("cockpit.commands.memory", fromlist=["cmd_memory"]).cmd_memory(a),
        "kems": lambda a: __import__("cockpit.commands.kems", fromlist=["cmd_kems"]).cmd_kems(a),
        "c2g": lambda a: __import__("cockpit.commands.c2g", fromlist=["cmd_c2g"]).cmd_c2g(a),
        "channels": lambda a: __import__("cockpit.commands.channels", fromlist=["cmd_channels"]).cmd_channels(a),
        "swarm": lambda a: __import__("cockpit.commands.swarm", fromlist=["cmd_swarm"]).cmd_swarm(a),
        "tui": lambda a: __import__("cockpit.tui", fromlist=["launch"]).launch(a),
        "bos-capability": lambda a: __import__(
            "cockpit.commands.bos", fromlist=["cmd_bos_capability"]
        ).cmd_bos_capability(a),
        "ask": lambda a: __import__("cockpit.commands.ask", fromlist=["cmd_ask"]).cmd_ask(a),
        "proxy-env": lambda a: __import__("cockpit.commands.ask", fromlist=["cmd_proxy_env"]).cmd_proxy_env(a),
        "bos-inbox": lambda a: __import__("cockpit.commands.bos_inbox", fromlist=["cmd_bos_inbox"]).cmd_bos_inbox(a),
        "ops": lambda a: __import__("cockpit.commands.ops", fromlist=["cmd_ops"]).cmd_ops(a),
        "events-watch": lambda a: _c_events(
            __import__("argparse").Namespace(watch=True, limit=getattr(a, "limit", 20), topic=None)
        ),
        "quickstart-check": lambda a: __import__(
            "cockpit.commands.quickstart", fromlist=["cmd_quickstart"]
        ).cmd_quickstart(__import__("argparse").Namespace(check=True, json=getattr(a, "json", False))),
        "watchdog": lambda a: __import__("cockpit.commands.watchdog", fromlist=["cmd_watchdog"]).cmd_watchdog(a),
        "policy": lambda a: __import__("ecos.cli.constraint", fromlist=["main"]).main(
            ["policy"] + getattr(a, "policy_args", [])
        ),
        # Phase C/D: chain / command-audit (延迟 import, 模块未落地时 parser 侧已跳过注册)
        "chain": lambda a: __import__("cockpit.chain", fromlist=["cmd_chain"]).cmd_chain(a),
        "command-audit": lambda a: __import__(
            "cockpit.commands.command_audit", fromlist=["cmd_command_audit"]
        ).cmd_command_audit(a),
    }
    # Phase B: 并入薄委派命令组 handlers (gac/adr/sweep/project_cli/root_bin)
    from .commands.delegation import DELEGATED_COMMANDS, inject_empty_help

    handlers.update(DELEGATED_COMMANDS)

    # Phase A1: 存量 REMAINDER 委派命令空参回退 → 注入 --help (裸命令显示下游帮助)
    inject_empty_help(args)

    global_output = getattr(args, "global_output", "text")
    if global_output == "tui":
        return __import__("cockpit.tui", fromlist=["launch"]).launch(args)

    # Phase A4: --output json 探测式分发 (JSON_CAPABLE 内命令注入 --json, 不静默)
    if global_output == "json":
        from .commands.output_mode import apply_json_mode

        apply_json_mode(args)

    handler = handlers.get(args.command)
    if handler:
        if (
            global_output == "text"
            and args.command not in ("tui", "help", "demo")
            and sys.stdout.isatty()
        ):
            try:
                from .commands.base import render_command_header
                from .commands.registry import COMMAND_CATALOG

                meta = COMMAND_CATALOG.get(args.command)
                title = f"{args.command.upper()}  ·  {meta.summary}" if meta else args.command.upper()
                render_command_header(title=title, category=meta.category if meta else "SYSTEM")
            except Exception:
                pass
        return handler(args)

    console.print(f"[red]未知命令: {args.command}[/]")
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
