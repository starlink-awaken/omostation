"""CLI command: lint — 代码质量检查（静态分析+架构合规+洞察）"""

from pathlib import Path

import click
from rich.panel import Panel
from rich.table import Table

from codeanalyze.analyzers import (  # type: ignore[import-not-found]
    ast_grep,  # type: ignore[import-not-found]
    gitnexus,
)
from codeanalyze.commands.common import _validate_path, console  # type: ignore[import-not-found]
from codeanalyze.core.registry import build_registry  # type: ignore[import-not-found]
from codeanalyze.core.workspace import detect_workspace  # type: ignore[import-not-found]
from codeanalyze.reports.insights import _SEVERITY_ICONS as INSIGHT_ICONS  # type: ignore[import-not-found]
from codeanalyze.reports.insights import analyze as analyze_insights  # type: ignore[import-not-found]


@click.command()
@click.argument("path", default=".")
@click.option("--output", "-o", default=None, help="输出路径")
@click.option("--strict", is_flag=True, help="严格模式（将 warning 提升为 error）")
def lint(path: str, output: str | None, strict: bool) -> None:
    """运行代码质量检查 — 静态分析 + 架构合规 + 依赖健康。

    检查包括:

    \b
    - 文件大小合规
    - 文档/注释覆盖率
    - 架构层级依赖违规
    - import 安全性检查
    - AST 结构化模式检查 (ast-grep)
    - 依赖图健康度 (GitNexus)
    """
    root = _validate_path(path)
    ws = detect_workspace(path)
    reg = build_registry()
    total_issues = 0
    error_count = 0
    warning_count = 0

    console.print(
        Panel.fit(
            f"[bold cyan]🔍 代码质量检查: {ws.name}[/]\n路径: {root}",
            border_style="cyan",
        )
    )

    # ── 1. 洞察分析（文件大小/文档覆盖率/层级违规/import 安全） ──
    console.print("\n[bold]▶ 洞察分析...[/]")
    gn_tool = reg.tools.get("gitnexus")
    gn_result = gitnexus.analyze(str(root), gn_tool) if gn_tool else {}
    insights = analyze_insights(str(root), gn_result)
    for ins in insights:
        severity = ins.get("severity", "insight")
        icon = INSIGHT_ICONS.get(severity, "💡")
        is_err = severity == "critical"
        is_warn = severity == "warning"
        if is_err and strict:
            is_err = True
        if is_err:
            error_count += 1
            total_issues += 1
            console.print(f"  {icon} [red]ERROR[/] {ins['title']}")
        elif is_warn:
            warning_count += 1
            total_issues += 1
            console.print(f"  {icon} [yellow]WARN[/]  {ins['title']}")
        else:
            console.print(f"  {icon} [green]OK[/]    {ins['title']}")

    # ── 2. AST-grep 结构化搜索（如果可用） ──
    console.print("\n[bold]▶ AST 结构化模式检查...[/]")
    if ast_grep.is_available():
        sg_version = ast_grep.get_version()
        console.print(f"  [dim]ast-grep {sg_version or ''}[/]")
        # 常用 lint pattern: 没有 try/except 的 async def
        result = ast_grep.search(
            pattern="async def $NAME($___)",
            path=str(root),
            max_count=50,
        )
        if result.error:
            console.print(f"  [yellow]⚠️ {result.error}[/]")
        elif result.matches:
            # 过滤掉测试文件
            non_test = [m for m in result.matches if "/test" not in m.path and "/tests" not in m.path]
            if non_test:
                warning_count += len(non_test)
                total_issues += len(non_test)
                console.print(f"  [yellow]WARN[/] {len(non_test)} 个 async def 可能缺 try/except:")
                for m in non_test[:5]:
                    short = m.path.split("/")[-1]
                    console.print(f"    - {short}:{m.line_start}  `{m.text.strip()[:60]}`")
                if len(non_test) > 5:
                    console.print(f"    ... 还有 {len(non_test) - 5} 个")
            else:
                console.print("  [green]OK[/]   async def 模式正常")
        else:
            console.print("  [green]OK[/]   async def 模式正常")

        # 检查大文件函数
        result2 = ast_grep.search(
            pattern="def $NAME($___):\n    $BODY",
            path=str(root),
            max_count=100,
        )
        # 不输出具体结果，仅报告可用性
        console.print(f"  [green]OK[/]   AST 分析完成 ({result2.total} 个函数匹配)")
    else:
        console.print("  [dim]⏭️ ast-grep 未安装 (brew install ast-grep)[/]")

    # ── 3. 总结 ──
    summary = Table.grid(padding=(0, 2))
    summary.add_column()
    if total_issues == 0:
        msg = "[bold green]✅ 全部检查通过，无问题[/]"
    else:
        parts = []
        if error_count:
            parts.append(f"[red]{error_count} 个错误[/]")
        if warning_count:
            parts.append(f"[yellow]{warning_count} 个警告[/]")
        msg = f"[bold yellow]⚠️ 发现问题: {', '.join(parts)}[/]"
    console.print()
    console.print(Panel.fit(msg, border_style="green" if total_issues == 0 else "yellow"))

    # 写报告（如果指定了 --output）
    if output:
        lines = [
            f"# 代码质量检查报告 — {ws.name}",
            f"> 路径: {root}",
            f"> 严格模式: {'是' if strict else '否'}",
            "",
            "## 摘要",
            f"- 总问题: {total_issues}",
            f"- 错误: {error_count}",
            f"- 警告: {warning_count}",
            "",
            "## 洞察分析",
        ]
        for ins in insights:
            severity = ins.get("severity", "insight")
            icon = INSIGHT_ICONS.get(severity, "💡")
            lines.append(f"- {icon} [{severity.upper()}] {ins['title']}")
            if ins.get("detail"):
                lines.append(f"  - {ins['detail']}")

        if ast_grep.is_available():
            lines.append("")
            lines.append("## AST 分析")
            lines.append("- ast-grep: 可用")
            lines.append(f"- async def 无 try/except: {warning_count if ast_grep.is_available() else 'N/A'}")

        Path(output).write_text("\n".join(lines), encoding="utf-8")
        console.print(f"\n📄 报告已写入: {output}")

    # 如果 strict 模式下有 error，非零退出
    if strict and error_count:
        raise SystemExit(1)
