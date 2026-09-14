"""CLI commands: repomix"""

from pathlib import Path

import click

from codeanalyze.analyzers import repomix  # type: ignore[import-not-found]
from codeanalyze.commands.common import console  # type: ignore[import-not-found]
from codeanalyze.core.registry import build_registry  # type: ignore[import-not-found]


@click.command()
@click.argument("path", default=".")
@click.option("--output", "-o", help="输出路径")
@click.option("--format", "-f", "fmt", default="xml", type=click.Choice(["xml", "markdown", "plain"]), help="输出格式")
@click.option("--include", "-i", multiple=True, help="包含的文件模式 (如 *.py)")
@click.option("--ignore", multiple=True, help="忽略的文件模式")
@click.option("--stats-only", is_flag=True, help="仅显示统计信息，不生成文件")
def pack(
    path: str,
    output: str | None,
    fmt: str,
    include: tuple[str, ...],
    ignore: tuple[str, ...],
    stats_only: bool,
) -> None:
    """将代码库打包为 LLM 友好格式 (repomix)。

    用于将整个项目转换为单个 XML/Markdown 文件喂给大语言模型。
    """
    reg = build_registry()
    tool = reg.tools.get("repomix")

    if not tool or not tool.available:
        console.print("[red]❌ repomix 未安装. 安装: npm install -g repomix 或使用 npx[/]")
        return

    root = Path(path).resolve()
    console.print(f"[cyan]📦 打包代码库:[/] {root.name}")

    if stats_only:
        console.print("[dim]统计文件中...[/]")
        stats = repomix.get_stats(str(root))
        if stats.get("error"):
            console.print(f"[red]❌ 统计失败: {stats['error']}[/]")
            return

        console.print(f"  文件数: [bold]{stats['file_count']}[/]")
        console.print(f"  Token 估算: [bold yellow]{stats['token_count']}[/]")
        console.print(f"  耗时: {stats['elapsed_ms']}ms")
        return

    with console.status("[dim]正在打包...[/]"):
        result = repomix.pack(
            path=str(root),
            output=output,
            fmt=fmt,
            include=list(include) if include else None,
            ignore=list(ignore) if ignore else None,
        )

    if result.error:
        console.print(f"[red]❌ 打包失败: {result.error}[/]")
        return

    console.print("[green]✅ 打包成功![/]")
    console.print(f"  输出文件: [underline]{result.output_path}[/]")
    console.print(f"  文件数: [bold]{result.file_count}[/]")
    console.print(f"  Token 估算: [bold yellow]{result.token_count}[/]")
    console.print(f"  大小: {result.char_count / 1024 / 1024:.2f} MB")
    console.print(f"  耗时: {result.elapsed_ms}ms")
