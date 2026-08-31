"""Cockpit CLI product map — grouped command catalog for `cockpit help` / `--help`.

Keeps human-facing navigation SSOT for CLI discovery (not a substitute for
per-command --help). Update when adding top-level commands in cli.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


@dataclass(frozen=True)
class CmdRow:
    name: str
    blurb: str
    example: str = ""


# ── Catalog (top-level only; keep blurb short) ───────────────────────────────

GROUPS: list[tuple[str, str, list[CmdRow]]] = [
    (
        "🚀 入门",
        "bright_green",
        [
            CmdRow("quickstart", "环境核验 + 上手向导 (init 同义)", "cockpit quickstart"),
            CmdRow("demo", "5 分钟产品闭环演示", "cockpit demo"),
            CmdRow("help", "本产品地图；help <词> 模糊搜", "cockpit help memory"),
            CmdRow("discover", "发现已安装能力", "cockpit discover"),
            CmdRow("version", "版本信息", "cockpit version"),
            CmdRow("quickstart-check", "环境核验状态快查", "cockpit quickstart-check"),
        ],
    ),
    (
        "📚 研究与知识",
        "cyan",
        [
            CmdRow("research", "深度研究 (create/list/open/publish/...)", 'cockpit research "主题"'),
            CmdRow("import", "导入网页/文档素材", "cockpit import ./note.md"),
            CmdRow("search", "跨源搜索 (本地+BOS)", 'cockpit search "关键词" --all'),
            CmdRow("vault", "L4 Vault 知识库搜索", 'cockpit vault "笔记"'),
            CmdRow("knowledge", "KOS 检索 search/status/stats", "cockpit knowledge search …"),
            CmdRow("memory", "Memory OS 统一记忆控制面", "cockpit memory status --json"),
            CmdRow("brain", "个人数字大脑问答", "cockpit brain …"),
            CmdRow("gbrain", "gbrain 知识库 CLI 委派", "cockpit gbrain search …"),
            CmdRow("kairon", "kairon monorepo 聚合", "cockpit kairon …"),
            CmdRow("daily", "每日研究简报", "cockpit daily"),
            CmdRow("brief", "会话简报", "cockpit brief"),
        ],
    ),
    (
        "🧠 记忆与检索怎么选",
        "magenta",
        [
            CmdRow("memory", "默认记忆入口 (write/recall/forget/consolidate)", "cockpit memory"),
            CmdRow("knowledge", "结构化 KOS 索引检索", "cockpit knowledge search q"),
            CmdRow("vault", "本地笔记/精读最快", 'cockpit vault "q"'),
            CmdRow("search", "跨源聚合", 'cockpit search "q" --all'),
            CmdRow("bos", "任意 BOS URI (含 mos/*)", "cockpit bos resolve bos://memory/mos/status"),
        ],
    ),
    (
        "🛠️ 系统与可观测",
        "blue",
        [
            CmdRow("status", "工作台 / 系统健康", "cockpit status"),
            CmdRow("health", "一键健康检查", "cockpit health --full"),
            CmdRow("product-health", "产品健康度", "cockpit product-health"),
            CmdRow("dashboard", "Web 控制台", "cockpit dashboard"),
            CmdRow("tui", "全屏终端 TUI", "cockpit tui"),
            CmdRow("monitor", "C2G Pipeline 实时大盘", "cockpit monitor"),
            CmdRow("events", "Agora SSE 事件流", "cockpit events"),
            CmdRow("events-watch", "SSE 简便监听", "cockpit events-watch"),
            CmdRow("observe", "Langfuse 可观测入口", "cockpit observe"),
            CmdRow("runtime", "runtime Matrix/Scheduler/KEI", "cockpit runtime …"),
            CmdRow("readiness", "治理 readiness 四卡片", "cockpit readiness"),
            CmdRow("journey", "Journey 状态图校验", "cockpit journey"),
            CmdRow("panorama", "7 维全景可观测", "cockpit panorama"),
            CmdRow("project", "17 项目 4D 体检", "cockpit project inspect"),
        ],
    ),
    (
        "🧠 认知操作系统与主权治理 (V3.0 ADR-0195~0203)",
        "bright_cyan",
        [
            CmdRow("intent", "🧠 意图解构与工程规格编译器 (ADR-0195)", 'cockpit intent "卫健委立项方案"'),
            CmdRow("challenge", "⚡️ 影子红蓝对抗审查与自动打补丁 (ADR-0196)", "cockpit challenge 方案.md --auto-patch"),
            CmdRow("cartridge", "👁️ 领域卡带打包与沙箱运行 (ADR-0203)", "cockpit cartridge list"),
            CmdRow("fabric", "🧑‍💻 主权混合算力与 KV 缓存快照 (ADR-0197)", "cockpit fabric inspect"),
            CmdRow("cell", "🤖 AGE-v2 动态 Agent Cell", "cockpit cell plan"),
        ],
    ),
    (
        "⚖️ 治理与 GaC",
        "yellow",
        [
            CmdRow("omo", "OMO debt/state/governance/lint", "cockpit omo state sync"),
            CmdRow("debt", "债务评分 list/summary/score", "cockpit debt list"),
            CmdRow("gac", "GaC 健康检查", "cockpit gac"),
            CmdRow("governance", "arcnode 校准/审计/巡检", "cockpit governance …"),
            CmdRow("audit", "六维审计", "cockpit audit"),
            CmdRow("cards", "CARDS 状态", "cockpit cards"),
            CmdRow("context", "Phase/CARDS/约束上下文", "cockpit context"),
            CmdRow("mof", "MOF 元模型 CLI", "cockpit mof …"),
            CmdRow("bdsk", "虚拟董事会 4角辩论", "cockpit bdsk debate 主题"),
            CmdRow("kems", "KEMS 域治理", "cockpit kems status"),
            CmdRow("agent-workflow", "Agent 治理流程 (agent 同义)", "cockpit agent-workflow status"),
        ],
    ),
    (
        "🤖 Agent / 战略 / 协作",
        "bright_magenta",
        [
            CmdRow("agent-onboard", "Agent 入职 checklist", "cockpit agent-onboard"),
            CmdRow("agent-runtime", "任务执行 / HTTP server", "cockpit agent-runtime …"),
            CmdRow("swarm", "多 agent 活动监控", "cockpit swarm"),
            CmdRow("compass", "C2G 战略罗盘", "cockpit compass"),
            CmdRow("iterate", "C2G 双擎迭代", "cockpit iterate …"),
            CmdRow("c2g", "战略 status/pipeline", "cockpit c2g status"),
            CmdRow("wave2", "预测治理面板", "cockpit wave2"),
            CmdRow("workflow", "工作流编排 MetaOS/ecos", "cockpit workflow …"),
            CmdRow("channels", "External channels 清单", "cockpit channels"),
        ],
    ),
    (
        "🔌 总线 / 项目入口",
        "bright_blue",
        [
            CmdRow("bos", "BOS URI 列表/解析/读取", "cockpit bos list"),
            CmdRow("bos-capability", "Toolbox 外部能力", "cockpit bos-capability …"),
            CmdRow("bos-inbox", "Inbox 多源神经网", "cockpit bos-inbox status"),
            CmdRow("agora", "Agora 网关 CLI 委派", "cockpit agora …"),
            CmdRow("mcp", "MCP server / 列工具", "cockpit mcp --list"),
            CmdRow("bus", "Omni-Bus 三平面", "cockpit bus …"),
            CmdRow("mesh", "omlx 算力网格", "cockpit mesh …"),
            CmdRow("compute", "LLM 网关 aetherforge", "cockpit compute …"),
            CmdRow("code", "代码库分析 codeanalyze", "cockpit code analyze"),
            CmdRow("family-hub", "家庭数字枢纽", "cockpit family-hub …"),
        ],
    ),
    (
        "🌿 生活场景",
        "green",
        [
            CmdRow("gongwen", "公文写作门户", "cockpit gongwen"),
            CmdRow("finance", "个人财务门户", "cockpit finance"),
            CmdRow("scenario", "radar/assistant/health", "cockpit scenario …"),
            CmdRow("profile", "身份档案 L4", "cockpit profile"),
            CmdRow("domains", "L4 域列表", "cockpit domains"),
            CmdRow("skill", "L4 定时技能", "cockpit skill …"),
        ],
    ),
    (
        "⚙️ 数据与契约",
        "white",
        [
            CmdRow("data", "index / types / gc", "cockpit data index"),
            CmdRow("contracts", "validate / export", "cockpit contracts validate"),
            CmdRow("dashboard", "Web Dashboard", "cockpit dashboard"),
        ],
    ),
]


SCENARIOS: list[tuple[str, str]] = [
    ("新用户", "cockpit quickstart → cockpit demo → cockpit help"),
    ("日常研究", 'cockpit research "主题" → cockpit daily'),
    ("统一记忆", 'source bin/memory-os-env.sh → cockpit memory status → cockpit memory recall "…"'),
    ("知识检索", 'cockpit knowledge search "q" · cockpit vault "q" · cockpit search "q" --all'),
    ("治理巡检", "cockpit gac · cockpit omo state sync · cockpit audit"),
    ("Agent 协作", "cockpit agent-onboard · cockpit swarm · cockpit agent status"),
    ("BOS 调用", "cockpit bos resolve bos://memory/mos/status · cockpit bos list"),
    ("Web 控制台", "cockpit dashboard → http://localhost:8090/overview"),
]


DOCS: list[tuple[str, str]] = [
    ("架构导航", "docs/architecture/memory-os.md · docs/SYSTEM-INDEX.md"),
    ("Memory OS 运维", ".omo/standards/memory-os-ops.md · docs/operations/memory-os-neo4j-local.md"),
    ("Agent 技能", ".agents/skills/memory-recall · bos-service-discovery"),
    ("BOS 注册表", "projects/agora/etc/bos-services.yaml"),
]


def _group_table(title: str, style: str, rows: list[CmdRow]) -> Table:
    t = Table(
        title=f"[{style}]{title}[/{style}]",
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style=f"bold {style}",
        pad_edge=False,
        expand=True,
        title_justify="left",
    )
    t.add_column("命令", style="bold cyan", no_wrap=True, min_width=14)
    t.add_column("说明", style="white", ratio=2)
    t.add_column("示例", style="dim", ratio=2)
    for r in rows:
        t.add_row(r.name, r.blurb, r.example or f"cockpit {r.name} --help")
    return t


def render_product_map(console: Console) -> None:
    """Full product map for `cockpit help`."""
    header = Text.from_markup(
        "[bold white]Workspace · Cockpit L3 统一入口[/]\n"
        "[dim]5+4+1+1 架构 · 研究 / 记忆 / 治理 / Agent 一站式 CLI[/]\n"
        "[dim]提示: [cyan]cockpit help <关键词>[/] 搜命令·MCP·BOS · "
        "[cyan]cockpit <cmd> --help[/] 子命令详情[/]"
    )
    console.print(
        Panel(
            header,
            title="[bold bright_cyan]🧭 Cockpit 产品地图[/]",
            border_style="bright_cyan",
            padding=(1, 2),
        )
    )

    for title, style, rows in GROUPS:
        console.print(_group_table(title, style, rows))
        console.print()

    # Scenarios
    scen = Table(box=box.ROUNDED, title="[bold yellow]💡 典型场景[/]", title_justify="left", expand=True)
    scen.add_column("场景", style="bold yellow", width=12)
    scen.add_column("推荐路径", style="white")
    for name, path in SCENARIOS:
        scen.add_row(name, path)
    console.print(scen)
    console.print()

    # Journey
    journey = (
        "[bold]研究旅程[/]  import → research → open → ask → publish → dossier → daily\n"
        "[bold]记忆旅程[/]  memory-os-env → neo4j-up → memory status → recall/write → bos resolve\n"
        "[bold]治理旅程[/]  agent-workflow bootstrap → start → claim → verify → closeout"
    )
    console.print(Panel(journey, title="[bold]🔄 用户旅程[/]", border_style="dim", padding=(0, 2)))

    docs = Table(box=box.SIMPLE, show_header=False, expand=True, pad_edge=False)
    docs.add_column(style="cyan", width=14)
    docs.add_column(style="dim")
    for k, v in DOCS:
        docs.add_row(k, v)
    console.print(Panel(docs, title="[bold]📖 文档指针[/]", border_style="blue", padding=(0, 1)))

    console.print(
        "[dim]Web: [link=http://localhost:8090/overview]http://localhost:8090/overview[/] · "
        "Dashboard: [cyan]cockpit dashboard[/] · "
        "环境: [cyan]source bin/memory-os-env.sh[/][/]\n"
    )


def render_compact_help(console: Console) -> None:
    """Shorter view for `cockpit --help` (avoid 70-cmd wall of text)."""
    console.print(
        Panel.fit(
            "[bold bright_cyan]cockpit[/] — Workspace L3 统一入口\n\n"
            "[bold]先看地图[/]  [cyan]cockpit help[/]\n"
            "[bold]搜能力[/]    [cyan]cockpit help memory[/] · [cyan]cockpit help bos[/]\n"
            "[bold]记忆[/]      [cyan]cockpit memory[/] · [cyan]cockpit memory status --json[/]\n"
            '[bold]研究[/]      [cyan]cockpit research "主题"[/] · [cyan]cockpit demo[/]\n'
            "[bold]治理[/]      [cyan]cockpit gac[/] · [cyan]cockpit agent status[/]\n"
            "[bold]BOS[/]       [cyan]cockpit bos resolve bos://memory/mos/status[/]\n"
            "[bold]上手[/]      [cyan]cockpit quickstart[/]\n\n"
            "[dim]完整分组目录 → cockpit help · 子命令详情 → cockpit <cmd> --help[/]",
            border_style="bright_cyan",
            title="[bold]🚀 快速入口[/]",
        )
    )
    # mini group list
    t = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold cyan", expand=True)
    t.add_column("分组", style="bold")
    t.add_column("代表命令", style="cyan")
    for title, _style, rows in GROUPS:
        names = " · ".join(r.name for r in rows[:6])
        if len(rows) > 6:
            names += f" · …(+{len(rows) - 6})"
        t.add_row(title, names)
    console.print(t)
    console.print("\n[dim]用法: cockpit [-h] [--output text|json|tui|markdown] <command> …[/]\n")


def all_command_names() -> list[str]:
    return sorted({r.name for _, _, rows in GROUPS for r in rows})


def render_discover_map(console: Console) -> None:
    """Command map for `cockpit discover` — same GROUPS SSOT as `cockpit help`."""
    n = len(all_command_names())
    g = len(GROUPS)
    console.print(f"[bold]命令地图[/] ([cyan]{n}[/] 个命令 · [cyan]{g}[/] 组 · 与 [cyan]cockpit help[/] 同源)")
    t = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold green", expand=True, pad_edge=False)
    t.add_column("分组", style="bold green", min_width=16)
    t.add_column("命令", style="cyan")
    for title, _style, rows in GROUPS:
        names = " · ".join(r.name for r in rows)
        t.add_row(title, names)
    console.print(t)
    # Explicit Memory OS callout for discover consistency with help
    console.print(
        "\n[bold magenta]🧠 Memory OS[/]  "
        "[cyan]cockpit memory[/] · [cyan]status/recall/write/forget/consolidate[/] · "
        "[dim]docs/architecture/memory-os.md[/]"
    )
    console.print(
        "[dim]完整说明/场景: [cyan]cockpit help[/] · 搜能力: [cyan]cockpit help memory[/] · "
        "子命令: [cyan]cockpit <cmd> --help[/][/dim]"
    )


def top_level_cli_names_from_source(cli_path: Path | None = None) -> set[str]:
    """Parse cli.py for `sub.add_parser("name"` top-level registrations.

    Parser 注册已抽至 `_subcommands.py` (T6-10 god-module split), 故同时
    扫描该模块; 显式传入 cli_path 时仅解析指定文件 (保持参数语义)。
    """
    import re

    root = Path(__file__).resolve().parent.parent
    paths = [cli_path or root / "cli.py"]
    if cli_path is None:
        subcmd_path = root / "_subcommands.py"
        if subcmd_path.exists():
            paths.append(subcmd_path)
    names: set[str] = set()
    for p in paths:
        text = p.read_text(encoding="utf-8")
        names.update(re.findall(r'\bsub\.add_parser\(\s*"([^"]+)"', text))
    return names
