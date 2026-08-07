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
from .commands.brief import _cmd_brief
from .commands.bus import cmd_bus
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


def _c_skill(a):
    from cockpit.commands.l4bridge import cmd_skill as _c

    return _c(a)


def _c_events(a):
    from cockpit.commands.events import run_events_dashboard

    run_events_dashboard(a.url)
    return 0


def _c_version(a):
    from cockpit import __version__

    console.print(f"[bold cyan]cockpit[/] v[bold]{__version__}[/]")
    console.print("[dim]L3 统一入口 · 5+4+1+1 架构[/]")
    return 0


def main() -> int:
    try:
        from kairon_observability.tracing import setup_tracing  # type: ignore[import-not-found]

        setup_tracing("cockpit-cli")
    except ImportError:
        pass  # Skip if observability package isn't installed

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

    r = sub.add_parser("research", help="深度研究")
    r.add_argument("topic", nargs="*", help="研究主题")
    r.add_argument("--list", action="store_true", help="查看研究历史")
    r.add_argument("--open", type=int, metavar="ID", help="打开研究全文")
    r.add_argument("--publish", type=int, metavar="ID", help="发布研究为正式 Markdown 报告")
    r.add_argument("--style", choices=["brief", "report", "memo"], default="report", help="publish 的输出风格")
    r.add_argument("--dossier", type=int, metavar="ID", help="查看研究的关系与产物视图")
    r.add_argument("--timeline", type=int, metavar="ID", help="查看研究的演化时间线")
    r.add_argument("--tag", type=int, metavar="ID", help="为研究添加/覆盖标签")
    r.add_argument("--labels", nargs="+", help="tag 操作使用的标签列表")
    r.add_argument("--rename", type=int, metavar="ID", help="重命名研究标题")
    r.add_argument("--new-title", nargs="+", help="rename 操作使用的新标题")
    r.add_argument("--archive", type=int, nargs="+", metavar="ID", help="归档研究记录")
    r.add_argument("--unarchive", type=int, nargs="+", metavar="ID", help="恢复已归档研究记录")
    r.add_argument("--all-active", action="store_true", help="对全部活跃研究执行 --archive/--unarchive 操作")
    r.add_argument("--export", type=str, metavar="FORMAT", help="导出研究 (markdown/text/json)")
    r.add_argument("--ask", type=int, metavar="ID", help="对指定研究发起追问，后接问题")
    r.add_argument("--search", type=str, metavar="KEYWORD", help="全文搜索")
    r.add_argument("--compare", type=int, nargs="+", metavar="ID", help="对比多个研究结果")
    r.add_argument("--merge", type=int, nargs="+", metavar="ID", help="合并多个研究结果为新研究")
    r.add_argument("--digest", type=int, nargs="+", metavar="ID", help="提炼多个研究结果为 digest")
    r.add_argument("--audit", action="store_true", help="扫描可疑研究记录")
    r.add_argument("--quarantine", type=int, nargs="+", metavar="ID", help="隔离可疑研究记录")
    r.add_argument("--restore", type=int, nargs="+", metavar="ID", help="恢复已隔离研究记录")
    r.add_argument("--limit", type=int, default=10)
    r.add_argument("--status", choices=["active", "archived", "all"], default="all", help="研究列表筛选（默认 all）")
    r.add_argument("--agent", type=str, metavar="NAME", help="标记/查询处理 Agent (如 minerva, sophia)")
    r.add_argument("--heatmap", action="store_true", help="显示研究活跃度热力图")
    r.add_argument("--follow-up", action="store_true", help="查看追问工作台（待追问/已回答统计）")
    r.add_argument("--health", action="store_true", help="查看研究健康报告（衰减状态/保鲜建议）")
    r.add_argument("--batch", action="store_true", help="批量研究模式: 逐个处理多个 topic，汇总结果")
    r.add_argument("--stream", action="store_true", help="流式输出 (ollama 逐 token 打印)")
    r.add_argument(
        "--backup",
        nargs="?",
        const="",
        metavar="OUTPUT",
        help="全量备份研究数据到 JSON 文件（默认 ~/Desktop/workspace_backup.json）",
    )
    r.add_argument("--backup-restore", type=str, metavar="PATH", help="从备份 JSON 文件恢复研究数据")
    r.add_argument("--json", action="store_true", help="以 JSON 格式输出（--list 和 --open 模式可用）")

    import_p = sub.add_parser("import", help="导入外部内容")
    import_p.add_argument("source", help="URL 或本地文件路径")

    status_p = sub.add_parser("status", help="系统健康")
    status_p.add_argument("--watch", action="store_true", help="持续监控并自动刷新")
    status_p.add_argument("--interval", type=float, default=5.0, help="监控刷新间隔（秒）")
    status_p.add_argument("--json", action="store_true", help="以 JSON 格式输出")

    # P66 增: readiness dashboard 子命令 (从 P65 wrapper 升级)
    from cockpit.commands import readiness as _readiness_mod

    readiness_p = sub.add_parser(
        "readiness",
        help="P66: governance readiness dashboard 摘要 (4 卡片: summary/dimensions/alerts/history)",
    )
    readiness_p.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="输出格式 (默认 json, 适合 dashboard 消费)",
    )
    readiness_p.add_argument("--output", help="输出文件路径 (默认 stdout)")
    readiness_p.set_defaults(func=_readiness_mod.cmd_readiness)

    # omo / runtime 委派子命令 (后端 cockpit.commands.{omo,runtime}.py 已实现 cmd_omo/cmd_runtime,
    # 补 argparse 注册. 修复声明/执行鸿沟: dispatch dict 有 lambda 但缺 add_parser → invalid choice)
    omo_p = sub.add_parser(
        "omo",
        help="OMO CLI 委派 (debt/state/governance/lint/...)",
    )
    omo_p.add_argument(
        "omo_args",
        nargs=argparse.REMAINDER,
        help="传给 omo CLI 的参数 (如 'debt list', 'state sync --dry-run')",
    )

    # debt — omo-debt 收编入口 (直接调用 omo-debt 评分算法, ADR-0122 F-13)
    from cockpit.commands import debt_scoring as _debt_mod

    debt_p = sub.add_parser(
        "debt",
        help="债务评分 (omo-debt Pattern 09 v2.1)",
    )
    debt_sub = debt_p.add_subparsers(dest="debt_subcommand")
    debt_score_p = debt_sub.add_parser("score", help="评分债务项")
    debt_score_p.add_argument("impact", type=int, nargs="?", default=5, help="影响 (1-10)")
    debt_score_p.add_argument("frequency", type=int, nargs="?", default=5, help="频率 (1-10)")
    debt_score_p.add_argument("cost", type=int, nargs="?", default=5, help="修复成本 (1-10)")
    debt_score_p.add_argument("--stage", default="stable_growth", help="项目阶段")
    debt_score_p.add_argument("--list-stages", action="store_true", help="列出可用阶段")
    debt_score_p.set_defaults(func=_debt_mod.cmd_debt_score)
    # list/summary 委派 omo debt (修复 US-C2: invalid choice: 'list' 被 argparse 拦)
    debt_list_p = debt_sub.add_parser("list", help="列债务项 (委派 omo debt)")
    debt_list_p.add_argument("omo_debt_args", nargs=argparse.REMAINDER, help="传给 omo debt 的参数")
    debt_summary_p = debt_sub.add_parser("summary", help="债务摘要 (委派 omo debt)")
    debt_summary_p.add_argument("omo_debt_args", nargs=argparse.REMAINDER, help="传给 omo debt 的参数")
    runtime_p = sub.add_parser(
        "runtime",
        help="runtime CLI 委派 (Matrix/Scheduler/KEI 沙箱)",
    )
    runtime_p.add_argument(
        "runtime_args",
        nargs=argparse.REMAINDER,
        help="传给 runtime CLI 的参数",
    )

    sub.add_parser("demo", help="快速演示")
    sub.add_parser("gac", help="GaC 治理健康检查 (ADR-0106, 7 机制 + 115 规则 + drift)")
    daily_p = sub.add_parser("daily", help="每日研究简报")
    daily_p.add_argument("--days", type=int, default=1, help="回顾最近 N 天")
    daily_p.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    data_p = sub.add_parser("data", help="数据目录索引 / 类型注册 / TTL 清理")
    data_sub = data_p.add_subparsers(dest="data_command", parser_class=WorkspaceParser)
    data_index_p = data_sub.add_parser("index", help="刷新 data/_index 元数据")
    data_index_p.add_argument("--root", help="显式指定 workspace root")
    data_index_p.add_argument("--json", action="store_true", help="以 JSON 输出索引结果")
    data_types_p = data_sub.add_parser("types", help="查看已注册的数据类型")
    data_types_p.add_argument("--root", help="显式指定 workspace root")
    data_types_p.add_argument("--json", action="store_true", help="以 JSON 输出类型注册表")
    data_gc_p = data_sub.add_parser("gc", help="清理 data/tmp 过期文件")
    data_gc_p.add_argument("--root", help="显式指定 workspace root")
    data_gc_p.add_argument("--max-age-hours", type=float, default=24.0, help="TTL 小时数（默认 24）")
    data_gc_p.add_argument("--json", action="store_true", help="以 JSON 输出清理结果")
    contracts_p = sub.add_parser("contracts", help="契约验证")
    contracts_sub = contracts_p.add_subparsers(dest="contracts_command", parser_class=WorkspaceParser)
    validate_p = contracts_sub.add_parser("validate", help="验证 Workspace 契约")
    validate_p.add_argument("path", nargs="?", help="可选：要验证的 WorkspaceObject JSON 文件")
    contracts_sub.add_parser("list", help="列出所有已注册的 Schema")
    export_research_p = contracts_sub.add_parser("export-research", help="将研究对象导出为 WorkspaceObject JSON")
    export_research_p.add_argument("research_id", type=int, metavar="ID", help="研究对象 ID")
    export_research_p.add_argument("--output", "-o", help="写入目标 JSON 文件；不提供则打印到 stdout")
    export_p = contracts_sub.add_parser("export", help="导出契约封套")
    export_sub = export_p.add_subparsers(dest="contracts_export_type")
    export_id_p = export_sub.add_parser("identity", help="导出身份封套 (IdentityEnvelope)")
    export_id_p.add_argument("--output", "-o", help="写入目标文件")
    export_event_p = export_sub.add_parser("event", help="导出事件封套 (EventEnvelope)")
    export_event_p.add_argument("--id", type=int, help="研究对象 ID 以导出其事件")
    export_event_p.add_argument("--output", "-o", help="写入目标文件")
    sub.add_parser("dashboard", help="打开 Web Dashboard")
    help_p = sub.add_parser("help", help="查看产品地图与快速入门 (cockpit help <关键词> 模糊搜命令/工具/服务)")
    help_p.add_argument("keyword", nargs="?", help="可选搜索关键词")
    qs_p = sub.add_parser("quickstart", help="🚀 新用户快速上手向导（环境核验 + 上手指引）")
    qs_p.add_argument("--fix", action="store_true", help="自动检测并修复常见问题")
    qs_p.add_argument("--model", default="llama3.2", help="默认拉取的 LLM 模型名（默认 llama3.2）")
    init_p = sub.add_parser("init", help="🚀 初始化向导（同 quickstart）")
    init_p.add_argument("--fix", action="store_true", help="自动检测并修复常见问题")
    init_p.add_argument("--model", default="llama3.2", help="默认拉取的 LLM 模型名（默认 llama3.2）")
    profile_p = sub.add_parser("profile", help="查看/编辑身份档案 (L4 入口)")
    profile_p.add_argument("--edit", action="store_true", help="编辑身份档案")

    sub.add_parser("product-health", help="产品健康度检测")

    # ── Round 43 P1: 融合 bin/workspace-audit (6 维度全方位审计) ──
    audit_p = sub.add_parser("audit", help="🔍 6 维度全方位审计 (调 bin/workspace-audit)")
    audit_p.add_argument(
        "--dim",
        type=str,
        choices=["governance", "lint", "radar", "ssot", "gitlink", "ops", "all"],
        default="all",
        help="只跑指定维度 (默认 all)",
    )
    audit_p.add_argument("--format", choices=["markdown", "json"], default="markdown", help="输出格式")
    audit_p.add_argument("--output", type=str, default=None, help="写报告到文件")
    audit_p.add_argument("--since", type=str, default="7d", help="agora 维度时间范围 (默认 7d)")

    mcp_p = sub.add_parser("mcp", help="启动 MCP server 或列出工具")
    mcp_p.add_argument("--transport", choices=["stdio", "sse"], default="stdio", help="传输协议（默认 stdio）")
    mcp_p.add_argument(
        "--port", type=int, default=int(os.environ.get("AGORA_MCP_SSE_PORT", "7431")), help="SSE 模式监听端口"
    )
    mcp_p.add_argument("--list-tools", action="store_true", help="列出已注册的工具，不启动 server")
    mcp_p.add_argument(
        "--agora",
        action="store_true",
        help="--list-tools 时同时列出 agora (:7431) 的 BOS 服务/工具",
    )

    sub.add_parser("gongwen", help="📄 公文写作门户引导 (文种/规范/入口, 委派 @公文 域)")
    sub.add_parser("finance", help="💰 个人财务门户引导 (场景/原则/入口, 委派 @个人 域)")
    gov_p = sub.add_parser("governance", help="架构治理 (委派 arcnode-*)")
    gov_p.add_argument(
        "subcommand",
        nargs="?",
        choices=[
            "calibrate",
            "rechain",
            "evolve",
            "report",
            "drift-check",
            "validate",
            "verify",
            "evolution",
            "surfaces",
            "ingress-goal",
            "ingress-task",
            "ingress-debt",
        ],
        help="治理子命令",
    )
    gov_p.add_argument("extra_args", nargs=argparse.REMAINDER, help="传递给 arcnode-* 脚本的额外参数")

    # ── L4 Bridge commands ────────────────────────────────────
    sub.add_parser("context", help="显示系统上下文 (Phase/CARDS/约束/引导)")
    cards_p = sub.add_parser("cards", help="显示 CARDS 卡片状态")
    cards_p.add_argument("--check", action="store_true", help="检查当前操作合规性")
    cards_p.add_argument("--card-id", type=str, help="检查指定卡片")
    cards_sub = cards_p.add_subparsers(dest="cards_command")
    cards_sub.add_parser("list", help="列所有 CARDS")
    cards_get_p = cards_sub.add_parser("get", help="查 1 个 card")
    cards_get_p.add_argument("id", nargs="?", help="卡片 ID 或 path")
    cards_search_p = cards_sub.add_parser("search", help="全文搜 CARDS")
    cards_search_p.add_argument("query", nargs="?", help="关键词")
    cards_sub.add_parser("serve", help="stdio JSON-RPC serve mode")
    vault_p = sub.add_parser("vault", help="搜索 L4 Vault 知识库")
    vault_p.add_argument("keyword", nargs="?", help="搜索关键词")

    sub.add_parser("domains", help="列出 L4 所有域及其状态")
    skill_p = sub.add_parser("skill", help="运行 L4 定时技能")
    skill_p.add_argument("skill_name", help="技能名称 (如 kos-daily-ontology-sync)")

    health_p = sub.add_parser("health", help="一键系统健康检查")
    health_p.add_argument("--json", action="store_true", help="JSON 格式输出")
    health_p.add_argument(
        "--full", action="store_true", help="全栈检查 (含 Agora 服务健康 + Runtime Matrix + OMO 债务)"
    )

    brief_p = sub.add_parser("brief", help="会话简报")
    brief_p.add_argument("--force", action="store_true", help="强制重新生成")

    search_p = sub.add_parser("search", help="跨源搜索 (数据库 + BOS 知识引擎)")
    search_p.add_argument("query", help="搜索关键词")
    search_p.add_argument("--all", action="store_true", help="搜索所有源 (本地 SQLite + BOS kos/gbrain)")
    search_p.add_argument("--json", action="store_true", help="输出 P2 memory spine 统一 JSON 格式")
    search_p.add_argument("--limit", type=int, default=10, help="每源结果数 (默认10)")

    sub.add_parser("discover", help="发现可用功能和资源")

    events_p = sub.add_parser("events", help="实时查看 Agora SSE 事件流 (Phase 34 L3 Dashboard)")
    events_p.add_argument(
        "--url",
        default=f"http://127.0.0.1:{os.environ.get('AGORA_MCP_SSE_PORT', '7431')}/v1/events",
        help="Agora SSE Endpoint",
    )

    sub.add_parser("version", help="版本信息")

    # ── TUI 极客终端控制台 ───────────────────────────────────
    tui_p = sub.add_parser("tui", help="极客终端交互控制台 (Textual 全屏 TUI)")
    tui_p.add_argument("--theme", default="dark", choices=["dark", "light"], help="配色主题")

    # ── BOS 知识能力与收件箱及监控快查命令 ─────────────────────
    bcap_p = sub.add_parser("bos-capability", help="BOS capability / toolbox 外部能力")
    bcap_p.add_argument("capability_command", nargs="?", default="list", choices=["list", "invoke"], help="子命令")
    binbox_p = sub.add_parser("bos-inbox", help="BOS Inbox 多源私有知识神经网查询与操作")
    binbox_p.add_argument(
        "inbox_cmd", nargs="?", default="status", choices=["status", "search", "pending", "archive"], help="子命令"
    )
    binbox_p.add_argument("query", nargs="?", default="", help="搜索关键词")
    ewatch_p = sub.add_parser("events-watch", help="实时监听 SSE 事件流简便入口")
    ewatch_p.add_argument("--limit", type=int, default=20, help="显示最近的事件条数")
    qcheck_p = sub.add_parser("quickstart-check", help="快速检查新用户环境核验状态")
    qcheck_p.add_argument("--json", action="store_true", help="JSON 格式输出")

    # ── CLI 收敛: SSB 签名链 ────────────────────────────────
    ssb_p = sub.add_parser(
        "ssb",
        help="SSB 签名链操作 (委派 ecos-ssb)",
        epilog="子命令 (源自 ecos-ssb): publish / query / state / recover / events / stats\n示例: cockpit ssb stats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ssb_p.add_argument("extra", nargs=argparse.REMAINDER, help="传递给 ecos-ssb 的参数")

    # ── CLI 收敛: MOF 元模型 ────────────────────────────────
    mof_p = sub.add_parser(
        "mof",
        help="MOF 元模型操作 (委派 mof CLI)",
        epilog="子命令 (源自 mof 引擎): validate / audit / derive / bridge-sync\n示例: cockpit mof validate",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mof_p.add_argument("extra", nargs=argparse.REMAINDER, help="传递给 mof 的参数")

    # ── CLI 收敛: Agora BOS 网关 ─────────────────────────────
    agora_p = sub.add_parser(
        "agora",
        help="Agora BOS 网关入口 (委派 agora CLI)",
        epilog="子命令: register / unregister / list / discover / health / pipeline / repo / mcp\n示例: cockpit agora list",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    agora_p.add_argument("agora_args", nargs=argparse.REMAINDER, help="传递给 agora CLI 的参数")

    # ── CLI 收敛: model-driven 生命周期 ───────────────────────
    model_driven_p = sub.add_parser(
        "model-driven",
        help="模型驱动生命周期入口 (委派 model-driven CLI)",
        epilog="子命令: lifecycle / spec / adr / okr / tool / mcp\n示例: cockpit model-driven lifecycle dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    model_driven_p.add_argument("model_driven_args", nargs=argparse.REMAINDER, help="传递给 model-driven CLI 的参数")

    # ── 个人数字大脑 (Phase 48 MVP) ──────────────────────────
    brain_p = sub.add_parser(
        "brain",
        help="个人数字大脑 — 知识检索 + 记忆 + 智能问答",
        epilog='子命令: ask / context / remember / history\n示例: cockpit brain ask "卫健委借调总结怎么写？"',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    brain_sub = brain_p.add_subparsers(dest="brain_subcommand", parser_class=WorkspaceParser)
    brain_ask_p = brain_sub.add_parser("ask", help="向大脑提问（知识检索 + LLM 回答）")
    brain_ask_p.add_argument("question", nargs=argparse.REMAINDER, help="你的问题")
    brain_sub.add_parser("context", help="查看当前记忆摘要")
    brain_remember_p = brain_sub.add_parser("remember", help="手动存入偏好/事实")
    brain_remember_p.add_argument("fact", nargs=argparse.REMAINDER, help="要记住的内容")
    brain_history_p = brain_sub.add_parser("history", help="查看对话历史")
    brain_history_p.add_argument("--limit", "-n", type=int, default=20, help="显示条数")

    # ── CLI 收敛: gbrain 知识库 ──────────────────────────────
    gbrain_p = sub.add_parser(
        "gbrain",
        help="Postgres-native 知识库入口 (委派 gbrain CLI)",
        epilog="子命令: search / import / stats / admin\n示例: cockpit gbrain search 'attention'",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    gbrain_p.add_argument("gbrain_args", nargs=argparse.REMAINDER, help="传递给 gbrain CLI 的参数")

    # ── CLI 收敛: kairon 知识引擎 monorepo ───────────────────
    kairon_p = sub.add_parser(
        "kairon",
        help="kairon 知识引擎 monorepo 聚合入口",
        epilog="package: kos / eidos / iris / code / ontoderive / minerva / kronos / sophia\n示例: cockpit kairon kronos fetch https://example.com",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    kairon_p.add_argument("kairon_args", nargs=argparse.REMAINDER, help="package + 子命令参数")

    # ── CLI 收敛: Omni-Bus ───────────────────────────────────
    bus_p = sub.add_parser("bus", help="Omni-Bus 三平面入口")
    bus_sub = bus_p.add_subparsers(dest="bus_command", parser_class=WorkspaceParser)
    bus_sub.add_parser("status", help="Bus 状态")
    bus_sub.add_parser("topics", help="列出已注册 topic")
    bus_sub.add_parser("metrics", help="查看 bus metrics 快照")
    bus_publish_p = bus_sub.add_parser("publish", help="发布事件")
    bus_publish_p.add_argument("--topic", required=True, help="topic 名")
    bus_publish_p.add_argument("--payload", default="{}", help="JSON payload")
    bus_data_p = bus_sub.add_parser("data", help="数据平面：emit 高吞吐 fire-and-forget")
    bus_data_p.add_argument("--topic", required=True, help="topic 名")
    bus_data_p.add_argument("--payload", default="{}", help="JSON payload")
    bus_control_p = bus_sub.add_parser("control", help="控制平面：submit / ack / nack")
    bus_control_sub = bus_control_p.add_subparsers(dest="control_command", parser_class=WorkspaceParser)
    bus_control_submit_p = bus_control_sub.add_parser("submit", help="提交控制任务")
    bus_control_submit_p.add_argument("--topic", required=True, help="topic 名")
    bus_control_submit_p.add_argument("--payload", default="{}", help="JSON payload")
    bus_control_ack_p = bus_control_sub.add_parser("ack", help="确认任务完成")
    bus_control_ack_p.add_argument("--task-id", required=True, help="任务 ID")
    bus_control_nack_p = bus_control_sub.add_parser("nack", help="否定确认任务")
    bus_control_nack_p.add_argument("--task-id", required=True, help="任务 ID")
    bus_control_nack_p.add_argument("--error", default="nacked", help="失败原因")

    # ── CLI 收敛: 可观测性栈 ─────────────────────────────────
    observe_p = sub.add_parser("observe", help="可观测性栈（Langfuse）入口")
    observe_sub = observe_p.add_subparsers(dest="observe_command", parser_class=WorkspaceParser)
    observe_sub.add_parser("status", help="Docker compose 状态")
    observe_sub.add_parser("up", help="启动观测栈")
    observe_sub.add_parser("down", help="停止观测栈")
    observe_logs_p = observe_sub.add_parser("logs", help="查看日志")
    observe_logs_p.add_argument("--service", default="langfuse-server", help="服务名")
    observe_sub.add_parser("url", help="打印 Langfuse Web URL")

    # ── CLI 收敛: family-hub ─────────────────────────────────
    family_hub_p = sub.add_parser("family-hub", help="家庭数字枢纽入口")
    family_hub_sub = family_hub_p.add_subparsers(dest="family_hub_command", parser_class=WorkspaceParser)
    family_hub_sub.add_parser("status", help="API/MCP server 状态")
    family_hub_sub.add_parser("api", help="启动 API server")
    family_hub_sub.add_parser("mcp", help="启动 MCP server")

    # ── CLI 收敛: 算力网格 ───────────────────────────────────
    mesh_p = sub.add_parser("mesh", help="omlx 算力网格路由入口")
    mesh_sub = mesh_p.add_subparsers(dest="mesh_command", parser_class=WorkspaceParser)
    mesh_sub.add_parser("nodes", help="列出 KOS 中注册的算力节点")
    mesh_sub.add_parser("status", help="mesh router 健康状态")
    mesh_route_p = mesh_sub.add_parser("route", help="为模型选择最优节点")
    mesh_route_p.add_argument("--model", required=True, help="模型名")
    mesh_sub.add_parser("serve", help="启动 mesh router HTTP server")

    # ── BOS URI 网关 ─────────────────────────────────────────
    bos_p = sub.add_parser("bos", help="BOS URI 查询与管理")
    bos_sub = bos_p.add_subparsers(dest="bos_cmd")
    bos_list_p = bos_sub.add_parser(
        "list",
        help="列出 BOS URI 路由（默认 routable；--all 含 unimplemented/deprecated）",
    )
    bos_list_p.add_argument(
        "--all",
        action="store_true",
        dest="all",
        help="包含 yaml 中 non-routable（unimplemented/deprecated）条目",
    )
    bos_sub.add_parser("discover", help="扫描 workspace 发现 MCP 服务")
    bos_sub.add_parser("status", help="BOS 系统状态与蜂群情况")
    bos_resolve_p = bos_sub.add_parser("resolve", help="统一 BOS URI 路由解析与目标元数据提取")
    bos_resolve_p.add_argument("uri", help="BOS URI, e.g. bos://memory/inbox/status")
    bos_read_p = bos_sub.add_parser("read", help="通过 BOS 网关统一读取指定 URI 资源")
    bos_read_p.add_argument("uri", help="BOS URI, e.g. bos://memory/inbox/status")
    bos_read_p.add_argument("--args", default="{}", help="JSON 格式查询参数字符串")
    # 补充 bos 子命令 (实现已在 commands/bos.py, 此前 parser 未注册)
    bos_sub.add_parser("health", help="BOS 服务健康检查")
    bos_sub.add_parser("backends", help="列出 BOS 后端")
    bos_sub.add_parser("reload", help="重载 BOS 配置/M1")
    bos_sub.add_parser("register", help="注册 BOS 服务")
    bos_sub.add_parser("workflow", help="BOS workflow 相关")
    bos_mutate_p = bos_sub.add_parser("mutate", help="通过 agora 统一 BOS URI 写协议修改资源")
    bos_mutate_p.add_argument("uri", help="BOS URI, e.g. bos://memory/inbox/archive")
    bos_mutate_p.add_argument("--payload", default="{}", help="JSON 格式 payload")
    bos_mutate_p.add_argument(
        "--action",
        default="update",
        choices=["update", "create", "delete"],
        help="写操作 (默认 update)",
    )

    # ECCP external-channels inventory
    channels_p = sub.add_parser(
        "channels",
        help="🌐 External channels inventory (ECCP) — 生成/查看 external-channels.yaml",
    )
    channels_p.add_argument(
        "--quiet",
        action="store_true",
        help="只跑生成器，不打印 human summary",
    )

    # Swarm activity dashboard
    swarm_p = sub.add_parser(
        "swarm",
        help="🤖 多 agent 实时活动监控 (active runs/locks/worktree/claims/子模块 dirty/冲突)",
    )
    swarm_mode = swarm_p.add_mutually_exclusive_group()
    swarm_mode.add_argument("--tui", action="store_true", help="Rich TUI 实时刷新模式 (默认单次)")
    swarm_mode.add_argument("--json", action="store_true", help="JSON 输出")
    swarm_mode.add_argument("--watch", type=int, default=0, metavar="SEC", help="每隔 N 秒文本刷新")
    swarm_p.add_argument("--refresh", type=int, default=5, help="TUI 刷新间隔秒 (默认 5)")

    # BOS Inbox / Neural Mesh
    bos_inbox_p = bos_sub.add_parser("inbox", help="BOS Inbox 多源私有知识神经网查询与操作")
    bos_inbox_sub = bos_inbox_p.add_subparsers(dest="inbox_cmd")
    bos_inbox_sub.add_parser("status", help="统计多源神经网本地证据与嵌入状态")
    bos_inbox_search_p = bos_inbox_sub.add_parser("search", help="语义搜索多源记忆")
    bos_inbox_search_p.add_argument("query", help="搜索关键词")
    bos_inbox_pending_p = bos_inbox_sub.add_parser("pending", help="查看未决待办快照预览")
    bos_inbox_pending_p.add_argument(
        "--source", default="seeyon_oa", help="来源: seeyon_oa | netease_mailmaster | apple_mail"
    )
    bos_inbox_sub.add_parser("watch", help="监听 BOS Inbox 紧急待办与提醒快照 (Event-Driven Watcher)")
    bos_inbox_archive_p = bos_inbox_sub.add_parser("archive", help="归档已处理完毕的 Inbox 待办文件")
    bos_inbox_archive_p.add_argument("filename", help="文件名或 all")
    bos_inbox_archive_p.add_argument("--reason", default="resolved", help="归档事由")

    # BOS Capability / Toolbox

    bos_capability_p = bos_sub.add_parser("capability", help="BOS capability 域 / toolbox 外部能力")
    bos_capability_sub = bos_capability_p.add_subparsers(dest="capability_command")
    bos_capability_sub.add_parser("list", help="列出 toolbox 中的 capability 服务")
    bos_capability_invoke_p = bos_capability_sub.add_parser(
        "invoke", help="调用 capability 服务（执行 BOS YAML command）"
    )
    bos_capability_invoke_p.add_argument("capability_service", help="URI 或短名，如 media-crawler / last30days-skill")
    bos_capability_invoke_p.add_argument(
        "capability_args",
        nargs=argparse.REMAINDER,
        help="透传给目标 command 的额外参数（非 shell 命令时）",
    )

    # OPC P5-F4: 统一 scenario 入口 — parser 定义抽到 commands/scenario.py (god-module 拆分)
    scenario_p = sub.add_parser(
        "scenario",
        help="P5 统一 scenario 入口 (radar/assistant/health/inbox/intake/task/approval/connector/review)",
    )
    from cockpit.commands.scenario import build_scenario_parser

    build_scenario_parser(scenario_p, WorkspaceParser)

    # Gap #7: MetaOS 工作流编排入口
    wf_p = sub.add_parser(
        "workflow",
        help="🧠 工作流编排（MetaOS 动态规划 / ecos L0 M1 引擎）",
        epilog='子命令: plan / run / history / approve (MetaOS) | ecos (L0 M1 引擎)\n示例:\n  cockpit workflow ecos list\n  cockpit workflow plan "目标"\n  cockpit workflow history',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    wf_p.add_argument("workflow_args", nargs="*", help="workflow 子命令和参数")

    agent_wf_p = sub.add_parser(
        "agent-workflow",
        help="🤖 Agent 可执行治理流程 (委派 root bin/agent-workflow.py)",
        epilog=(
            "示例:\n"
            "  cockpit agent-workflow list\n"
            "  cockpit agent-workflow lint\n"
            "  cockpit agent-workflow doctor\n"
            "  cockpit agent-workflow show project-code-change --project omo"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    agent_wf_p.add_argument(
        "agent_workflow_args",
        nargs=argparse.REMAINDER,
        help="Arguments passed to bin/agent-workflow.py",
    )
    agent_p = sub.add_parser(
        "agent",
        help="🤖 Agent 治理控制入口 (bootstrap / status / start / claim / verify / closeout)",
        epilog=(
            "示例:\n"
            "  cockpit agent\n"
            "  cockpit agent status --json\n"
            '  cockpit agent start project-doc-change --profile governance-agent --objective "docs"\n'
            "  cockpit agent claim <run-id> --path AGENTS.md\n"
            "  cockpit agent verify <run-id> --from-diff --execute\n"
            "  cockpit agent closeout <run-id>"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    agent_p.add_argument(
        "agent_args",
        nargs=argparse.REMAINDER,
        help="Arguments passed to bin/agent-workflow.py",
    )

    # ── Agent onboarding ──────────────────────────────────
    onboard_p = sub.add_parser(
        "agent-onboard",
        help="🤖 Agent 入职引导 checklist (profile + MCP + BOS + skills)",
        epilog=(
            "示例:\n"
            "  cockpit agent-onboard\n"
            "  cockpit agent-onboard --profile governance-agent\n"
            "  cockpit agent-onboard --json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    onboard_p.add_argument("--profile", help="Check if a specific profile is registered")
    onboard_p.add_argument("--json", action="store_true", help="Output JSON")

    # ── CLI 收敛: agent-runtime 并入 cockpit ─────────────────
    agent_runtime_p = sub.add_parser(
        "agent-runtime",
        help="🤖 Agent Runtime 任务执行 / HTTP server (替代独立 agent-runtime 命令)",
        epilog=(
            "示例:\n"
            '  cockpit agent-runtime --prompt "Hello"\n'
            "  cockpit agent-runtime --task my-task\n"
            "  cockpit agent-runtime --server --port 8080\n"
            '  cockpit agent-runtime --model gpt-4 --tools read write --prompt "Hi"'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    agent_runtime_p.add_argument("--prompt", "-p", help="Task prompt")
    agent_runtime_p.add_argument("--task", "-t", help="Task name (load from task_definitions/<name>.json)")
    agent_runtime_p.add_argument("--model", help="Override model")
    agent_runtime_p.add_argument("--tools", nargs="*", help="Enabled tool names")
    agent_runtime_p.add_argument("--server", action="store_true", help="Start HTTP server")
    agent_runtime_p.add_argument("--port", type=int, help="HTTP server port")

    # Gap #8: C2G 双擎编排流入口 (Phase 40)
    iterate_p = sub.add_parser("iterate", help="♻️ C2G 双擎迭代流 (MetaOS 发散 -> Model-Driven 桥接 -> OMO 门控执行)")
    iterate_p.add_argument("topic", nargs="?", default="未命名探索主题", help="要发起探索的主题")
    iterate_p.add_argument("--mock", action="store_true", help="是否模拟生成带 TODO 的测试数据以触发门控")

    compass_p = sub.add_parser(
        "compass",
        help="🧭 C2G 战略罗盘 (V2P -> C2G -> AGC 统一管理)",
        epilog=(
            "子命令 (源自 c2g 引擎):\n"
            '  brainstorm "主题"  发散想法生成 Pitch\n'
            "  draft               交互式起草 Pitch\n"
            "  bet <pitch.md>      Pitch → 受治理任务\n"
            "  radar               战略对齐审计\n"
            "  gc                  清理滞留 Pitch\n"
            "详细: c2g compass --help"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    compass_p.add_argument("compass_args", nargs=argparse.REMAINDER, help="Arguments passed to c2g compass engine")

    # Wave2 dashboard / proposals (ADR-0190) — JSON contract for agents + UI
    wave2_p = sub.add_parser(
        "wave2",
        help="📈 Wave2 预测治理面板 (dashboard/proposals/predictive JSON)",
        epilog=(
            "子命令:\n"
            "  dashboard   cards+heatmap+proposals 统一 JSON (c2g.wave2.dashboard.v1)\n"
            "  proposals   C2G→OMO 治理提案\n"
            "  predictive  预测 + 热力 Markdown\n"
            "示例: cockpit wave2 dashboard\n"
            "      cockpit wave2 proposals -- --show-apply-plan"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    wave2_p.add_argument(
        "wave2_command",
        nargs="?",
        default="dashboard",
        help="dashboard|proposals|predictive (default: dashboard)",
    )
    wave2_p.add_argument("--pretty", action="store_true", help="Indent dashboard JSON")
    wave2_p.add_argument(
        "wave2_args",
        nargs=argparse.REMAINDER,
        help="Extra args passed through (after --)",
    )

    bdsk_p = sub.add_parser("bdsk", help="🧠 B.D.S.K. 虚拟董事会 (4角对抗辩论与架构决策)")
    bdsk_p.add_argument("bdsk_subcmd", nargs="?", default="debate", help="debate (default: debate)")
    bdsk_p.add_argument("topic", nargs="?", default="架构决策与技术选型", help="辩论主题或决策方案")

    sub.add_parser("journey", help="🗺️ Journey State Graph 状态表达校验器")
    sub.add_parser("panorama", help="🌐 7 维全景终极可观测仪表盘 (执行过程/服务/内容/知识/数据/异常/债务资产)")

    proj_p = sub.add_parser("project", help="🔍 17 项目全景 4D 体检与诊断")
    proj_p.add_argument("project_subcmd", nargs="?", default="inspect", help="inspect|list (default: inspect)")
    proj_p.add_argument("project_name", nargs="?", default="", help="指定项目名称")
    proj_p.add_argument("--json", action="store_true", help="JSON 输出")

    sub.add_parser("monitor", help="📊 实时终端大盘 (C2G Pipeline 监控仪, 实时刷新 Ctrl+C 退出)")

    code_p = sub.add_parser("code", help="代码库分析与审查 (基于 codeanalyze)")
    code_sub = code_p.add_subparsers(dest="code_command", parser_class=WorkspaceParser)

    # 基础分析命令
    code_sub.add_parser("analyze", help="运行全部分析工具")
    code_sub.add_parser("graph", help="运行语义图谱分析")
    code_sub.add_parser("pack", help="将代码库打包为 LLM 友好格式")
    code_sub.add_parser("dashboard", help="启动交互式知识图谱仪表盘")

    # 高级工作流命令
    code_workflow_p = code_sub.add_parser("workflow", help="高级分析工作流")
    code_workflow_sub = code_workflow_p.add_subparsers(dest="workflow_command")

    code_impact_p = code_workflow_sub.add_parser("impact", help="分析符号的变更影响面")
    code_impact_p.add_argument("--symbol", help="目标符号名称")
    code_workflow_sub.add_parser("onboarding", help="为 AI 构建项目全貌上下文")

    # ── CLI 收敛: 算力与 LLM 网关 (替代 deprecated aetherforge CLI) ──
    compute_p = sub.add_parser(
        "compute",
        help="算力与 LLM 网关操作 (委派 aetherforge)",
        epilog="子命令: gateway generate / gateway list / mesh list / mesh status / mesh cost / swarm run\n示例: cockpit compute gateway generate 'hello'",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    compute_p.add_argument("compute_command", nargs="?", help="gateway/mesh/swarm")
    compute_p.add_argument("extra", nargs=argparse.REMAINDER, help="传递给 aetherforge 的参数")

    # ── Phase 49+: 能力全景覆盖 — 新增命令组 ──────────────────
    # knowledge — KOS 知识检索治理 (5193 篇索引)
    knowledge_p = sub.add_parser("knowledge", help="📚 KOS 知识检索 (search/status/stats)")
    knowledge_sub = knowledge_p.add_subparsers(dest="knowledge_command")
    knowledge_search_p = knowledge_sub.add_parser("search", help="语义搜索")
    knowledge_search_p.add_argument("query", nargs="?", help="搜索词")
    knowledge_search_p.add_argument("--limit", type=int, default=5, help="结果数 (默认 5)")
    knowledge_sub.add_parser("status", help="KOS 服务健康")
    knowledge_sub.add_parser("stats", help="索引统计")

    # memory — Memory OS 统一控制面 (ADR-0372 phase10) → bos://memory/mos/*
    memory_p = sub.add_parser(
        "memory",
        help="🧠 Memory OS (status/recall/write/forget/consolidate/knowledge-ref)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "BOS: bos://memory/mos/{write,recall,status,forget,consolidate,knowledge-ref}\n"
            "Examples:\n"
            "  cockpit memory status --json\n"
            "  cockpit memory recall 'Alice' --intent temporal_fact --as-of 2021-06-01T00:00:00Z\n"
            "  cockpit memory write --type semantic --content '…' --subject A --predicate works_at --object B\n"
            "  source bin/memory-os-env.sh && bash bin/memory-os-neo4j-up.sh\n"
            "  # live (optional): MOS_LIVE_KOS=1 MOS_LIVE_GBRAIN=1\n"
            "Docs: docs/architecture/memory-os.md · .omo/standards/memory-os-ops.md"
        ),
    )
    memory_sub = memory_p.add_subparsers(dest="memory_command")
    mem_status = memory_sub.add_parser(
        "status",
        help="控制面健康 / neo4j / rbac / consolidate / adapters",
    )
    mem_status.add_argument("--json", action="store_true")
    mem_status.add_argument("--role", default=None)
    mem_status.add_argument("--agent-profile", dest="agent_profile", default=None)
    mem_recall = memory_sub.add_parser("recall", help="意图路由召回（neo4j/temporal 支持 --as-of）")
    mem_recall.add_argument("query", nargs="?", help="查询")
    mem_recall.add_argument("--intent", default=None, help="file_note|temporal_fact|entity_relation|…")
    mem_recall.add_argument("--limit", type=int, default=10)
    mem_recall.add_argument(
        "--as-of",
        dest="as_of",
        default=None,
        help="ISO-8601 bi-temporal as-of for neo4j/temporal (omit = current state)",
    )
    mem_recall.add_argument("--principal-id", dest="principal_id", default=None)
    mem_recall.add_argument("--agent-profile", dest="agent_profile", default=None)
    mem_recall.add_argument("--scene-id", dest="scene_id", default=None)
    mem_recall.add_argument("--role", default=None)
    mem_recall.add_argument("--json", action="store_true")
    mem_write = memory_sub.add_parser("write", help="双轨写入 (+ Neo4j FACT 若配置)")
    mem_write.add_argument("--type", dest="mem_type", required=True, help="semantic|episodic|…")
    mem_write.add_argument("--content", default=None)
    mem_write.add_argument("--content-ref", dest="content_ref", default=None)
    mem_write.add_argument("--confidence", type=float, default=0.8)
    mem_write.add_argument("--principal-id", dest="principal_id", default=None)
    mem_write.add_argument("--agent-profile", dest="agent_profile", default=None)
    mem_write.add_argument("--scene-id", dest="scene_id", default=None)
    mem_write.add_argument("--subject", default=None)
    mem_write.add_argument("--predicate", default=None)
    mem_write.add_argument("--object", default=None)
    mem_write.add_argument("--valid-from", dest="valid_from", default=None)
    mem_write.add_argument("--valid-to", dest="valid_to", default=None)
    mem_write.add_argument("--role", default=None)
    mem_write.add_argument("--json", action="store_true")
    mem_forget = memory_sub.add_parser("forget", help="遗忘传播")
    mem_forget.add_argument("memory_id", nargs="?", help="memory id")
    mem_forget.add_argument("--reason", default=None)
    mem_forget.add_argument("--role", default=None)
    mem_forget.add_argument("--agent-profile", dest="agent_profile", default=None)
    mem_forget.add_argument("--json", action="store_true")
    mem_cons = memory_sub.add_parser("consolidate", help="sleep-time 巩固 (默认 dry-run)")
    mem_cons.add_argument("--live", action="store_true", help="非 dry-run")
    mem_cons.add_argument("--dry-run", dest="dry_run", action="store_true", default=True)
    mem_cons.add_argument("--phases", default=None, help="comma-separated phases")
    mem_cons.add_argument("--role", default=None)
    mem_cons.add_argument("--agent-profile", dest="agent_profile", default=None)
    mem_cons.add_argument("--json", action="store_true")
    for kref_name in ("knowledge-ref", "kref"):
        mem_kref = memory_sub.add_parser(kref_name, help="ADR-0315 引用元数据 (无正文)")
        mem_kref.add_argument("query", nargs="?", help="查询")
        mem_kref.add_argument("--intent", default=None)
        mem_kref.add_argument("--limit", type=int, default=5)
        mem_kref.add_argument("--principal-id", dest="principal_id", default=None)
        mem_kref.add_argument("--role", default=None)
        mem_kref.add_argument("--json", action="store_true")

    # kems — KEMS 域治理 (28 域)
    kems_p = sub.add_parser("kems", help="🧬 KEMS 域治理 (domains/status/scan)")
    kems_sub = kems_p.add_subparsers(dest="kems_command")
    kems_sub.add_parser("domains", help="列出 28 域状态")
    kems_sub.add_parser("status", help="控制面状态")
    kems_sub.add_parser("scan", help="平面扫描")

    # c2g — C2G 战略罗盘全局状态
    c2g_p = sub.add_parser("c2g", help="🎯 C2G 战略罗盘 (status/pipeline)")
    c2g_sub = c2g_p.add_subparsers(dest="c2g_command")
    c2g_sub.add_parser("status", help="全局状态 (radar)")
    c2g_sub.add_parser("pipeline", help="pipeline 概览")

    # workflow mesh 子命令通过 dispatch 处理 (避免与 workflow_args nargs=* 冲突)

    args = parser.parse_args()

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
                "  [cyan]cockpit model-driven[/]      — 生命周期 / OKR\n"
                "  [cyan]cockpit bus[/]               — Omni-Bus 三平面\n"
                "  [cyan]cockpit observe[/]           — Langfuse 可观测性\n"
                "  [cyan]cockpit family-hub[/]        — 家庭数字枢纽\n"
                "  [cyan]cockpit mesh[/]              — 算力网格路由\n"
                "  [cyan]cockpit bos capability[/]    — Toolbox 外部能力\n\n"
                "[bold]工具[/]\n"
                "  [cyan]cockpit search --all KEY[/]  — 跨源搜索 (本地+BOS)\n"
                "  [cyan]cockpit discover[/]           — 发现可用功能\n"
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

    def dispatch_research(a):
        if getattr(a, "batch", False) and getattr(a, "topic", []):
            if len(a.topic) >= 2:
                return _cmd_research_batch(a)
        if getattr(a, "search", False):
            return cmd_research_search(a)
        if getattr(a, "compare", False):
            return cmd_research_compare(a)
        if getattr(a, "merge", False):
            return cmd_research_merge(a)
        if getattr(a, "digest", False):
            return cmd_research_digest(a)
        if getattr(a, "audit", False):
            return cmd_research_audit(a)
        if getattr(a, "quarantine", False):
            return cmd_research_quarantine(a)
        if getattr(a, "restore", False):
            return cmd_research_restore(a)
        if getattr(a, "heatmap", False):
            return cmd_research_heatmap(a)
        if getattr(a, "follow_up", False):
            return cmd_research_follow_up(a)
        if getattr(a, "health", False):
            return cmd_research_health(a)
        if getattr(a, "backup", None) is not None:
            a.output = a.backup or None
            return cmd_research_backup(a)
        if getattr(a, "backup_restore", False):
            return cmd_research_backup_restore(a)
        if getattr(a, "agent", False):
            return cmd_research_agent(a)
        if getattr(a, "list", False):
            return cmd_research_list(a)
        if getattr(a, "dossier", False):
            return cmd_research_dossier(a)
        if getattr(a, "timeline", False):
            return cmd_research_timeline(a)
        if getattr(a, "tag", False):
            return cmd_research_tag(a)
        if getattr(a, "rename", False):
            return cmd_research_rename(a)
        if getattr(a, "archive", False) or getattr(a, "all_active", False):
            return cmd_research_archive(a)
        if getattr(a, "unarchive", False):
            return cmd_research_unarchive(a)
        if getattr(a, "publish", False):
            return cmd_research_publish(a)
        if getattr(a, "export", False):
            return cmd_research_export(a)
        if getattr(a, "open", False):
            return cmd_research_open(a)
        if getattr(a, "ask", False):
            return cmd_research_ask(a)
        return cmd_research(a)

    def dispatch_code(a):
        if getattr(a, "code_command", "") == "workflow":
            from cockpit.commands.code import cmd_code_workflow

            return cmd_code_workflow(a)
        elif getattr(a, "code_command", ""):
            from cockpit.commands.code import cmd_code_base

            return cmd_code_base(a)
        code_p.print_help()
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
        import os
        import subprocess

        c2g_project = str((_SCRIPT_DIR.parent.parent.parent.parent / "c2g").resolve())
        cmd = ["uv", "run", "--project", c2g_project, "c2g"] + getattr(a, "compass_args", [])
        # 清 VIRTUAL_ENV 避免 uv venv 冲突 (cockpit → c2g subprocess 继承父环境)
        env = {k: v for k, v in os.environ.items() if not k.startswith("VIRTUAL_ENV") and k != "PYTHONHOME"}
        return subprocess.call(cmd, env=env)

    def dispatch_bdsk(a):
        from cockpit.commands.bdsk_engine import DynamicBDSKAdjudicator

        topic = getattr(a, "topic", "架构决策与技术选型")
        res = DynamicBDSKAdjudicator.adjudicate(topic)

        source_tag = "⚡️ AetherForge + omlxc (Local LLM Active)" if res.get("engine_source") == "aetherforge_local_llm" else "ℹ️ [AetherForge] 网关未在线 ➔ 平滑降级至领域推理引擎"

        print("=========================================================================")
        print(f" 🧠 B.D.S.K. 虚拟董事会 (4 角动态对抗模式) ➔ {source_tag}")
        print(f" 🔬 领域分类: {res['domain_label']} | 🎯 议题: {res['topic']}")
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
        print(f"💡 4 角共识裁决结论: {res['conclusion']}")
        print("=========================================================================")
        return 0

    def dispatch_journey(a):
        import subprocess
        ws_root = (_SCRIPT_DIR.parent.parent.parent.parent.parent).resolve()
        runner = str(ws_root / "bin" / "ssot" / "journey-runner.py")
        return subprocess.call(["python3", runner, "--help"])

    def dispatch_panorama(a):
        import os
        import subprocess

        omo_project = str((_SCRIPT_DIR.parent.parent.parent.parent / "omo").resolve())
        cmd = ["uv", "run", "--project", omo_project, "python", "-m", "omo.cli", "panorama"]
        if getattr(a, "json", False):
            cmd.append("--json")
        env = {k: v for k, v in os.environ.items() if not k.startswith("VIRTUAL_ENV") and k != "PYTHONHOME"}
        return subprocess.call(cmd, env=env)

    def dispatch_project(a):
        import os
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
            "[yellow]试试: [cyan]cockpit data index[/] 或 [cyan]cockpit data types[/] 或 [cyan]cockpit data gc[/][/]"
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
        print(
            "用法: cockpit contracts {validate|list|export-research <ID>|export identity|export event}\n"
            "  validate          验证 Workspace 契约\n"
            "  list              列出所有已注册 Schema\n"
            "  export-research   将研究对象导出为 WorkspaceObject JSON\n"
            "  export identity/event  导出契约封套"
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
        "brief": _cmd_brief,
        "discover": _cmd_discover,
        "profile": cmd_profile,
        "cards": dispatch_cards,
        "audit": cmd_audit,
        "demo": cmd_demo,
        "search": _cmd_search,
        "dashboard": cmd_dashboard,
        "vault": _c_vault,
        "bos": dispatch_bos,
        "code": dispatch_code,
        "research": dispatch_research,
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
        "compute": cmd_compute,
        "gac": cmd_gac,
        "omo": lambda a: __import__("cockpit.commands.omo", fromlist=["cmd_omo"]).cmd_omo(a),
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
        "bos-inbox": lambda a: __import__("cockpit.commands.bos_inbox", fromlist=["cmd_bos_inbox"]).cmd_bos_inbox(a),
        "events-watch": lambda a: _c_events(
            __import__("argparse").Namespace(watch=True, limit=getattr(a, "limit", 20), topic=None)
        ),
        "quickstart-check": lambda a: __import__(
            "cockpit.commands.quickstart", fromlist=["cmd_quickstart"]
        ).cmd_quickstart(__import__("argparse").Namespace(check=True, json=getattr(a, "json", False))),
    }

    global_output = getattr(args, "global_output", "text")
    if global_output == "tui":
        return __import__("cockpit.tui", fromlist=["launch"]).launch(args)

    handler = handlers.get(args.command)
    if handler:
        if (
            global_output == "text"
            and args.command not in ("tui", "completion", "help", "demo")
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
