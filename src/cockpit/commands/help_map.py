"""Cockpit CLI product map — `cockpit help` / `--help` 的产品地图 (Phase A3 SSOT 化).

SSOT 原则 (Phase A3 修复):
  命令清单不再内联维护, 运行时从 ``commands.registry.COMMAND_CATALOG`` 按 category
  分组生成 (含 Phase B 薄委派组, 经 ``delegation.ensure_delegated_catalog`` 并入);
  分组顺序/颜色来自 ``registry.CATEGORY_GROUPS``。

  本文件只保留两类人工内容 (引导文案, 非数据源):
    · ``GUIDE_SECTIONS``  — 跨命令选择引导 ("记忆与检索怎么选" 等)
    · ``BLURB_OVERRIDES`` — 个别命令的口语化一句简介 (fallback 到 catalog summary)
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


# ── 人工引导内容 (不是命令数据源) ─────────────────────────────────────────────

# 个别命令的口语化覆写 (fallback: catalog summary)
BLURB_OVERRIDES: dict[str, str] = {
    "research": "深度研究 (create/list/open/publish/…)",
    "quickstart": "环境核验 + 上手向导 (init 同义)",
    "agent-workflow": "Agent 治理流程 (agent 同义)",
}

# 跨命令选择引导段 (原内联分组的引导语义, 保留为静态段)
GUIDE_SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "🧠 记忆与检索怎么选",
        [
            ("memory", "默认记忆入口 (write/recall/forget/consolidate) — cockpit memory"),
            ("knowledge", "结构化 KOS 索引检索 — cockpit knowledge search q"),
            ("vault", "本地笔记/精读最快 — cockpit vault \"q\""),
            ("search", "跨源聚合 — cockpit search \"q\" --all"),
            ("bos", "任意 BOS URI (含 mos/*) — cockpit bos resolve bos://memory/mos/status"),
        ],
    ),
]

# 引导段引用的命令必须存在于 catalog (test_help_map_ssot 校验, 防悬空)
GUIDE_REFERENCED_COMMANDS: tuple[str, ...] = (
    "memory", "knowledge", "vault", "search", "bos",
)


# ── SSOT: 从 COMMAND_CATALOG 生成分组 ────────────────────────────────────────

def _build_groups() -> list[tuple[str, str, list[CmdRow]]]:
    from cockpit.commands.delegation import category_color, category_order, ensure_delegated_catalog
    from cockpit.commands.registry import COMMAND_CATALOG

    ensure_delegated_catalog()  # 并入 Phase B 薄委派组 (幂等)

    by_category: dict[str, list] = {}
    for meta in COMMAND_CATALOG.values():
        by_category.setdefault(meta.category, []).append(meta)

    groups: list[tuple[str, str, list[CmdRow]]] = []
    for category in sorted(by_category, key=category_order):
        metas = sorted(by_category[category], key=lambda m: m.name)
        rows = [
            CmdRow(
                name=m.name,
                blurb=BLURB_OVERRIDES.get(m.name, m.summary),
                example=m.example,
            )
            for m in metas
        ]
        groups.append((category, category_color(category), rows))
    return groups


GROUPS: list[tuple[str, str, list[CmdRow]]] = _build_groups()


def rebuild_groups() -> None:
    """测试/热更新用: 从 catalog 重建 GROUPS."""
    global GROUPS
    GROUPS = _build_groups()


SCENARIOS: list[tuple[str, str]] = [
    ("新用户", "cockpit quickstart → cockpit demo → cockpit help"),
    ("日常研究", 'cockpit research "主题" → cockpit daily'),
    ("统一记忆", 'source bin/memory-os-env.sh → cockpit memory status → cockpit memory recall "…"'),
    ("知识检索", 'cockpit knowledge search "q" · cockpit vault "q" · cockpit search "q" --all'),
    ("治理巡检", "cockpit gac · cockpit omo state sync · cockpit audit"),
    ("链路编排", "cockpit chain list → cockpit chain run governance-patrol --dry-run"),
    ("Agent 协作", "cockpit agent-onboard · cockpit swarm · cockpit agent status"),
    ("命令审查", "cockpit command-audit lint · cockpit command-audit report"),
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

    # 跨命令引导段 (SSOT: 引用校验由 test_help_map_ssot 保障)
    for section_title, pairs in GUIDE_SECTIONS:
        t = Table(
            title=f"[bold magenta]{section_title}[/]",
            box=box.SIMPLE_HEAD,
            show_header=False,
            expand=True,
            pad_edge=False,
            title_justify="left",
        )
        t.add_column("命令", style="cyan", no_wrap=True, min_width=14)
        t.add_column("什么时候用", style="white", ratio=3)
        for name, guidance in pairs:
            t.add_row(name, guidance)
        console.print(t)
        console.print()

    # Scenarios
    scen = Table(box=box.ROUNDED, title="[bold yellow]💡 典型场景[/]", title_justify="left", expand=True)
    scen.add_column("场景", style="bold yellow", width=12)
    scen.add_column("推荐路径", style="white")
    for name, path in SCENARIOS:
        scen.add_row(name, path)
    console.print(scen)
    console.print()

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
    """Shorter view for `cockpit --help` (avoid cmd wall of text)."""
    console.print(
        Panel.fit(
            "[bold bright_cyan]cockpit[/] — Workspace L3 统一入口\n\n"
            "[bold]先看地图[/]  [cyan]cockpit help[/]\n"
            "[bold]搜能力[/]    [cyan]cockpit help memory[/] · [cyan]cockpit help bos[/]\n"
            "[bold]记忆[/]      [cyan]cockpit memory[/] · [cyan]cockpit memory status --json[/]\n"
            '[bold]研究[/]      [cyan]cockpit research "主题"[/] · [cyan]cockpit demo[/]\n'
            "[bold]治理[/]      [cyan]cockpit gac[/] · [cyan]cockpit agent status[/]\n"
            "[bold]链路[/]      [cyan]cockpit chain list[/] · [cyan]cockpit chain run <id> --dry-run[/]\n"
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
    console.print(f"[bold]命令地图[/] ([cyan]{n}[/] 个命令 · [cyan]{g}[/] 组 · 与 [cyan]cockpit help[/] 同源 (COMMAND_CATALOG))")
    t = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold green", expand=True, pad_edge=False)
    t.add_column("分组", style="bold green", min_width=16)
    t.add_column("命令", style="cyan")
    for title, _style, rows in GROUPS:
        names = " · ".join(r.name for r in rows)
        t.add_row(title, names)
    console.print(t)
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
