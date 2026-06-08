#!/usr/bin/env python3
"""workspace — 产品级终端体验入口。"""

from __future__ import annotations

import argparse
import sys
import time as _time_mod
from pathlib import Path  # noqa: F401
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
    class WorkspaceParser(argparse.ArgumentParser):
        def error(self, message):
            parser_console = Console()
            parser_console.print(f"\n[red]Error: {message}[/]")
            parser_console.print("[yellow]试试以下命令:[/]")
            parser_console.print('  [cyan]workspace research "你的主题"[/]')
            parser_console.print("  [cyan]workspace research --list[/]")
            parser_console.print("  [cyan]workspace status[/]")
            parser_console.print("  [cyan]workspace demo[/]")
            parser_console.print()
            sys.exit(2)

    parser = WorkspaceParser(
        prog="workspace",
        description="Workspace — 产品级统一入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
旅程:
  research    深度研究 & 知识管理
  import      导入外部内容
  status      系统健康 & 研究状态
  demo        快速演示闭环
  daily       每日研究简报
  dashboard   打开 Web Dashboard

示例:
  workspace research "attention mechanism"
  workspace research --list
  workspace research --search "keyword"
  workspace research --open 1
  workspace research --ask 1 "追问问题"
  workspace research --publish 1 --style brief
  workspace research --dossier 1
  workspace research --timeline 1
  workspace research --tag 1 --labels llm agents
  workspace research --rename 1 --new-title better title
  workspace research --archive 1
  workspace research --unarchive 1
  workspace research --compare 1 2
  workspace research --merge 1 2
  workspace research --digest 1 2
  workspace research --audit
  workspace research --quarantine 4 5
  workspace research --restore 4 5
  workspace import ~/Desktop/note.md
  workspace status
  workspace status --watch --interval 2
  workspace contracts validate
  workspace contracts export-research 1
  workspace demo
  workspace daily
  workspace dashboard
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
    ctx_p = sub.add_parser("context", help="显示系统上下文 (Phase/CARDS/约束/引导)")
    cards_p = sub.add_parser("cards", help="显示 CARDS 卡片状态")
    cards_p.add_argument("--check", action="store_true", help="检查当前操作合规性")
    cards_p.add_argument("--card-id", type=str, help="检查指定卡片")
    vault_p = sub.add_parser("vault", help="搜索 L4 Vault 知识库")
    vault_p.add_argument("keyword", nargs="?", help="搜索关键词")

    domains_p = sub.add_parser("domains", help="列出 L4 所有域及其状态")
    skill_p = sub.add_parser("skill", help="运行 L4 定时技能")
    skill_p.add_argument("skill_name", help="技能名称 (如 kos-daily-ontology-sync)")

    health_p = sub.add_parser("health", help="一键系统健康检查")
    health_p.add_argument("--json", action="store_true", help="JSON 格式输出")
    health_p.add_argument("--full", action="store_true", help="全栈检查 (含 Agora 服务健康 + Runtime Matrix + OMO 债务)")

    brief_p = sub.add_parser("brief", help="会话简报")
    brief_p.add_argument("--force", action="store_true", help="强制重新生成")

    events_p = sub.add_parser("events", help="实时查看 Agora SSE 事件流 (Phase 34 L3 Dashboard)")
    events_p.add_argument("--url", default="http://127.0.0.1:8080/v1/events", help="Agora SSE Endpoint")

    sub.add_parser("version", help="版本信息")

    # Gap #7: MetaOS 工作流编排入口
    wf_p = sub.add_parser("workflow", help="🧠 MetaOS 工作流编排（动态规划 / 执行 / 历史）")
    wf_p.add_argument("workflow_args", nargs="*", help="workflow 子命令和参数")

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
            "[yellow]试试: [cyan]workspace data index[/] 或 [cyan]workspace data types[/] 或 [cyan]workspace data gc[/][/]"
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
                "[yellow]试试: [cyan]workspace contracts export identity[/] 或 [cyan]workspace contracts export event --id 1[/][/]"
            )
            return 1
        console.print(
            "[yellow]试试: [cyan]workspace contracts validate[/] 或 [cyan]workspace contracts list[/] 或 [cyan]workspace contracts export-research 1[/] 或 [cyan]workspace contracts export identity[/][/]"
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
        return handle_workflow(getattr(args, "workflow_args", []))

    console.print(
        Panel.fit(
            "[bold cyan]🛸 Cockpit · L3 统一入口[/bold cyan]\n\n"
            "[bold]上下文[/]\n"
            "  [cyan]workspace context[/]          — 系统上下文 (Phase/P0/约束)\n"
            "  [cyan]workspace cards[/]            — CARDS 卡片列表\n"
            "  [cyan]workspace cards --check[/]    — 操作合规检查\n"
            "  [cyan]workspace vault search KEY[/] — 搜索知识库\n"
            "  [cyan]workspace health[/]           — 一键系统健康\n"
            "  [cyan]workspace brief[/]            — 会话简报\n\n"
            "[bold]研究对象[/]\n"
            "  [cyan]workspace research \"主题\"[/]   — 发起研究\n"
            "  [cyan]workspace research --list[/]   — 查看历史\n\n"
            "[bold]工具[/]\n"
            "  [cyan]workspace status[/]            — 工作台\n"
            "  [cyan]workspace dashboard[/]         — Web 驾驶舱\n"
            "  [cyan]workspace mcp[/]               — MCP Server\n"
            "  [cyan]workspace demo[/]              — 5 分钟体验\n"
            "  [cyan]workspace code analyze[/]      — 代码分析\n"
            "  [cyan]workspace version[/]           — 版本信息\n\n"
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
            import subprocess as _sp
            from pathlib import Path as _P
            ws = _P(os.environ.get("WORKSPACE_ROOT", str(_P(__file__).resolve().parents[4])))
            agora_bin = ws / "projects" / "agora" / ".venv" / "bin" / "agora"
            if agora_bin.exists():
                result = _sp.run([str(agora_bin), "stats"], capture_output=True, text=True, timeout=15)
                if not args.json:
                    # Parse agora stats output for key metrics
                    for line in result.stdout.split("\n"):
                        if "总计" in line or "健康" in line or "异常" in line or "健康率" in line:
                            console.print(f"  [dim]{line.strip()}[/]")
                    healthy_count = result.stdout.count("healthy")
                    total_count = max(len([l for l in result.stdout.split("\n") if "│" in l and "┃" not in l]) - 1, 0)
            else:
                console.print("[yellow]⚠ agora CLI 未安装[/]")
        except Exception as e:
            console.print(f"[yellow]⚠ I0 检查跳过: {e}[/]")

        # ── Full: Runtime Matrix ────────────────────────────────
        console.print("\n[bold cyan]═══ L1 运行时 ═══[/]\n")
        matrix_path = _P.home() / "runtime" / "matrix_state.json"
        if not args.json and matrix_path.exists():
            try:
                import json as _j
                state = _j.loads(matrix_path.read_text())
                console.print(f"  [dim]服务注册: {len(state.get('services', {}))} 项[/]")
                h = sum(1 for s in state.get("services", {}).values() if s.get("healthy"))
                t = max(len(state.get("services", {})), 1)
                console.print(f"  [{'green' if h==t else 'yellow'}]健康: {h}/{t}[/]")
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

        console.print(f"\n[bold green]✅ 全栈健康检查完成[/]\n")

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
            for c in [c for c in cards if c['priority'] == 'P0']:
                console.print(f"  [red]▪[/] {c['title']}")

        console.print(f"\n[dim]生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}[/]")
    except Exception as e:
        console.print(f"[yellow]⚠ Brief generation limited: {e}[/]")

    return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
