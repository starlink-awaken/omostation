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
    cmd_bos_capability,
    cmd_bos_discover,
    cmd_bos_list,
    cmd_bos_status,
)
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
    model_driven_p.add_argument(
        "model_driven_args", nargs=argparse.REMAINDER, help="传递给 model-driven CLI 的参数"
    )

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
        epilog="package: kos / eidos / iris / code / ontoderive / minerva / sophia\n示例: cockpit kairon kos search 'attention'",
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
    family_hub_sub = family_hub_p.add_subparsers(
        dest="family_hub_command", parser_class=WorkspaceParser
    )
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
    bos_sub.add_parser("list", help="列出所有 BOS URI 路由")
    bos_sub.add_parser("discover", help="扫描 workspace 发现 MCP 服务")
    bos_sub.add_parser("status", help="BOS 系统状态与蜂群情况")

    # BOS Capability / Toolbox
    bos_capability_p = bos_sub.add_parser("capability", help="BOS capability 域 / toolbox 外部能力")
    bos_capability_sub = bos_capability_p.add_subparsers(dest="capability_command")
    bos_capability_sub.add_parser("list", help="列出 toolbox 中的 capability 服务")
    bos_capability_invoke_p = bos_capability_sub.add_parser("invoke", help="调用 capability 服务")
    bos_capability_invoke_p.add_argument("capability_service", help="服务 ID")

    # OPC P5-F4: 统一 scenario 入口 — 用户无需理解仓边界
    scenario_p = sub.add_parser(
        "scenario",
        help="P5 统一 scenario 入口 (radar/assistant/health)",
    )
    # 产品走查 v5 #V5-13: 默认人类可读面板, --json 输出机器可读原样 (脚本/管道消费)
    scenario_p.add_argument(
        "--json",
        action="store_true",
        dest="scenario_json",
        help="输出原始 JSON (脚本/管道消费); 默认人类可读面板",
    )
    scenario_sub = scenario_p.add_subparsers(dest="scenario_sub", parser_class=WorkspaceParser)
    scenario_radar = scenario_sub.add_parser(
        "radar", help="P5-F1 technical-radar: 扫描研究活动, 产出 ≥3 upgrade candidates"
    )
    scenario_radar.add_argument("--limit", type=int, default=10, help="最多产出多少 candidates (默认 10, 红线 ≥3)")
    scenario_assistant = scenario_sub.add_parser(
        "assistant", help="P5-F2 work-assistant: 1 真实工作 query → 结构化草稿"
    )
    scenario_assistant.add_argument("--query", type=str, default="OPC P5 progress", help="真实工作 query")
    scenario_health = scenario_sub.add_parser(
        "health", help="P5-F3 family-health: 1 真实家庭健康 query → 3 级 next-action (privacy=confidential)"
    )
    scenario_health.add_argument("--query", type=str, default="日常家庭健康问询", help="真实家庭健康 query")

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

    args = parser.parse_args()

    # ── Registry-Based Dispatch ──
    if not args.command:
        console.print(
            Panel.fit(
                "[bold cyan]🛸 Cockpit · L3 统一入口[/bold cyan]\n\n"
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
        elif sub == "capability":
            return cmd_bos_capability(a)
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

    def dispatch_wave2(a):
        from cockpit.commands.wave2 import cmd_wave2

        return cmd_wave2(a)

    def dispatch_workflow(a):
        from cockpit.commands.workflow import handle_workflow

        return handle_workflow(getattr(a, "workflow_args", []))

    def dispatch_agent_workflow(a):
        from cockpit.commands.agent_workflow import cmd_agent_workflow

        return cmd_agent_workflow(a)

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
        "wave2": dispatch_wave2,
        "workflow": dispatch_workflow,
        "agent-workflow": dispatch_agent_workflow,
        "agent": dispatch_agent_workflow,
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
        "debt": lambda a: __import__("cockpit.commands.debt_scoring", fromlist=["cmd_debt_score"]).cmd_debt_score(a),
    }

    handler = handlers.get(args.command)
    if handler:
        return handler(args)

    console.print(f"[red]未知命令: {args.command}[/]")
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
