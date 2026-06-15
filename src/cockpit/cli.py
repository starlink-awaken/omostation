#!/usr/bin/env python3
"""cockpit — eCOS v5 L3 入口层。"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time as _time_mod
from argparse import Namespace
from datetime import datetime
from pathlib import Path
from urllib import request as urlrequest  # noqa: F401

from rich import box
from rich.console import Console
from rich.panel import Panel

# ── Shared singletons (defined here so tests can monkeypatch cli.xxx) ──
console = Console()
err = Console(stderr=True)
from .storage import get_data_access  # noqa: F401

time = _time_mod

# ── Command modules ──
# ── Compatibility re-exports (tests monkeypatch these via cli.xxx) ──
from .commands.base import (
    _SCRIPT_DIR,
    _find_cli,  # noqa: F401
    _panel,
)
from .commands.contracts import (
    cmd_contracts_export_event,
    cmd_contracts_export_identity,
    cmd_contracts_export_research,
    cmd_contracts_list,
    cmd_contracts_validate,
)
from .commands.data import cmd_data_gc, cmd_data_index, cmd_data_types
from .commands.governance import cmd_governance
from .commands.importer import cmd_import
from .commands.mcp import cmd_mcp
from .commands.profile import cmd_profile
from .commands.quickstart import cmd_quickstart
from .commands.research import (
    _notify_research_complete,  # noqa: F401
    _research_progress,  # noqa: F401
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
from .commands.status import (
    _render_workbench,  # noqa: F401
    cmd_daily,
    cmd_dashboard,
    cmd_demo,
    cmd_help,
    cmd_status,
)


def main() -> int:
    try:
        from kairon_observability.tracing import setup_tracing
        setup_tracing("cockpit-cli")
    except ImportError:
        pass  # Skip if observability package isn't installed

    class WorkspaceParser(argparse.ArgumentParser):
        def error(self, message):
            parser_console = Console()
            parser_console.print(f"\n[red]Error: {message}[/]")
            parser_console.print("[yellow]试试以下命令:[/]")
            parser_console.print('  [cyan]cockpit research "你的主题"[/]')
            parser_console.print("  [cyan]cockpit research --list[/]")
            parser_console.print("  [cyan]cockpit status[/]")
            parser_console.print("  [cyan]cockpit demo[/]")
            parser_console.print()
            sys.exit(2)

    parser = WorkspaceParser(
        prog="cockpit",
        description="Workspace — 产品级统一入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
旅程:
  research    深度研究 & 知识管理
  import      导入外部内容
  status      系统健康 & 研究状态
  demo        快速演示闭环
  daily       每日研究简报
  display     查看所有 export 内容
  dashboard   打开 Web Dashboard

示例:
  cockpit research "attention mechanism"
  cockpit research --list
  cockpit research --search "keyword"
  cockpit research --open 1
  cockpit research --ask 1 "追问问题"
  cockpit research --publish 1 --style brief
  cockpit research --dossier 1
  cockpit research --timeline 1
  cockpit research --tag 1 --labels llm agents
  cockpit research --rename 1 --new-title better title
  cockpit research --archive 1
  cockpit research --unarchive 1
  cockpit research --compare 1 2
  cockpit research --merge 1 2
  cockpit research --digest 1 2
  cockpit research --audit
  cockpit research --quarantine 4 5
  cockpit research --restore 4 5
  cockpit import ~/Desktop/note.md
  cockpit status
  cockpit status --watch --interval 2
  cockpit contracts validate
  cockpit contracts export-research 1
  cockpit demo
  cockpit daily
  cockpit dashboard
        """,
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
    sub.add_parser("demo", help="快速演示")
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
    sub.add_parser("help", help="查看产品地图与快速入门")
    qs_p = sub.add_parser("quickstart", help="🚀 新用户快速上手向导（环境核验 + 上手指引）")
    qs_p.add_argument("--fix", action="store_true", help="自动检测并修复常见问题")
    qs_p.add_argument("--model", default="llama3.2", help="默认拉取的 LLM 模型名（默认 llama3.2）")
    init_p = sub.add_parser("init", help="🚀 初始化向导（同 quickstart）")
    init_p.add_argument("--fix", action="store_true", help="自动检测并修复常见问题")
    init_p.add_argument("--model", default="llama3.2", help="默认拉取的 LLM 模型名（默认 llama3.2）")
    profile_p = sub.add_parser("profile", help="查看/编辑身份档案 (L4 入口)")
    profile_p.add_argument("--edit", action="store_true", help="编辑身份档案")

    sub.add_parser("product-health", help="产品健康度检测")

    mcp_p = sub.add_parser("mcp", help="启动 MCP server 或列出工具")
    mcp_p.add_argument("--transport", choices=["stdio", "sse"], default="stdio", help="传输协议（默认 stdio）")
    mcp_p.add_argument("--port", type=int, default=7431, help="SSE 模式监听端口（默认 7431）")
    mcp_p.add_argument("--list-tools", action="store_true", help="列出已注册的工具，不启动 server")

    gov_p = sub.add_parser("governance", help="架构治理 (委派 arcnode-*)")
    gov_p.add_argument(
        "subcommand",
        nargs="?",
        choices=["calibrate", "rechain", "evolve", "report", "drift-check", "validate"],
        help="治理子命令",
    )
    gov_p.add_argument("extra_args", nargs=argparse.REMAINDER, help="传递给 arcnode-* 脚本的额外参数")

    # ── L4 Bridge commands ────────────────────────────────────
    sub.add_parser("context", help="显示系统上下文 (Phase/CARDS/约束/引导)")
    cards_p = sub.add_parser("cards", help="显示 CARDS 卡片状态")
    cards_p.add_argument("--check", action="store_true", help="检查当前操作合规性")
    cards_p.add_argument("--card-id", type=str, help="检查指定卡片")
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

    brief_p =     sub.add_parser("brief", help="会话简报")
    brief_p.add_argument("--force", action="store_true", help="强制重新生成")

    search_p = sub.add_parser("search", help="跨源搜索 (数据库 + BOS 知识引擎)")
    search_p.add_argument("query", help="搜索关键词")
    search_p.add_argument("--all", action="store_true", help="搜索所有源 (本地 SQLite + BOS kos/gbrain)")
    search_p.add_argument("--json", action="store_true", help="输出 P2 memory spine 统一 JSON 格式")
    search_p.add_argument("--limit", type=int, default=10, help="每源结果数 (默认10)")

    sub.add_parser("discover", help="发现可用功能和资源")

    events_p = sub.add_parser("events", help="实时查看 Agora SSE 事件流 (Phase 34 L3 Dashboard)")
    events_p.add_argument("--url", default="http://127.0.0.1:8080/v1/events", help="Agora SSE Endpoint")

    sub.add_parser("version", help="版本信息")

    # ── CLI 收敛: SSB 签名链 ────────────────────────────────
    ssb_p = sub.add_parser("ssb", help="SSB 签名链操作 (委派 ecos-ssb)")
    ssb_p.add_argument("extra", nargs=argparse.REMAINDER, help="传递给 ecos-ssb 的参数")

    # ── CLI 收敛: MOF 元模型 ────────────────────────────────
    mof_p = sub.add_parser("mof", help="MOF 元模型操作 (委派 mof CLI)")
    mof_p.add_argument("extra", nargs=argparse.REMAINDER, help="传递给 mof 的参数")

    # OPC P5-F4: 统一 scenario 入口 — 用户无需理解仓边界
    scenario_p = sub.add_parser(
        "scenario",
        help="P5 统一 scenario 入口 (radar/assistant/health)",
    )
    scenario_sub = scenario_p.add_subparsers(
        dest="scenario_sub", parser_class=WorkspaceParser
    )
    scenario_radar = scenario_sub.add_parser(
        "radar", help="P5-F1 technical-radar: 扫描研究活动, 产出 ≥3 upgrade candidates"
    )
    scenario_radar.add_argument(
        "--limit", type=int, default=10, help="最多产出多少 candidates (默认 10, 红线 ≥3)"
    )
    scenario_assistant = scenario_sub.add_parser(
        "assistant", help="P5-F2 work-assistant: 1 真实工作 query → 结构化草稿"
    )
    scenario_assistant.add_argument(
        "--query", type=str, default="OPC P5 progress", help="真实工作 query"
    )
    scenario_health = scenario_sub.add_parser(
        "health", help="P5-F3 family-health: 1 真实家庭健康 query → 3 级 next-action (privacy=confidential)"
    )
    scenario_health.add_argument(
        "--query", type=str, default="日常家庭健康问询", help="真实家庭健康 query"
    )

    # Gap #7: MetaOS 工作流编排入口
    wf_p = sub.add_parser("workflow", help="🧠 MetaOS 工作流编排（动态规划 / 执行 / 历史）")
    wf_p.add_argument("workflow_args", nargs="*", help="workflow 子命令和参数")

    # Gap #8: C2G 双擎编排流入口 (Phase 40)
    iterate_p = sub.add_parser("iterate", help="♻️ C2G 双擎迭代流 (MetaOS 发散 -> Model-Driven 桥接 -> OMO 门控执行)")
    iterate_p.add_argument("topic", nargs="?", default="未命名探索主题", help="要发起探索的主题")
    iterate_p.add_argument("--mock", action="store_true", help="是否模拟生成带 TODO 的测试数据以触发门控")

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

    args = parser.parse_args()

    if args.command == "code":
        if args.code_command == "workflow":
            from cockpit.commands.code import cmd_code_workflow

            return cmd_code_workflow(args)
        elif args.code_command:
            from cockpit.commands.code import cmd_code_base

            return cmd_code_base(args)
        else:
            code_p.print_help()
            return 1

    if args.command == "research":
        if args.search:
            return cmd_research_search(args)
        if args.compare:
            return cmd_research_compare(args)
        if args.merge:
            return cmd_research_merge(args)
        if args.digest:
            return cmd_research_digest(args)
        if args.audit:
            return cmd_research_audit(args)
        if args.quarantine:
            return cmd_research_quarantine(args)
        if args.restore:
            return cmd_research_restore(args)
        if args.heatmap:
            return cmd_research_heatmap(args)
        if args.follow_up:
            return cmd_research_follow_up(args)
        if args.health:
            return cmd_research_health(args)
        if args.backup is not None:
            args.output = args.backup or None
            return cmd_research_backup(args)
        if args.backup_restore:
            return cmd_research_backup_restore(args)
        if args.agent:
            return cmd_research_agent(args)
        if args.list:
            return cmd_research_list(args)
        if args.dossier:
            return cmd_research_dossier(args)
        if args.timeline:
            return cmd_research_timeline(args)
        if args.tag:
            return cmd_research_tag(args)
        if args.rename:
            return cmd_research_rename(args)
        if args.archive or args.all_active:
            return cmd_research_archive(args)
        if args.unarchive:
            return cmd_research_unarchive(args)
        if args.publish:
            return cmd_research_publish(args)
        if args.export:
            if not args.open:
                console.print("[red]Error: specify --open N to export a research[/]")
                return 1
            args.research_id = args.open
            return cmd_research_export(args)
        if args.open:
            args.research_id = args.open
            return cmd_research_open(args)
        if args.ask:
            args.research_id = args.ask
            args.question = args.topic
            return cmd_research_ask(args)
        if args.batch and args.topic:
            return _cmd_research_batch(args)
        return cmd_research(args)

    if args.command == "import":
        return cmd_import(args)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "demo":
        return cmd_demo(args)
    if args.command == "daily":
        return cmd_daily(args)
    if args.command == "data":
        if args.data_command == "index":
            return cmd_data_index(args)
        if args.data_command == "types":
            return cmd_data_types(args)
        if args.data_command == "gc":
            return cmd_data_gc(args)
        console.print(
            "[yellow]试试: [cyan]cockpit data index[/] 或 [cyan]cockpit data types[/] 或 [cyan]cockpit data gc[/][/]"
        )
        return 1
    if args.command == "contracts":
        if args.contracts_command == "validate":
            return cmd_contracts_validate(args)
        if args.contracts_command == "list":
            return cmd_contracts_list(args)
        if args.contracts_command == "export-research":
            return cmd_contracts_export_research(args)
        if args.contracts_command == "export":
            if args.contracts_export_type == "identity":
                return cmd_contracts_export_identity(args)
            elif args.contracts_export_type == "event":
                return cmd_contracts_export_event(args)
            console.print(
                "[yellow]试试: [cyan]cockpit contracts export identity[/] 或 [cyan]cockpit contracts export event --id 1[/][/]"
            )
            return 1
        console.print(
            "[yellow]试试: [cyan]cockpit contracts validate[/] 或 [cyan]cockpit contracts list[/] 或 [cyan]cockpit contracts export-research 1[/] 或 [cyan]cockpit contracts export identity[/][/]"
        )
        return 1
    if args.command == "dashboard":
        return cmd_dashboard(args)
    if args.command == "help":
        return cmd_help(args)
    if args.command in ("quickstart", "init"):
        return cmd_quickstart(args)
    if args.command == "profile":
        return cmd_profile(args)
    if args.command == "product-health":
        import subprocess as _sp

        result = _sp.run([sys.executable, str(_SCRIPT_DIR / "product-health")])
        returncode = getattr(result, "returncode", 0)
        return returncode if isinstance(returncode, int) else 0
    if args.command == "governance":
        return cmd_governance(args)
    if args.command == "mcp":
        return cmd_mcp(args)
    if args.command == "context":
        from .commands.l4bridge import cmd_context

        return cmd_context(args)
    if args.command == "cards":
        from .commands.l4bridge import cmd_cards

        return cmd_cards(args)
    if args.command == "vault":
        from .commands.l4bridge import cmd_vault

        return cmd_vault(args)
    if args.command == "domains":
        from .commands.l4bridge import cmd_domains

        return cmd_domains(args)
    if args.command == "skill":
        from .commands.l4bridge import cmd_skill

        return cmd_skill(args)
    if args.command == "health":
        return _cmd_health(args)
    if args.command == "search":
        return _cmd_search(args)
    if args.command == "discover":
        return _cmd_discover(args)
    if args.command == "brief":
        return _cmd_brief(args)
    if args.command == "events":
        from .commands.events import run_events_dashboard

        run_events_dashboard(args.url)
        return 0
    if args.command == "version":
        from cockpit import __version__

        console.print(f"[bold cyan]cockpit[/] v[bold]{__version__}[/]")
        console.print("[dim]L3 统一入口 · 5+3+1 架构[/]")
        return 0

    if args.command == "workflow":
        from cockpit.commands.workflow import handle_workflow

        return handle_workflow(args.workflow_args)

    if args.command == "iterate":
        from cockpit.commands.iterate import cmd_iterate

        return cmd_iterate(args)

    if args.command == "ssb":
        from cockpit.commands.ssb import cmd_ssb

        return cmd_ssb(args)

    if args.command == "mof":
        from cockpit.commands.mof import cmd_mof

        return cmd_mof(args)

    if args.command == "scenario":
        from cockpit.commands.scenario import cmd_scenario

        return cmd_scenario(args)

    console.print(
        Panel.fit(
            "[bold cyan]🛸 Cockpit · L3 统一入口[/bold cyan]\n\n"
            "[bold]上下文[/]\n"
            "  [cyan]cockpit context[/]          — 系统上下文 (Phase/P0/约束)\n"
            "  [cyan]cockpit cards[/]            — CARDS 卡片列表\n"
            "  [cyan]cockpit cards --check[/]    — 操作合规检查\n"
            "  [cyan]cockpit vault search KEY[/] — 搜索知识库\n"
            "  [cyan]cockpit health[/]           — 一键系统健康\n"
            "  [cyan]cockpit brief[/]            — 会话简报\n\n"
            "[bold]研究对象[/]\n"
            '  [cyan]cockpit research "主题"[/]   — 发起研究\n'
            "  [cyan]cockpit research --list[/]   — 查看历史\n\n"
            "[bold]工具[/]\n"
            "  [cyan]cockpit search --all KEY[/]  — 跨源搜索 (本地+BOS)\n"
            "  [cyan]cockpit discover[/]           — 发现可用功能\n"
            "  [cyan]cockpit status[/]            — 工作台\n"
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


def _cmd_research_batch(args: Namespace) -> int:
    """批量研究模式 — 逐个处理多个 topic，汇总结果。"""
    from .commands.research import cmd_research

    topics = args.topic
    if len(topics) < 2:
        console.print("[red]batch 模式需要至少 2 个研究主题[/]")
        return 1

    results: list[dict[str, str | int]] = []
    start = time.time()
    import copy as _copy  # lazy to avoid overhead on non-batch path

    console.print(f"\n[bold cyan]📚 批量研究: {len(topics)} 个主题[/]\n")

    for i, t in enumerate(topics, 1):
        console.print(f"[bold yellow]⏳ [{i}/{len(topics)}][/] {t}")
        batch_args = _copy.copy(args)
        batch_args.topic = [t]
        batch_args.batch = False
        batch_args.stream = False  # batch 模式禁用流式避免交错
        try:
            ret = cmd_research(batch_args)
            results.append({"topic": t, "status": "ok" if ret == 0 else "error", "code": ret})
            status_icon = "[green]✅[/]" if ret == 0 else "[red]❌[/]"
            console.print(f"  {status_icon} 完成 [{i}/{len(topics)}]")
        except Exception as e:
            results.append({"topic": t, "status": "error", "error": str(e)})
            console.print(f"  [red]❌ 失败: {e}[/]")

    elapsed = time.time() - start
    ok = sum(1 for r in results if r["status"] == "ok")
    err = len(results) - ok

    console.print(f"\n[bold]批量研究完成: {ok} 成功, {err} 失败 · 耗时 {elapsed:.1f}s[/]")
    return 0 if err == 0 else 1


def _cmd_health(args: Namespace) -> int:
    """一键系统健康检查 — 聚合 Context + Status + 可选全栈检查。"""
    return_code = 0

    # ── L4 Context ──────────────────────────────────────────────
    console.print("\n[bold cyan]═══ L4 上下文 ═══[/]\n")
    try:
        from .commands.l4bridge import cmd_context

        cmd_context(args)
    except Exception:
        console.print("[yellow]⚠ L4 bridge 不可用[/]")
        return_code = 1

    # ── L3 Cockpit Status ───────────────────────────────────────
    console.print("\n[bold cyan]═══ L3 Cockpit ═══[/]\n")
    try:
        if args.json:
            from cockpit.scripts.cockpit_mcp import workspace_context

            print(workspace_context())
        else:
            cmd_status(args)
    except Exception as e:
        console.print(f"[red]Cockpit status error: {e}[/]")
        return_code = 1

        # ── Full: I0 Agora + L1 Runtime + L2 OMO ────────────────────
    if getattr(args, "full", False):
        console.print("\n[bold cyan]═══ I0 服务网格 ═══[/]\n")
        try:
            # Try l4-kernel for domain health first
            try:
                from l4_kernel import DomainRegistry

                reg = DomainRegistry()
                h = reg.aggregate_health()
                if not args.json:
                    console.print(
                        f"  [dim]域总数: {h['total']}  |  存在: {h['existing']}  |  健康率: {h['health_rate']}[/]"
                    )
            except ImportError:
                pass

            # Agora stats via subprocess as fallback
            import subprocess as _sp

            ws = Path(os.environ.get("WORKSPACE_ROOT", str(Path(__file__).resolve().parents[4])))
            agora_bin = ws / "projects" / "agora" / ".venv" / "bin" / "agora"
            if agora_bin.exists():
                result = _sp.run([str(agora_bin), "stats"], capture_output=True, text=True, timeout=15)
                if not args.json:
                    for line in result.stdout.split("\n"):
                        if "总计" in line or "健康" in line or "异常" in line or "健康率" in line:
                            console.print(f"  [dim]{line.strip()}[/]")
            else:
                console.print("[yellow]⚠ agora CLI 未安装[/]")
        except Exception as e:
            console.print(f"[yellow]⚠ I0 检查跳过: {e}[/]")

        # ── L4 Domain Health ──────────────────────────────────────
        console.print("\n[bold cyan]═══ L4 域健康 ═══[/]\n")
        try:
            from l4_kernel import DomainRegistry
            from l4_kernel.health import DomainHealth

            reg = DomainRegistry()
            dh = DomainHealth(reg)
            dashboard = dh.generate_dashboard()
            if not args.json:
                # Extract summary lines
                for line in dashboard.split("\n"):
                    if line.startswith("- **"):
                        console.print(f"  [dim]{line.strip()}[/]")
        except ImportError:
            console.print("[yellow]⚠ l4-kernel 未安装[/]")

        # ── Full: Runtime Matrix ────────────────────────────────
        console.print("\n[bold cyan]═══ L1 运行时 ═══[/]\n")
        matrix_path = Path.home() / "runtime" / "matrix_state.json"
        if not args.json and matrix_path.exists():
            try:
                import json as _j

                state = _j.loads(matrix_path.read_text())
                console.print(f"  [dim]服务注册: {len(state.get('services', {}))} 项[/]")
                h = sum(1 for s in state.get("services", {}).values() if s.get("healthy"))
                t = max(len(state.get("services", {})), 1)
                console.print(f"  [{'green' if h == t else 'yellow'}]健康: {h}/{t}[/]")
            except Exception:
                console.print("[yellow]⚠ Matrix state 解析失败[/]")
        elif not args.json:
            console.print("[yellow]⚠ Matrix state 未生成 (runtime scheduler 未运行)[/]")

        # ── Full: OMO Debt ───────────────────────────────────────
        console.print("\n[bold cyan]═══ L2 治理 ═══[/]\n")
        debt_path = ws / ".omo" / "state" / "system.yaml"
        if debt_path.exists():
            try:
                import yaml

                sys_data = yaml.safe_load(debt_path.read_text())
                if not args.json:
                    phase = sys_data.get("current_phase", "?")
                    health = sys_data.get("health_score", 0)
                    debt = sys_data.get("debt_weight", 0)
                    console.print(f"  [dim]Phase: {phase}  |  健康分: {health}  |  债务权重: {debt}[/]")
            except Exception:
                console.print("[yellow]⚠ OMO state 解析失败[/]")
        elif not args.json:
            console.print("[yellow]⚠ OMO state 未生成[/]")

        # ── Full: L4 文档域健康 ─────────────────────────────────
        console.print("\n[bold cyan]═══ L4 文档域 ═══[/]\n")
        l4_health = Path.home() / "Documents" / "@驾驶舱" / "_runtime" / "ecos-health-check.py"
        if l4_health.exists():
            try:
                import subprocess as _l4sp
                result = _l4sp.run(
                    [sys.executable, str(l4_health)],
                    capture_output=True, text=True, timeout=30,
                )
                if not args.json:
                    for line in result.stdout.split("\n"):
                        stripped = line.strip()
                        if stripped and not stripped.startswith("L4"):
                            console.print(f"  [dim]{stripped}[/]")
            except Exception as e:
                console.print(f"[yellow]⚠ L4 文档域检查跳过: {e}[/]")
        elif not args.json:
            console.print("[yellow]⚠ L4 健康脚本未找到 (创建 _runtime/ecos-health-check.py)[/]")

        console.print("\n[bold green]✅ 全栈健康检查完成[/]\n")

    return return_code


def _cmd_brief(args: Namespace) -> int:
    """生成会话简报。"""
    from datetime import datetime

    console.print(_panel("[bold cyan]📋 会话简报[/]", "cyan"))

    try:
        import json

        from cockpit.scripts.cockpit_mcp import cards_status, workspace_context

        ctx = json.loads(workspace_context())
        cards = json.loads(cards_status())

        console.print(f"Phase {ctx['phase']} · {ctx.get('theme', '')}")
        console.print(f"活跃卡片: {ctx['cards_summary']['active']} (P0: {ctx['cards_summary']['p0_open']})")

        if cards and args.force:
            console.print("\n[bold]P0 优先:[/]")
            for c in [c for c in cards if c["priority"] == "P0"]:
                console.print(f"  [red]▪[/] {c['title']}")

        console.print(f"\n[dim]生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}[/]")
    except Exception as e:
        console.print(f"[yellow]⚠ Brief generation limited: {e}[/]")

    return 0
    return 0


def _cmd_search(args: Namespace) -> int:
    """跨源搜索 — P2 记忆脊统一聚合搜索。"""
    console = Console()
    query = getattr(args, "query", "")
    if not query:
        console.print("[yellow]请输入搜索关键词[/]")
        console.print('  [cyan]cockpit search "关键词" --all[/]')
        return 1

    search_all = getattr(args, "all", False)
    limit = getattr(args, "limit", 10)

    zone_count: dict[str, int] = {}
    merged_results: list[dict] = []
    now = datetime.now().isoformat()

    # Zone 1: cockpit local SQLite FTS5
    try:
        from .storage import get_data_access
        local = get_data_access().search_research(query, limit=limit)
        zone_count["local"] = len(local)
        merged_results.extend(local)
    except Exception as e:
        zone_count["local"] = 0
        console.print(f"[dim]⚠ 本地搜索跳过: {e}[/]")

    # Zone 2: KOS (kairon/kos MCP stdio).
    # Gate C1 contract: zone_count.kos MUST be a real count derived from the
    # KOS response, not a hard-coded 1. We never inject a fake "stdout blob"
    # result item — that violates OPC P2.2 red line.
    #
    # Gate C2 contract: must actually invoke kairon/kos MCP server
    # (uv run python -m kos.mcp.server) over JSON-RPC stdio, parse
    # search_knowledge response, and map KOS schema
    # (doc_id/title/zone/canonical_path/updated_at/body_preview)
    # to P2 contract (id/title/snippet/_source/_source_path/_zone/_type/...).
    if search_all:
        zone_count["kos"] = 0  # default; updated only on real success
        try:
            kos_items = _invoke_kos_search(query, limit=limit)
            if kos_items:
                for item in kos_items:
                    item.setdefault("_source", "kairon-kos")
                    item.setdefault("_source_path", item.get("canonical_path", "bos://memory/kos/search"))
                    item.setdefault("_zone", "structured-memory")
                    item.setdefault("_type", "knowledge")
                    item.setdefault("_freshness", "unknown")
                    item.setdefault("_owner", "kairon")
                    item.setdefault("_reuse_policy", "reference-only")
                    item.setdefault("_retrieved_at", now)
                merged_results.extend(kos_items)
                zone_count["kos"] = len(kos_items)
        except Exception as e:
            _log_kos_skip(f"unexpected: {type(e).__name__}: {e}")

    # Zone 3: Vault (@学习进化 markdown 知识库).
    # Gate C3 contract: at least one real query must hit two zones.
    # Vault activation invokes the existing vault-search.sh (deterministic
    # fulltext/concept/tag/filename search) — which is the "确定范围" layer
    # of KEMS ("确定范围应该是确定性的，推理应该是概率性的").
    # Real subprocess call, real rg output, no fake file listing.
    if search_all:
        zone_count["vault"] = 0
        try:
            vault_items = _invoke_vault_search(query, limit=limit)
            if vault_items:
                for item in vault_items:
                    item.setdefault("_source", "@学习进化")
                    item.setdefault("_source_path", item.get("source_path", "vault://学习进化"))
                    item.setdefault("_zone", "document-vault")
                    item.setdefault("_type", "document")
                    item.setdefault("_freshness", "unknown")
                    item.setdefault("_owner", "vault")
                    item.setdefault("_reuse_policy", "derived-allowed")
                    item.setdefault("_retrieved_at", now)
                merged_results.extend(vault_items)
                zone_count["vault"] = len(vault_items)
        except Exception as e:
            _log_vault_skip(f"unexpected: {type(e).__name__}: {e}")

    # Zone 4: Trace Closure (Gate C4).
    # 把本次 search 的 input + zones + counts 持久化到 cockpit research
    # (writeback), 并把 list_research 命中作为 evidence 返回。
    # 红线: 不重复 writeback (用 query+now 简单去重), 不阻塞用户响应
    # (subprocess 静默错误)。
    trace: dict = {}
    if search_all:
        try:
            trace = _writeback_search_trace(
                query, zone_count, len(merged_results), limit, merged_results
            )
        except Exception as e:
            _log_trace_skip(f"unexpected: {type(e).__name__}: {e}")

    # ═══ P2 统一响应契约: zone, query, zone_count, results, total ═══
    # Task 2 (P2 closeout): multi-zone results visibility.
    # 必须保证每个 non-zero zone 至少 1 条代表项在 results[:limit] 中,
    # 然后 round-robin 补满. 否则 vault/kos 易被前面 zone 全部挤掉.
    interleaved = _interleave_by_source(merged_results, limit)
    response = {
        "zone": "all",
        "query": query,
        "zone_count": zone_count,
        "results": interleaved,
        "total": len(merged_results),
    }
    if trace.get("trace_id"):
        response["_trace"] = trace

    if args.json:
        import json as _json
        import sys as _sys
        # Gate C2: 必须 sys.stdout.write 直写, 绕过 rich console.print
        # (rich 会把 JSON 字符串里的 \\n literal 解释为 ANSI/控制字符,
        #  破坏 JSON 序列化)
        _sys.stdout.write(_json.dumps(response, ensure_ascii=False, indent=2))
        _sys.stdout.write("\n")
        _sys.stdout.flush()
    else:
        # 文本模式必须表达与 JSON 相同的核心事实 (zone / query / total / zone_count)
        console.print(
            f"\n[bold cyan]query:[/] {query}  "
            f"[bold cyan]zone:[/] all  "
            f"[bold cyan]total:[/] {len(merged_results)}  "
            f"[bold cyan]zones:[/] {zone_count}"
        )
        for item in interleaved:
            title = str(item.get("topic", item.get("title", str(item)[:80])))[:70]
            zone = item.get("_zone", "?")
            src = item.get("_source", "?")
            console.print(f"  ▸ [{zone}] {title}  [dim]{src}[/dim]")
        if not search_all:
            console.print("[dim]提示: 加 --all 搜索 BOS 知识引擎[/]")
        if trace.get("trace_id"):
            console.print(f"[dim]trace_id: {trace['trace_id']} ({'deduped' if trace.get('deduped') else 'new'})[/dim]")

    return 0


def _interleave_by_source(items: list[dict], limit: int) -> list[dict]:
    """Task 2 (P2 closeout): multi-zone results visibility.

    Guarantees that every non-zero zone (by _source) gets at least 1
    representative in the first `limit` results, then fills the remainder
    round-robin across the zones.

    Without this, a long local-zone prefix would push vault/kos items
    past the slice boundary even when zone_count shows them as non-zero.

    Strategy: bucket items by _source, then round-robin one item from
    each bucket per pass, until we hit `limit` or all buckets are empty.
    Order of zones = first-seen order (preserves caller-intended ordering).
    """
    if limit <= 0 or not items:
        return items[:limit] if limit > 0 else []
    buckets: dict[str, list[dict]] = {}
    order: list[str] = []
    for it in items:
        src = it.get("_source", "_unknown")
        if src not in buckets:
            buckets[src] = []
            order.append(src)
        buckets[src].append(it)
    out: list[dict] = []
    # Pass 1: ensure every non-empty bucket contributes at least 1
    for src in order:
        if buckets[src] and len(out) < limit:
            out.append(buckets[src].pop(0))
    # Pass 2: round-robin the remaining until limit or empty
    while len(out) < limit:
        progressed = False
        for src in order:
            if buckets[src] and len(out) < limit:
                out.append(buckets[src].pop(0))
                progressed = True
        if not progressed:
            break
    return out[:limit]


def _log_kos_skip(reason: str) -> None:
    """记录 KOS 跳过原因 (debug-level, 不污染用户输出)。"""
    import logging as _logging
    _logging.getLogger("cockpit.cli.kos").debug("KOS skip: %s", reason)


def _invoke_kos_search(query: str, limit: int = 10, timeout: float = 60.0) -> list[dict]:
    """Gate C2 — 真实调用 kairon/kos MCP server (JSON-RPC stdio) 并提取结果。

    流程:
      1. spawn `uv run python -m kos.mcp.server` (cwd = projects/kairon)
      2. MCP 握手 (initialize → initialized notification)
      3. tools/call search_knowledge {query, limit}
      4. 解析响应: result.content[0].text → JSON {query, results[], count}
      5. 把 KOS schema 映射到 P2 contract (id/title/snippet/timestamp/source_path)
      6. 返回 P2 items (空列表 if 任何一步失败)

    设计原则 (OPC P2.2 red lines):
      - 不重试 fake blob: 任何步骤失败返回 [], 绝不注入假数据
      - 不修改原始 KOS schema: 仅追加 P2 contract 字段
      - 完整错误捕获: subprocess / JSON / IO 全部 except
    """
    import json as _json
    import os as _os
    import select as _sel
    import subprocess as _sp

    ws_root = Path(_os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace")))
    kairon_dir = ws_root / "projects" / "kairon"
    if not kairon_dir.exists():
        _log_kos_skip(f"kairon dir not found: {kairon_dir}")
        return []

    try:
        proc = _sp.Popen(
            ["uv", "run", "python", "-m", "kos.mcp.server"],
            stdin=_sp.PIPE, stdout=_sp.PIPE, stderr=_sp.PIPE,
            text=True, bufsize=1, cwd=str(kairon_dir),
        )
    except (OSError, _sp.SubprocessError) as e:
        _log_kos_skip(f"spawn failed: {type(e).__name__}: {e}")
        return []

    try:
        # 1) initialize
        proc.stdin.write(_json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        }) + "\n")
        proc.stdin.flush()
        # 2) initialized notification
        proc.stdin.write(_json.dumps({
            "jsonrpc": "2.0", "method": "notifications/initialized",
        }) + "\n")
        proc.stdin.flush()
        # 3) tools/call search_knowledge
        proc.stdin.write(_json.dumps({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {
                "name": "search_knowledge",
                "arguments": {"query": query, "limit": limit},
            },
        }) + "\n")
        proc.stdin.flush()
        proc.stdin.close()

        # 4) blocking read with timeout, wait for "id": 2 response line
        buf = ""
        import time as _time
        deadline = _time.time() + timeout
        while _time.time() < deadline:
            r, _, _ = _sel.select([proc.stdout], [], [], 0.5)
            if r:
                chunk = _os.read(proc.stdout.fileno(), 65536).decode("utf-8", errors="replace")
                if not chunk:
                    break
                buf += chunk
                if '"id": 2' in buf and buf.rstrip().endswith("}"):
                    break
        else:
            _log_kos_skip(f"read timeout after {timeout}s")
            return []

        # 5) parse JSON-RPC response
        raw_results: list[dict] = []
        for line in buf.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                msg = _json.loads(line)
            except _json.JSONDecodeError:
                continue
            if msg.get("id") != 2:
                continue
            if "error" in msg:
                _log_kos_skip(f"kos error: {msg['error']}")
                return []
            content = msg.get("result", {}).get("content", [])
            for c in content:
                if c.get("type") == "text":
                    try:
                        payload = _json.loads(c["text"])
                    except _json.JSONDecodeError:
                        continue
                    if isinstance(payload, dict) and isinstance(payload.get("results"), list):
                        raw_results = [r for r in payload["results"] if isinstance(r, dict)]
                    break
            break

        if not raw_results:
            return []  # KOS 真实返回 0 → zone_count.kos=0, 不视为失败

        # 6) map KOS schema → P2 contract
        mapped: list[dict] = []
        for r in raw_results:
            # KOS schema: doc_id, title, kind, zone, status, canonical_path,
            #             trust_level, updated_at, body_preview
            title = str(r.get("title", r.get("canonical_path", "?")))
            updated = str(r.get("updated_at", ""))
            # 转换 YYYYMMDDHHMMSS → ISO 8601 (best effort)
            timestamp = _kos_ts_to_iso(updated)
            body_preview_raw = r.get("body_preview", "")
            # 控制字符清洗: KOS body_preview 实际含真换行符, 不清洗会破坏 JSON 序列化
            body_preview = _clean_control_chars(str(body_preview_raw))
            mapped.append({
                "id": r.get("doc_id", ""),
                "title": _clean_control_chars(title),
                "snippet": body_preview[:200],
                "source": "kairon-kos",  # P2 contract: producer
                "source_path": r.get("canonical_path", "bos://memory/kos/search"),
                "timestamp": timestamp,
                "type": "knowledge",
                "relevance": 1.0,
                # KOS native fields preserved
                "kind": r.get("kind", ""),
                "zone": r.get("zone", ""),
                "status": r.get("status", ""),
                "trust_level": r.get("trust_level", ""),
                "updated_at": updated,
                "body_preview": body_preview,
            })
        return mapped

    except Exception as e:
        _log_kos_skip(f"invoke error: {type(e).__name__}: {e}")
        return []
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            pass


def _kos_ts_to_iso(ts: str) -> str:
    """转换 KOS 时间戳 (YYYYMMDDHHMMSS) → ISO 8601。失败返回原值。"""
    if not ts or not ts.isdigit() or len(ts) != 14:
        return ts
    try:
        from datetime import datetime as _dt
        return _dt.strptime(ts, "%Y%m%d%H%M%S").isoformat() + "Z"
    except ValueError:
        return ts


def _clean_control_chars(s: str) -> str:
    """把字符串中的控制字符 (\\n \\r \\t 等) 替换为单空格, 保留可读性并避免破坏 JSON 序列化。"""
    if not s:
        return s
    import re as _re
    # 替换 \n \r \t \v \f 以及其他控制字符为单空格, 合并连续空格
    cleaned = _re.sub(r"[\x00-\x1f\x7f]+", " ", s)
    return _re.sub(r"\s+", " ", cleaned).strip()


def _log_vault_skip(reason: str) -> None:
    """记录 Vault 跳过原因 (debug-level)。"""
    import logging as _logging
    _logging.getLogger("cockpit.cli.vault").debug("vault skip: %s", reason)


def _invoke_vault_search(query: str, limit: int = 10, timeout: float = 30.0) -> list[dict]:
    """Gate C3 — 真实调用 @学习进化 vault-search.sh 提取结果。

    流程:
      1. 找到 @学习进化 Vault 根目录 (PATH 优先 / WORKSPACE_ROOT 推导 / 固定 fallback)
      2. spawn `bash _control/executors/vault-search.sh <query>` (cwd = vault root)
      3. 解析 stdout: 每个非空行 = 一个相对路径 (rg 命中 .md 文件)
      4. 把每个 path 映射到 P2 contract (id, title, snippet, source_path, ...)
      5. 标题: 路径 basename (去除 .md 后缀)
      6. snippet: 尝试读 file 第一段非 frontmatter 的标题/正文 (best effort)
      7. 返回 P2 items (空列表 if 任何一步失败)

    设计原则 (OPC P2.2 red lines):
      - 不重试 fake listing: 任何步骤失败返回 [], 绝不注入假数据
      - 实际执行真实脚本, 不绕过 rg
      - 完整错误捕获: subprocess / IO / OSError 全部 except
      - snippet 截断 200 字符 + 控制字符清洗
    """
    import os as _os
    import re as _re
    import subprocess as _sp

    # 1) 定位 Vault 根目录
    candidates = [
        _os.environ.get("LEARNING_VAULT"),
        _os.path.expanduser("~/Documents/@学习进化"),
        str(Path(_os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace"))).parent / "Documents" / "@学习进化"),
    ]
    vault_root = None
    for c in candidates:
        if c and Path(c).is_dir() and (Path(c) / "_control" / "executors" / "vault-search.sh").is_file():
            vault_root = c
            break
    if vault_root is None:
        _log_vault_skip("vault root not found")
        return []

    script = Path(vault_root) / "_control" / "executors" / "vault-search.sh"

    try:
        proc = _sp.Popen(
            ["bash", str(script), query],
            cwd=vault_root,
            stdout=_sp.PIPE, stderr=_sp.PIPE,
            text=True, bufsize=1,
        )
        try:
            stdout, _ = proc.communicate(timeout=timeout)
        except _sp.TimeoutExpired:
            proc.kill()
            proc.communicate()
            _log_vault_skip(f"timeout after {timeout}s")
            return []
    except (OSError, _sp.SubprocessError) as e:
        _log_vault_skip(f"spawn failed: {type(e).__name__}: {e}")
        return []

    if proc.returncode != 0 or not stdout:
        return []  # vault 真实返回 0 → zone_count.vault=0

    # 2) 解析输出: 第 1 行是 "🔍 全文搜索: QUERY" 头, 后续每行 = 一个相对路径
    raw_items: list[dict] = []
    path_re = _re.compile(r"^\./.+\.md$")
    for line in stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("🔍"):
            continue
        if not path_re.match(line):
            continue  # 跳过非文件路径行
        raw_items.append({"rel_path": line[2:]})  # strip "./"
        if len(raw_items) >= limit:
            break

    if not raw_items:
        return []

    # 3) 映射到 P2 contract
    mapped: list[dict] = []
    for r in raw_items:
        rel = r["rel_path"]
        abs_path = Path(vault_root) / rel
        title = abs_path.stem
        # 尝试读文件头 (snippet = 第一行非 frontmatter 的内容, 截断 200)
        snippet = _read_vault_snippet(abs_path)
        mapped.append({
            "id": rel,  # 用相对路径作为 ID (在 vault 内唯一)
            "title": _clean_control_chars(title),
            "snippet": snippet,
            "source": "@学习进化",  # P2 contract
            "source_path": rel,
            "timestamp": _vault_file_mtime(abs_path),
            "type": "document",
            "relevance": 1.0,
            "vault_zone": _infer_vault_zone(rel),
        })
    return mapped


def _read_vault_snippet(abs_path: Path) -> str:
    """读 vault 文件第一段非 frontmatter 内容, 截断 200 字符。失败返回空。"""
    try:
        text = abs_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    # 跳过 frontmatter
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            text = text[end + 4 :]
    # 取第一个非空行
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        return _clean_control_chars(line)[:200]
    return ""


def _vault_file_mtime(abs_path: Path) -> str:
    """读文件 mtime, 转 ISO 8601。失败返回 unknown。"""
    try:
        import datetime as _dt2
        mtime = abs_path.stat().st_mtime
        return _dt2.datetime.fromtimestamp(mtime, tz=_dt2.UTC).isoformat()
    except OSError:
        return "unknown"


def _infer_vault_zone(rel_path: str) -> str:
    """从相对路径推导 vault zone (control/entities/knowledge/storage/inbox/archive)。"""
    parts = rel_path.split("/", 1)
    if parts and parts[0].startswith("_"):
        return parts[0].lstrip("_")
    return "knowledge"


def _log_trace_skip(reason: str) -> None:
    """记录 trace 跳过原因 (debug-level)。"""
    import logging as _logging
    _logging.getLogger("cockpit.cli.trace").debug("trace skip: %s", reason)


def _writeback_search_trace(
    query: str,
    zone_count: dict,
    total: int,
    limit: int,
    merged_results: list[dict] | None = None,
) -> dict:
    """Gate C4 — 持久化 search trace 到 cockpit research (writeback)。

    流程:
      1. 检查 recent 60s 内是否有同 query 的 trace (去重, 避免重复 writeback)
      2. 调 cockpit storage.save_research, 把 trace 写入 research 表
        - topic:    "search-trace: <query>" (限长 200)
        - summary:  zone_count 字典 (JSON) + total + limit + 时间戳
        - full_text: 可复盘摘要, 每个非零 zone 列出 top-3 项
                     (source / title / source_path / timestamp)
        - source_count: total
        - agent:     "opc-p2-trace"
      3. 返回 trace dict: {trace_id, query, zone_count, total, timestamp, deduped,
                            hit_summary:[{zone, count, sample:[{...}]}]}

    设计原则 (OPC P2.2 red lines):
      - 不重复 writeback: 同 query 在 60s 内已存在则返回已有 trace (deduped=True)
      - 不阻塞: 任何步骤 except, 静默返回 {}
      - 不重试: 单次 save 失败 → 返回 {}
      - full_text 不再是固定占位串, 必须含真实命中摘要
    """
    import json as _json
    import time as _time
    try:
        from .storage import get_data_access
    except ImportError:
        from cockpit.storage import get_data_access
    da = get_data_access()
    now = _time.time()

    # 0) Build hit_summary (per-zone top-3) — used in both summary and full_text
    hit_summary = _build_hit_summary(merged_results or [], per_zone=3)

    # 1) dedup check: 60s 内同 query 的 trace
    # 用直接 SQL 查询 (避免 search_research 的 FTS5 特殊字符 bug:
    #  `search-trace: foo` 的冒号会让 FTS5 MATCH 报 no such column)
    try:
        da._ensure_db()
        _conn = da._connect()
        _rows = _conn.execute(
            "SELECT id, created_at FROM research "
            "WHERE topic LIKE ? AND agent = ? AND created_at > ? "
            "ORDER BY created_at DESC LIMIT 3",
            (f"search-trace: {query[:50]}%", "opc-p2-trace", now - 60),
        ).fetchall()
        _conn.close()
        recent = [{"id": r[0], "created_at": r[1]} for r in _rows]
    except Exception as e:
        _log_trace_skip(f"dedup check failed: {type(e).__name__}: {e}")
        recent = []

    for r in recent:
        created = r.get("created_at", 0)
        if created and (now - float(created)) < 60:
            return {
                "trace_id": r.get("id"),
                "query": query,
                "zone_count": zone_count,
                "total": total,
                "timestamp": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime(float(created))),
                "deduped": True,
                "hit_summary": hit_summary,
            }

    # 2) 写入新 trace
    summary_dict = {
        "query": query,
        "zone_count": zone_count,
        "total": total,
        "limit": limit,
        "timestamp": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime(now)),
        "hit_summary": hit_summary,
    }
    try:
        trace_id = da.save_research(
            topic=f"search-trace: {query[:200]}",
            summary=_json.dumps(summary_dict, ensure_ascii=False),
            full_text=_format_trace_full_text(query, zone_count, hit_summary),
            source_count=total,
            agent="opc-p2-trace",
        )
    except Exception as e:
        _log_trace_skip(f"save failed: {type(e).__name__}: {e}")
        return {}

    return {
        "trace_id": trace_id,
        "query": query,
        "zone_count": zone_count,
        "total": total,
        "timestamp": summary_dict["timestamp"],
        "deduped": False,
        "hit_summary": hit_summary,
    }


def _build_hit_summary(
    items: list[dict], per_zone: int = 3
) -> list[dict]:
    """Build a per-zone hit summary for trace writeback.

    Returns: [{"zone": str, "count": int, "sample": [{id, title, source, source_path, timestamp}, ...]}, ...]
    Order: first-seen zone order. Sample capped at `per_zone` items.
    """
    if not items:
        return []
    by_zone: dict[str, list[dict]] = {}
    order: list[str] = []
    for it in items:
        zone = it.get("_zone") or it.get("source") or "_unknown"
        if zone not in by_zone:
            by_zone[zone] = []
            order.append(zone)
        by_zone[zone].append(it)
    out: list[dict] = []
    for zone in order:
        bucket = by_zone[zone]
        sample = []
        for it in bucket[:per_zone]:
            sample.append(
                {
                    "id": it.get("id"),
                    "title": it.get("title") or it.get("topic") or "",
                    "source": it.get("source") or it.get("_source") or "",
                    "source_path": it.get("source_path")
                    or it.get("_source_path")
                    or "",
                    "timestamp": it.get("timestamp") or it.get("_retrieved_at") or "",
                }
            )
        out.append({"zone": zone, "count": len(bucket), "sample": sample})
    return out


def _format_trace_full_text(query: str, zone_count: dict, hit_summary: list[dict]) -> str:
    """Render trace full_text as a multi-line, human-readable summary.

    Per zone: zone, count, top sample (id / title / source / source_path / timestamp).
    Not a full blob — only what's needed to recap the recall.
    """
    lines: list[str] = []
    lines.append("P2 C4 search-trace writeback")
    lines.append(f"query: {query}")
    lines.append(f"zone_count: {json.dumps(zone_count, ensure_ascii=False, sort_keys=True)}")
    if not hit_summary:
        lines.append("hits: <none>")
        return "\n".join(lines) + "\n"
    for entry in hit_summary:
        zone = entry.get("zone", "?")
        count = entry.get("count", 0)
        lines.append(f"hits[{zone}]: count={count}")
        for s in entry.get("sample", []):
            sid = s.get("id", "")
            title = s.get("title", "")
            source = s.get("source", "")
            spath = s.get("source_path", "")
            ts = s.get("timestamp", "")
            lines.append(f"  - id={sid} title={title!r}")
            lines.append(f"    source={source} source_path={spath}")
            if ts:
                lines.append(f"    timestamp={ts}")
    return "\n".join(lines) + "\n"


def _cmd_discover(args: Namespace) -> int:
    """发现可用功能和资源。"""
    console = Console()
    console.print("[bold cyan]🛸 cockpit 可用功能[/bold cyan]\n")
    console.print("[bold]入口[/]")
    console.print("  [cyan]cockpit[/]                — 本帮助菜单")
    console.print("  [cyan]cockpit health --full[/]   — 全栈健康检查")
    console.print("  [cyan]cockpit search --all KEY[/]— 跨源搜索")
    console.print("  [cyan]cockpit discover[/]        — 本页面\n")
    console.print("[bold]BOS 资源域 (通过 agora MCP :7431)[/]")
    console.print("  [cyan]memory/[/]     — 知识存储 (kairon: kos/kronos/sophia)")
    console.print("  [cyan]governance/[/] — 治理 (omo + cockpit MCP)")
    console.print("  [cyan]analysis/[/]   — 分析 (minerva/ontoderive/codeanalyze)")
    console.print("  [cyan]persona/[/]    — 人格 (runtime)")
    console.print("  [cyan]capability/[/] — 能力 (forge/agora-proxy)\n")
    console.print("[bold]文档[/]")
    console.print("  [cyan]docs/PANORAMA.md[/]           — 系统全景架构")
    console.print("  [cyan]docs/JOURNEY-PROBES.md[/]     — 用户旅程探针")
    console.print("  [cyan]docs/ENTRY-CONVERGENCE.md[/]  — 入口收敛方案\n")
    console.print("[dim]提示: agora MCP 连接后可直接调用 resolve_bos_uri 使用所有功能[/]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
