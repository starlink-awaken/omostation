"""Cockpit CLI subcommand registration — extracted from cli.py main() (T6-10 god-module split).

This module contains all argparse subcommand registration logic (~750 lines),
keeping cli.py under the 1500L error threshold.

Usage:
    from cockpit._subcommands import register_subcommands
    register_subcommands(sub_parser, workspace_parser)
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def register_subcommands(sub: argparse._SubParsersAction, workspace_parser: type[argparse.ArgumentParser]) -> None:
    """Register all cockpit subcommands on the given sub-parser.

    Args:
        sub: The subparsers action from parser.add_subparsers()
        workspace_parser: Custom ArgumentParser class for workspace-aware help/errors
    """

    # ── research ──────────────────────────────────────────────
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
    r.add_argument(
        "--all-active",
        action="store_true",
        help="对全部活跃研究执行 --archive/--unarchive 操作",
    )
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
    r.add_argument(
        "--status",
        choices=["active", "archived", "all"],
        default="all",
        help="研究列表筛选（默认 all）",
    )
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

    # ── import / status / readiness ───────────────────────────
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

    # ── omo / debt / runtime ──────────────────────────────────
    omo_p = sub.add_parser(
        "omo",
        help="OMO CLI 委派 (debt/state/governance/lint/...)",
    )
    omo_p.add_argument(
        "omo_args",
        nargs=argparse.REMAINDER,
        help="传给 omo CLI 的参数 (如 'debt list', 'state sync --dry-run')",
    )

    # resident — 常驻 Agent 体系 (WP-A~I / ADR-0396)
    # 委派 omo.cli resident (SSOT: docs/architecture/resident-agent-system-v1.md)
    resident_p = sub.add_parser(
        "resident",
        help="Resident 常驻 Agent 体系 (status/roles/daemon/decision/execute/...)",
    )
    resident_p.add_argument(
        "resident_args",
        nargs=argparse.REMAINDER,
        help="传给 omo resident 的参数 (如 'status', 'roles', 'daemon --once')",
    )

    # bcos — BCOS 业务域系统 (W1~W4, 2026-08-23)
    # 委派根仓 bin/bc-os/*.py (SSOT: docs/architecture/bcos-system-v1.md)
    bcos_p = sub.add_parser(
        "bcos",
        help="BCOS 业务域系统 (evolve/signals/north-star)",
    )
    bcos_p.add_argument(
        "bcos_args",
        nargs=argparse.REMAINDER,
        help="传给 bin/bc-os 脚本的参数 (如 'evolve --json', 'signals', 'north-star --json')",
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

    # ── demo / gac / daily / data ─────────────────────────────
    sub.add_parser("demo", help="快速演示")
    sub.add_parser("gac", help="GaC 治理健康检查 (ADR-0106, 7 机制 + 115 规则 + drift)")
    daily_p = sub.add_parser("daily", help="每日研究简报")
    daily_p.add_argument("--days", type=int, default=1, help="回顾最近 N 天")
    daily_p.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    data_p = sub.add_parser("data", help="数据目录索引 / 类型注册 / TTL 清理")
    data_sub = data_p.add_subparsers(dest="data_command", parser_class=workspace_parser)
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

    # ── ADR-0200~0202 记忆/审计/算力 (stub, 待实现) ───────────
    sub.add_parser("memory-distill", help="记忆自蒸馏与冲突自愈 (ADR-0200)")
    sub.add_parser("audit-ledger", help="密码学级 Merkle 审计账本 (ADR-0201)")
    sub.add_parser("fabric-mesh", help="局域网边缘算力漫游网格 (ADR-0202)")

    # ── contracts ─────────────────────────────────────────────
    contracts_p = sub.add_parser("contracts", help="契约验证")
    contracts_sub = contracts_p.add_subparsers(dest="contracts_command", parser_class=workspace_parser)
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

    # ── dashboard / help / quickstart / init / profile ────────
    sub.add_parser("dashboard", help="打开 Web Dashboard")
    help_p = sub.add_parser(
        "help",
        help="查看产品地图与快速入门 (cockpit help <关键词> 模糊搜命令/工具/服务)",
    )
    help_p.add_argument("keyword", nargs="?", help="可选搜索关键词")
    qs_p = sub.add_parser("quickstart", help="🚀 新用户快速上手向导（环境核验 + 上手指引）")
    qs_p.add_argument("--fix", action="store_true", help="自动检测并修复常见问题")
    qs_p.add_argument(
        "--model",
        default="llama3.2",
        help="默认拉取的 LLM 模型名（默认 llama3.2）",
    )
    init_p = sub.add_parser("init", help="🚀 初始化向导（同 quickstart）")
    init_p.add_argument("--fix", action="store_true", help="自动检测并修复常见问题")
    init_p.add_argument(
        "--model",
        default="llama3.2",
        help="默认拉取的 LLM 模型名（默认 llama3.2）",
    )
    profile_p = sub.add_parser("profile", help="查看/编辑身份档案 (L4 入口)")
    profile_p.add_argument("--edit", action="store_true", help="编辑身份档案")

    sub.add_parser("product-health", help="产品健康度检测")

    # ── audit ─────────────────────────────────────────────────
    audit_p = sub.add_parser("audit", help="🔍 6 维度全方位审计 (调 bin/workspace-audit)")
    audit_p.add_argument(
        "--dim",
        type=str,
        choices=[
            "governance",
            "lint",
            "radar",
            "ssot",
            "gitlink",
            "ops",
            "all",
        ],
        default="all",
        help="只跑指定维度 (默认 all)",
    )
    audit_p.add_argument("--format", choices=["markdown", "json"], default="markdown", help="输出格式")
    audit_p.add_argument("--output", type=str, default=None, help="写报告到文件")
    audit_p.add_argument("--since", type=str, default="7d", help="agora 维度时间范围 (默认 7d)")

    # ── mcp ───────────────────────────────────────────────────
    mcp_p = sub.add_parser("mcp", help="启动 MCP server 或列出工具")
    mcp_p.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="传输协议（默认 stdio）",
    )
    mcp_p.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("AGORA_MCP_SSE_PORT", "7431")),
        help="SSE 模式监听端口",
    )
    mcp_p.add_argument("--list-tools", action="store_true", help="列出已注册的工具，不启动 server")
    mcp_p.add_argument(
        "--agora",
        action="store_true",
        help="--list-tools 时同时列出 agora (:7431) 的 BOS 服务/工具",
    )

    # ── gongwen / finance / governance ────────────────────────
    sub.add_parser(
        "gongwen",
        help="📄 公文写作门户引导 (文种/规范/入口, 委派 @公文 域)",
    )
    sub.add_parser(
        "finance",
        help="💰 个人财务门户引导 (场景/原则/入口, 委派 @个人 域)",
    )
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
    gov_p.add_argument(
        "extra_args",
        nargs=argparse.REMAINDER,
        help="传递给 arcnode-* 脚本的额外参数",
    )

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
    domain_status_p = sub.add_parser("domain-status", help="显示 Documents 域项目绑定与引导状态")
    domain_status_p.add_argument("domain_id", nargs="?", default="", help="可选 L4 域 ID")
    domain_status_p.add_argument("--json", action="store_true", help="输出稳定 JSON envelope")
    facts_audit_p = sub.add_parser("facts-audit", help="审计 Documents 文档域 facts 文件")
    facts_audit_p.add_argument("domain_id", nargs="?", default="", help="可选 document 域 ID")
    facts_audit_p.add_argument("--json", action="store_true", help="输出稳定 JSON envelope")
    facts_validation_p = sub.add_parser("facts-validation", help="读取 Runtime Facts 审计回执")
    facts_validation_p.add_argument("domain_id", help="L4 document 域 ID")
    facts_validation_p.add_argument("--json", action="store_true", help="输出稳定 JSON envelope")
    model_freshness_p = sub.add_parser("model-freshness", help="读取 Runtime 模型新鲜度回执")
    model_freshness_p.add_argument("domain_id", help="L4 document 域 ID")
    model_freshness_p.add_argument("--json", action="store_true", help="输出稳定 JSON envelope")
    sanyi_status_p = sub.add_parser("sanyi-status", help="读取 Runtime 三医状态一致性回执")
    sanyi_status_p.add_argument("domain_id", help="L4 document 域 ID")
    sanyi_status_p.add_argument("--json", action="store_true", help="输出稳定 JSON envelope")
    controller_shadow_p = sub.add_parser("controller-shadow", help="读取 Runtime 旧控制器影子迁移回执")
    controller_shadow_p.add_argument("domain_id", help="L4 document 域 ID")
    controller_shadow_p.add_argument("--json", action="store_true", help="输出稳定 JSON envelope")
    skill_p = sub.add_parser("skill", help="运行 L4 定时技能")
    skill_p.add_argument("skill_name", help="技能名称 (如 kos-daily-ontology-sync)")

    health_p = sub.add_parser("health", help="一键系统健康检查")
    health_p.add_argument("--json", action="store_true", help="JSON 格式输出")
    health_p.add_argument(
        "--full",
        action="store_true",
        help="全栈检查 (含 Agora 服务健康 + Runtime Matrix + OMO 债务)",
    )

    brief_p = sub.add_parser("brief", help="会话简报 / 每日早报 (--morning)")
    brief_p.add_argument("--force", action="store_true", help="强制重新生成")
    brief_p.add_argument("--morning", action="store_true", help="渲染每日业务与技术早报 (T7-03)")

    search_p = sub.add_parser("search", help="跨源搜索 (数据库 + BOS 知识引擎)")
    search_p.add_argument("query", help="搜索关键词")
    search_p.add_argument(
        "--all",
        action="store_true",
        help="搜索所有源 (本地 SQLite + BOS kos/gbrain)",
    )
    search_p.add_argument("--json", action="store_true", help="输出 P2 memory spine 统一 JSON 格式")
    search_p.add_argument("--limit", type=int, default=10, help="每源结果数 (默认10)")

    sub.add_parser("discover", help="发现可用功能和资源")

    # ── 统一能力发现 (Agent 感知 9.5/10) ──────────────────────
    cap_p = sub.add_parser(
        "capabilities",
        help="统一能力发现入口 — 搜索/推荐/全量列出 (CLI+BOS+Scene+Journey+Governance)",
    )
    cap_p.add_argument(
        "capabilities_command",
        nargs="?",
        default="list",
        choices=["list", "search", "recommend"],
        help="子命令: list(全量) / search(搜索) / recommend(任务推荐)",
    )
    cap_p.add_argument("--query", default="", help="搜索关键词 (search 子命令)")
    cap_p.add_argument("--task", default="", help="任务描述 (recommend 子命令)")

    events_p = sub.add_parser("events", help="实时查看 Agora SSE 事件流 (Phase 34 L3 Dashboard)")
    events_p.add_argument(
        "--url",
        default=f"http://127.0.0.1:{os.environ.get('AGORA_MCP_SSE_PORT', '7431')}/v1/events",
        help="Agora SSE Endpoint",
    )

    sub.add_parser("version", help="版本信息")

    # ── TUI ───────────────────────────────────────────────────
    tui_p = sub.add_parser("tui", help="极客终端交互控制台 (Textual 全屏 TUI)")
    tui_p.add_argument("--theme", default="dark", choices=["dark", "light"], help="配色主题")

    # ── BOS capability / inbox / watch ────────────────────────
    bcap_p = sub.add_parser("bos-capability", help="BOS capability / toolbox 外部能力")
    bcap_p.add_argument(
        "capability_command",
        nargs="?",
        default="list",
        choices=["list", "invoke"],
        help="子命令",
    )
    binbox_p = sub.add_parser("bos-inbox", help="BOS Inbox 多源私有知识神经网查询与操作")
    binbox_p.add_argument(
        "inbox_cmd",
        nargs="?",
        default="status",
        choices=["status", "search", "pending", "archive"],
        help="子命令",
    )
    binbox_p.add_argument("query", nargs="?", default="", help="搜索关键词")
    ewatch_p = sub.add_parser("events-watch", help="实时监听 SSE 事件流简便入口")
    ewatch_p.add_argument("--limit", type=int, default=20, help="显示最近的事件条数")
    qcheck_p = sub.add_parser("quickstart-check", help="快速检查新用户环境核验状态")
    qcheck_p.add_argument("--json", action="store_true", help="JSON 格式输出")

    # ── SSB / MOF / Agora / model-driven ──────────────────────
    ssb_p = sub.add_parser(
        "ssb",
        help="[DEPRECATED] SSB 签名链操作 — ECOS SSB 独立 CLI 已弃用",
        epilog="子命令 (源自 ecos-ssb): publish / query / state / recover / events / stats\n示例: cockpit ssb stats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ssb_p.add_argument("extra", nargs=argparse.REMAINDER, help="传递给 ecos-ssb 的参数")

    mof_p = sub.add_parser(
        "mof",
        help="MOF 元模型操作 (委派 mof CLI)",
        epilog="子命令 (源自 mof 引擎): validate / audit / derive / bridge-sync\n示例: cockpit mof validate",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mof_p.add_argument("extra", nargs=argparse.REMAINDER, help="传递给 mof 的参数")

    agora_p = sub.add_parser(
        "agora",
        help="Agora BOS 网关入口 (委派 agora CLI)",
        epilog="子命令: register / unregister / list / discover / health / pipeline / repo / mcp\n示例: cockpit agora list",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    agora_p.add_argument(
        "agora_args",
        nargs=argparse.REMAINDER,
        help="传递给 agora CLI 的参数",
    )

    model_driven_p = sub.add_parser(
        "model-driven",
        help="[DEPRECATED] 模型驱动生命周期入口 (ADR-0240 D1) — 拒绝执行",
        epilog="子命令: lifecycle / spec / adr / okr / tool / mcp\n示例: cockpit model-driven lifecycle dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    model_driven_p.add_argument(
        "model_driven_args",
        nargs=argparse.REMAINDER,
        help="传递给 model-driven CLI 的参数",
    )

    # ── brain / gbrain / kairon ───────────────────────────────
    brain_p = sub.add_parser(
        "brain",
        help="个人数字大脑 — 知识检索 + 记忆 + 智能问答",
        epilog='子命令: ask / context / remember / history\n示例: cockpit brain ask "卫健委借调总结怎么写？"',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    brain_sub = brain_p.add_subparsers(dest="brain_subcommand", parser_class=workspace_parser)
    brain_ask_p = brain_sub.add_parser("ask", help="向大脑提问（知识检索 + LLM 回答）")
    brain_ask_p.add_argument("question", nargs=argparse.REMAINDER, help="你的问题")
    brain_sub.add_parser("context", help="查看当前记忆摘要")
    brain_remember_p = brain_sub.add_parser("remember", help="手动存入偏好/事实")
    brain_remember_p.add_argument("fact", nargs=argparse.REMAINDER, help="要记住的内容")
    brain_history_p = brain_sub.add_parser("history", help="查看对话历史")
    brain_history_p.add_argument("--limit", "-n", type=int, default=20, help="显示条数")

    gbrain_p = sub.add_parser(
        "gbrain",
        help="Postgres-native 知识库入口 (委派 gbrain CLI)",
        epilog="子命令: search / import / stats / admin\n示例: cockpit gbrain search 'attention'",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    gbrain_p.add_argument(
        "gbrain_args",
        nargs=argparse.REMAINDER,
        help="传递给 gbrain CLI 的参数",
    )

    kairon_p = sub.add_parser(
        "kairon",
        help="kairon 知识引擎 monorepo 聚合入口",
        epilog="package: kos / eidos / iris / code / ontoderive / minerva / kronos / sophia\n示例: cockpit kairon kronos fetch https://example.com",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    kairon_p.add_argument(
        "kairon_args",
        nargs=argparse.REMAINDER,
        help="package + 子命令参数",
    )

    # ── Omni-Bus ──────────────────────────────────────────────
    bus_p = sub.add_parser("bus", help="Omni-Bus 三平面入口")
    bus_sub = bus_p.add_subparsers(dest="bus_command", parser_class=workspace_parser)
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
    bus_control_sub = bus_control_p.add_subparsers(dest="control_command", parser_class=workspace_parser)
    bus_control_submit_p = bus_control_sub.add_parser("submit", help="提交控制任务")
    bus_control_submit_p.add_argument("--topic", required=True, help="topic 名")
    bus_control_submit_p.add_argument("--payload", default="{}", help="JSON payload")
    bus_control_ack_p = bus_control_sub.add_parser("ack", help="确认任务完成")
    bus_control_ack_p.add_argument("--task-id", required=True, help="任务 ID")
    bus_control_nack_p = bus_control_sub.add_parser("nack", help="否定确认任务")
    bus_control_nack_p.add_argument("--task-id", required=True, help="任务 ID")
    bus_control_nack_p.add_argument("--error", default="nacked", help="失败原因")

    # ── observe / family-hub / mesh ───────────────────────────
    observe_p = sub.add_parser("observe", help="可观测性栈（Langfuse）入口")
    observe_sub = observe_p.add_subparsers(dest="observe_command", parser_class=workspace_parser)
    observe_sub.add_parser("status", help="Docker compose 状态")
    observe_sub.add_parser("up", help="启动观测栈")
    observe_sub.add_parser("down", help="停止观测栈")
    observe_logs_p = observe_sub.add_parser("logs", help="查看日志")
    observe_logs_p.add_argument("--service", default="langfuse-server", help="服务名")
    observe_sub.add_parser("url", help="打印 Langfuse Web URL")

    family_hub_p = sub.add_parser("family-hub", help="家庭数字枢纽入口")
    family_hub_sub = family_hub_p.add_subparsers(dest="family_hub_command", parser_class=workspace_parser)
    family_hub_sub.add_parser("status", help="API/MCP server 状态")
    family_hub_sub.add_parser("api", help="启动 API server")
    family_hub_sub.add_parser("mcp", help="启动 MCP server")
    family_hub_sub.add_parser("client", help="以 REPL 模式连接到 MCP server")

    mesh_p = sub.add_parser("mesh", help="omlx 算力网格路由入口")
    mesh_sub = mesh_p.add_subparsers(dest="mesh_command", parser_class=workspace_parser)
    mesh_sub.add_parser("nodes", help="列出 KOS 中注册的算力节点")
    mesh_sub.add_parser("status", help="mesh router 健康状态")
    mesh_sub.add_parser("fabric", help="检查 omlxc 智能算力织网 (温控/分诊/显存/缓存)")
    mesh_triage_p = mesh_sub.add_parser("triage", help="分析 Prompt 意图复杂度分级")
    mesh_triage_p.add_argument("prompt", help="待分析的 Prompt 文本")
    mesh_vram_p = mesh_sub.add_parser("vram", help="计算模型动态 KV Cache 显存预算")
    mesh_vram_p.add_argument("model", help="模型 ID (如 coding / qwen-72b)")
    mesh_vram_p.add_argument("tokens", type=int, help="上下文 Token 数量")
    mesh_warm_p = mesh_sub.add_parser("warm", help="预热系统 Prompt 前缀缓存以实现 0ms TTFT")
    mesh_warm_p.add_argument("--model", "-m", default="coding", help="目标模型 ID (默认 coding)")
    mesh_route_p = mesh_sub.add_parser("route", help="为模型选择最优节点")
    mesh_route_p.add_argument("--model", required=True, help="模型名")
    mesh_sub.add_parser("cache", help="检查三级分层缓存与 Radix 前缀树状态 (含基准压测)")
    mesh_sub.add_parser("dflash", help="DFlash 2 块扩散投机解码加速与集群基准")
    mesh_sub.add_parser("cluster", help="异构三节点智能路由与拓扑诊断")
    mesh_sub.add_parser("tree", help="自适应熵感知树状投机解码与多候选验证基准")
    mesh_sub.add_parser("stream", help="跨节点 Chunk-level 流式协同流水线基准")
    mesh_sub.add_parser("swarm", help="分布式跨节点 KV 共享池与超长上下文置换基准")
    mesh_sub.add_parser("hud", help="查看次世代主权算力织网全景 HUD 实时状态")
    mesh_sub.add_parser("heatmap", help="查看分布式 KV 内存池热力分布与投机蒸馏指标")
    mesh_sub.add_parser("dma", help="测试雷雳 5 跨机零拷贝 DMA 通道与换页基准")
    mesh_sub.add_parser("lora", help="查看与测试端侧在线 LoRA 适配层热插拔")
    mesh_compact_p = mesh_sub.add_parser("compact", help="上下文滑动蒸馏与双区自适应量化压缩模拟")
    mesh_compact_p.add_argument("--model", "-m", default="coding", help="目标模型 ID")
    mesh_compact_p.add_argument("--tokens", "-t", type=int, default=32768, help="目标 Token 数")
    mesh_compact_p.add_argument("--available-mb", "-a", type=int, default=4096, help="可用显存 MB")
    mesh_sub.add_parser("serve", help="启动 mesh router HTTP server")

    # ── spine ────────────────────────────────────────────────
    spine_p = sub.add_parser("spine", help="Spine 主干真值流与署名自进化操作 (ADR-0437)")
    spine_sub = spine_p.add_subparsers(dest="spine_command", parser_class=workspace_parser)
    spine_draft_p = spine_sub.add_parser("draft", help="从本地主权大模型请求草稿")
    spine_draft_p.add_argument("--prompt", "-p", required=True, help="草稿生成提示词")
    spine_draft_p.add_argument("--model", "-m", default="qwen3.8-27b", help="模型 ID")
    spine_sign_p = spine_sub.add_parser("sign", help="提交用户署名 Diff 并入队 Experience Replay")
    spine_sign_p.add_argument("--original", "-o", default="", help="原始草稿内容")
    spine_sign_p.add_argument("--signed", "-s", required=True, help="署名后的最终内容")
    spine_sign_p.add_argument("--domain", "-d", default="signature-style", help="领域标签")
    spine_sub.add_parser("diff", help="查看待处理署名 Diff 统计")
    spine_sub.add_parser("status", help="查看 DMA 守护进程实时遥测状态")
    spine_distill_p = spine_sub.add_parser("distill", help="在 Mac mini M4 触发闲时 LoRA 蒸馏")
    spine_distill_p.add_argument("--domain", "-d", default="signature-style", help="领域标签")
    spine_distill_p.add_argument("--epochs", "-e", type=int, default=3, help="训练轮数")
    spine_sub.add_parser("replay", help="查看 Experience Replay 缓冲区状态")


    # ── BOS URI gateway ───────────────────────────────────────
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

    # ── channels / swarm ──────────────────────────────────────
    channels_p = sub.add_parser(
        "channels",
        help="🌐 External channels inventory (ECCP) — 生成/查看 external-channels.yaml",
    )
    channels_p.add_argument(
        "--quiet",
        action="store_true",
        help="只跑生成器，不打印 human summary",
    )

    swarm_p = sub.add_parser(
        "swarm",
        help="🤖 多 agent 实时活动监控 (active runs/locks/worktree/claims/子模块 dirty/冲突)",
    )
    swarm_mode = swarm_p.add_mutually_exclusive_group()
    swarm_mode.add_argument("--tui", action="store_true", help="Rich TUI 实时刷新模式 (默认单次)")
    swarm_mode.add_argument("--json", action="store_true", help="JSON 输出")
    swarm_mode.add_argument("--watch", type=int, default=0, metavar="SEC", help="每隔 N 秒文本刷新")
    swarm_p.add_argument("--refresh", type=int, default=5, help="TUI 刷新间隔秒 (默认 5)")

    # ── BOS inbox / capability ────────────────────────────────
    bos_inbox_p = bos_sub.add_parser("inbox", help="BOS Inbox 多源私有知识神经网查询与操作")
    bos_inbox_sub = bos_inbox_p.add_subparsers(dest="inbox_cmd")
    bos_inbox_sub.add_parser("status", help="统计多源神经网本地证据与嵌入状态")
    bos_inbox_search_p = bos_inbox_sub.add_parser("search", help="语义搜索多源记忆")
    bos_inbox_search_p.add_argument("query", help="搜索关键词")
    bos_inbox_pending_p = bos_inbox_sub.add_parser("pending", help="查看未决待办快照预览")
    bos_inbox_pending_p.add_argument(
        "--source",
        default="seeyon_oa",
        help="来源: seeyon_oa | netease_mailmaster | apple_mail",
    )
    bos_inbox_sub.add_parser(
        "watch",
        help="监听 BOS Inbox 紧急待办与提醒快照 (Event-Driven Watcher)",
    )
    bos_inbox_archive_p = bos_inbox_sub.add_parser("archive", help="归档已处理完毕的 Inbox 待办文件")
    bos_inbox_archive_p.add_argument("filename", help="文件名或 all")
    bos_inbox_archive_p.add_argument("--reason", default="resolved", help="归档事由")

    bos_capability_p = bos_sub.add_parser("capability", help="BOS capability 域 / toolbox 外部能力")
    bos_capability_sub = bos_capability_p.add_subparsers(dest="capability_command")
    bos_capability_sub.add_parser("list", help="列出 toolbox 中的 capability 服务")
    bos_capability_invoke_p = bos_capability_sub.add_parser(
        "invoke", help="通过治理网关调用 exact native BOS capability"
    )
    bos_capability_invoke_p.add_argument(
        "capability_service",
        help="完整 BOS URI 或 canonical ID；不接受短名或子串",
    )
    bos_capability_invoke_p.add_argument(
        "--input-json",
        dest="capability_input_json",
        type=Path,
        required=True,
        help="结构化输入 JSON 文件（上限由治理网关执行）",
    )
    bos_capability_invoke_p.add_argument(
        "--binding-json",
        dest="capability_binding_json",
        type=Path,
        help="完整 trace binding JSON 文件",
    )
    bos_capability_invoke_p.add_argument(
        "--inspection-receipt-json",
        dest="capability_inspection_receipt_json",
        type=Path,
        help="native inspection receipt JSON 文件",
    )
    bos_capability_invoke_p.add_argument(
        "--admission-receipt-json",
        dest="capability_admission_receipt_json",
        type=Path,
        help="admission receipt JSON 文件",
    )
    bos_capability_invoke_p.add_argument(
        "--operation-id",
        dest="capability_operation_id",
        help="exact operation identifier",
    )
    bos_capability_invoke_p.add_argument(
        "--effect-classification",
        dest="capability_effect_classification",
        choices=("read_only", "effectful"),
        help="operation effect classification",
    )

    # ── scenario ──────────────────────────────────────────────
    scenario_p = sub.add_parser(
        "scenario",
        help="P5 统一 scenario 入口 (radar/assistant/health/inbox/intake/task/approval/connector/review)",
    )
    from cockpit.commands.scenario import build_scenario_parser

    build_scenario_parser(scenario_p, workspace_parser)

    # ── workflow / agent-workflow / agent / agent-onboard ─────
    wf_p = sub.add_parser(
        "workflow",
        help="🧠 工作流编排（MetaOS 动态规划 / ecos L0 M1 引擎）",
        epilog='子命令: plan / run / history / approve (MetaOS) | ecos (L0 M1 引擎)\n示例:\n  cockpit workflow ecos list\n  cockpit workflow plan "目标"\n  cockpit workflow history',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    wf_p.add_argument("workflow_args", nargs=argparse.REMAINDER, help="workflow 子命令和参数")

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

    # ── agent-runtime ─────────────────────────────────────────
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

    # ── iterate / compass / wave2 / bdsk ──────────────────────
    iterate_p = sub.add_parser(
        "iterate",
        help="♻️ C2G 双擎迭代流 (MetaOS 发散 -> Model-Driven 桥接 -> OMO 门控执行)",
    )
    iterate_p.add_argument("topic", nargs="?", default="未命名探索主题", help="要发起探索的主题")
    iterate_p.add_argument(
        "--mock",
        action="store_true",
        help="是否模拟生成带 TODO 的测试数据以触发门控",
    )

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
    compass_p.add_argument(
        "compass_args",
        nargs=argparse.REMAINDER,
        help="Arguments passed to c2g compass engine",
    )

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

    bdsk_p = sub.add_parser(
        "bdsk",
        help="🧠 B.D.S.K. 虚拟董事会 (4角对抗辩论与 0-Touch 影子预演)",
    )
    bdsk_p.add_argument("bdsk_subcmd", nargs="?", default="debate", help="debate|simulate (default: debate)")
    bdsk_p.add_argument("topic", nargs="?", default="架构决策与技术选型", help="辩论主题或决策方案")

    # ── journey / panorama / project / monitor ────────────────
    sub.add_parser("journey", help="🗺️ Journey State Graph 状态表达校验器")
    sub.add_parser(
        "panorama",
        help="🌐 7 维全景终极可观测仪表盘 (执行过程/服务/内容/知识/数据/异常/债务资产)",
    )

    proj_p = sub.add_parser("project", help="🔍 17 项目全景 4D 体检与诊断")
    proj_p.add_argument("project_subcmd", nargs="?", default="inspect", help="inspect|list (default: inspect)")
    proj_p.add_argument("project_name", nargs="?", default="", help="指定项目名称")
    proj_p.add_argument("--json", action="store_true", help="JSON 输出")

    sub.add_parser(
        "monitor",
        help="📊 实时终端大盘 (C2G Pipeline 监控仪, 实时刷新 Ctrl+C 退出)",
    )

    # ── code ──────────────────────────────────────────────────
    code_p = sub.add_parser("code", help="代码库分析与审查 (基于 codeanalyze)")
    code_sub = code_p.add_subparsers(dest="code_command", parser_class=workspace_parser)
    code_sub.add_parser("analyze", help="运行全部分析工具")
    code_sub.add_parser("graph", help="运行语义图谱分析")
    code_sub.add_parser("pack", help="将代码库打包为 LLM 友好格式")
    code_sub.add_parser("dashboard", help="启动交互式知识图谱仪表盘")
    code_workflow_p = code_sub.add_parser("workflow", help="高级分析工作流")
    code_workflow_sub = code_workflow_p.add_subparsers(dest="workflow_command")
    code_impact_p = code_workflow_sub.add_parser("impact", help="分析符号的变更影响面")
    code_impact_p.add_argument("--symbol", help="目标符号名称")
    code_workflow_sub.add_parser("onboarding", help="为 AI 构建项目全貌上下文")

    # ── compute ───────────────────────────────────────────────
    compute_p = sub.add_parser(
        "compute",
        help="算力与 LLM 网关操作 (委派 aetherforge)",
        epilog="子命令: gateway generate / gateway list / mesh list / mesh status / mesh cost / swarm run\n示例: cockpit compute gateway generate 'hello'",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    compute_p.add_argument("compute_command", nargs="?", help="gateway/mesh/swarm")
    compute_p.add_argument("extra", nargs=argparse.REMAINDER, help="传递给 aetherforge 的参数")

    # ── ask & proxy-env ───────────────────────────────────────────────
    ask_p = sub.add_parser("ask", help="快速大模型对话问答 (AetherForge)")
    ask_p.add_argument("prompt", nargs="+", help="对话内容")
    ask_p.add_argument("--model", "-m", help="指定模型 ID (例如 omlxc/coding-next)")

    sub.add_parser("proxy-env", help="输出兼容外部客户端的本地环境变量 (OPENAI_API_BASE)")

    # ── knowledge / memory / kems / c2g ───────────────────────
    knowledge_p = sub.add_parser("knowledge", help="📚 KOS 知识检索 (search/status/stats)")
    knowledge_sub = knowledge_p.add_subparsers(dest="knowledge_command")
    knowledge_search_p = knowledge_sub.add_parser("search", help="语义搜索")
    knowledge_search_p.add_argument("query", nargs="?", help="搜索词")
    knowledge_search_p.add_argument("--limit", type=int, default=5, help="结果数 (默认 5)")
    knowledge_sub.add_parser("status", help="KOS 服务健康")
    knowledge_sub.add_parser("stats", help="索引统计")

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

    kems_p = sub.add_parser("kems", help="🧬 KEMS 域治理 (domains/status/scan)")
    kems_sub = kems_p.add_subparsers(dest="kems_command")
    kems_sub.add_parser("domains", help="列出 28 域状态")
    kems_status_p = kems_sub.add_parser("status", help="控制面状态")
    kems_status_p.add_argument("--json", action="store_true", help="输出稳定 JSON envelope")
    kems_sub.add_parser("scan", help="平面扫描")

    c2g_p = sub.add_parser("c2g", help="🎯 C2G 战略罗盘 (status/pipeline)")
    c2g_sub = c2g_p.add_subparsers(dest="c2g_command")
    c2g_sub.add_parser("status", help="全局状态 (radar)")
    c2g_sub.add_parser("pipeline", help="pipeline 概览")

    # ── V2 认知治理与意图编译器 (ADR-0195) ───────────────────────────
    intent_p = sub.add_parser("intent", help="🧠 自然语言意图解构与工程规格编译器 (ADR-0195)")
    intent_p.add_argument("prompt", nargs="+", help="自然语言意图或需求描述")
    intent_p.add_argument("--domain", help="显式指定领域 (work-weijian, work-transfer, engineering)")
    intent_p.add_argument("--json", action="store_true", help="以 JSON 格式输出")

    # ── 决策收件箱 ──────────────────────────────────────────────────
    decide_p = sub.add_parser("decide", help="📬 决策收件箱 (列出/添加/批准/拒绝)")
    decide_sub = decide_p.add_subparsers(dest="decide_action")
    decide_sub.add_parser("list", help="列出待决策项")
    decide_add = decide_sub.add_parser("add", help="手动添加决策项")
    decide_add.add_argument("title", nargs="+", help="决策标题")
    decide_approve = decide_sub.add_parser("approve", help="批准决策")
    decide_approve.add_argument("id", help="决策 ID")
    decide_reject = decide_sub.add_parser("reject", help="拒绝决策")
    decide_reject.add_argument("id", help="决策 ID")
    decide_sub.add_parser("status", help="收件箱状态概览")

    # ── V2 影子红蓝对抗审查与自动打补丁 (ADR-0196) ─────────────────────
    chall_p = sub.add_parser("challenge", help="⚡️ 影子红蓝对抗审查与合规自动打补丁 (ADR-0196)")
    chall_p.add_argument("target", help="待审查的方案文件路径或文本")
    chall_p.add_argument("--domain", help="显式指定领域")
    chall_p.add_argument("--auto-patch", action="store_true", help="自动合成合规增强段落")
    chall_p.add_argument("--strict", action="store_true", help="存在任何违规时非零退出")
    chall_p.add_argument("--json", action="store_true", help="以 JSON 格式输出")

    # ── V2 长尾领域治理卡带工坊 (ADR-0198) ─────────────────────────
    cart_p = sub.add_parser("cartridge", help="👁️ 长尾领域治理卡带工坊 (ADR-0198/0203)")
    cart_sub = cart_p.add_subparsers(dest="action")
    cart_sub.add_parser("list", help="列出已注册卡带")
    cart_exp = cart_sub.add_parser("export", help="导出指定卡带")
    cart_exp.add_argument("cartridge_id", help="卡带ID (e.g. cartridge-weijian-v1)")
    cart_exp.add_argument("--output", help="导出文件路径")
    cart_val = cart_sub.add_parser("validate", help="校验卡带文件规范")
    cart_val.add_argument("file_path", help="卡带 YAML/ZIP 文件路径")
    cart_pack = cart_sub.add_parser("pack", help="打包源码目录为签名胶囊 (.cartridge)")
    cart_pack.add_argument("source_dir", help="领域源码目录")
    cart_pack.add_argument("--output", required=True, help="输出卡带路径 (e.g. out.cartridge)")
    cart_run = cart_sub.add_parser("run", help="在隔离沙箱中挂载卡带并执行领域意图")
    cart_run.add_argument("cartridge_file", help="卡带文件 (.cartridge)")
    cart_run.add_argument("--intent", required=True, help="领域执行意图")

    # ── AGE-v2 Agent Cell ────────────────────────────────────────
    cell_p = sub.add_parser("cell", help="🤖 AGE-v2 动态 Agent Cell (规划/执行/验证/治理)")
    cell_p.add_argument(
        "cell_action",
        nargs="?",
        default="help",
        choices=["plan", "execute", "verify", "govern", "pdp", "pep", "memory", "replay", "dashboard"],
        help="Cell 子命令",
    )
    cell_p.add_argument("cell_args", nargs="*", help="子命令参数")

    # ── V2 主权算力网络与 0ms TTFT 快照 (ADR-0197) ─────────────────
    fab_p = sub.add_parser("fabric", help="🧑‍💻 主权混合算力与 KV 缓存快照 (ADR-0197)")
    fab_sub = fab_p.add_subparsers(dest="action")
    fab_sub.add_parser("inspect", help="查看算力网格健康度与节点状态")
    fab_snap = fab_sub.add_parser("snapshot", help="KV 缓存快照管理与预热")
    fab_snap.add_argument("snapshot_action", nargs="?", default="list", choices=["list", "create", "warm"])
    fab_snap.add_argument("--name", help="快照名称")
    fab_snap.add_argument("--model", help="模型名称")
    fab_eval = fab_sub.add_parser("speculative-eval", help="本地首选投机推演评估")
    fab_eval.add_argument("prompt", help="任务提示词")
    fab_eval.add_argument("--domain", help="领域标识")

    # ── watchdog ───────────────────────────────────────────────
    watchdog_p = sub.add_parser("watchdog", help="🐕 自治守护犬与自愈探针 (Agora Bus / Resident 监视器)")
    watchdog_p.add_argument("--probe", action="store_true", help="仅执行单轮自愈探针检查并输出状态")
    watchdog_p.add_argument("--json", action="store_true", help="以 JSON 格式输出健康数据")
    watchdog_p.add_argument("--interval", type=float, default=5.0, help="守护巡检间隔秒数 (默认 5.0)")

    # ── policy ────────────────────────────────────────────────
    policy_p = sub.add_parser("policy", help="⚖️ 领域监管合规与 Policy-as-Code 红线审查 (E-POL-*)")
    policy_p.add_argument("policy_args", nargs=argparse.REMAINDER, help="传递给 ecos-constraint policy 的参数")

    # ── ops (Service Gateway) ─────────────────────────────────
    ops_p = sub.add_parser(
        "ops", help="🔧 Service Gateway — 统一运维控制面 (status/up/down/deploy/deps/logs/discover/validate/generate)"
    )
    ops_p.add_argument(
        "ops_action",
        nargs="?",
        default="status",
        choices=["status", "up", "down", "deploy", "deps", "logs", "summary", "discover", "validate", "generate"],
        help="ops 子命令 (默认: status)",
    )
    ops_p.add_argument("service", nargs="?", help="服务 ID (用于 up/down/deps/validate)")
    ops_p.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    ops_p.add_argument("--dry-run", action="store_true", help="预览模式 (不实际执行)")
    ops_p.add_argument("--profile", choices=["minimal", "full"], default="full", help="部署配置")
    ops_p.add_argument(
        "--format", choices=["docker-compose", "systemd", "launchd"], default="docker-compose", help="生成格式"
    )
    ops_p.add_argument("--output", "-o", help="输出文件路径")
    ops_p.add_argument("--update", action="store_true", help="更新 services.yaml")
    ops_p.add_argument("-n", "--lines", type=int, default=50, help="日志行数")
