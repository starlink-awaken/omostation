"""CLI commands: crg (code-review-graph)"""

import click

from codeanalyze.analyzers import codereviewgraph  # type: ignore[import-not-found]
from codeanalyze.commands.common import _validate_path, console  # type: ignore[import-not-found]
from codeanalyze.core.registry import build_registry  # type: ignore[import-not-found]


@click.group()
def crg() -> None:
    """Tree-sitter 持久化知识图谱 (code-review-graph)。

    基于 Tree-sitter 的代码结构分析工具。
    比 Graphify 更快（零 LLM 成本），自动增量更新。
    """


@crg.command("build")
@click.argument("path", default=".")
def crg_build(path: str) -> None:
    """构建 Tree-sitter 知识图谱（增量构建，不会清空已有数据）。"""
    root = _validate_path(path)
    reg = build_registry()
    crg_tool = reg.tools.get("code_review_graph")
    if not crg_tool or not crg_tool.available:
        console.print("[red]❌ code-review-graph 未安装. 安装: pip install code-review-graph[/]")
        return

    console.print(f"[bold cyan]▶ 构建 Tree-sitter 知识图谱: {root}[/]")
    stats = codereviewgraph.build(str(root))
    if stats.error:
        console.print(f"  [red]❌ {stats.error}[/]")
        return

    console.print("  [green]✅ 构建完成[/]")
    console.print(f"  文件: {stats.total_files} | 节点: {stats.total_nodes} | 边: {stats.total_edges}")


@crg.command("update")
@click.argument("path", default=".")
def crg_update(path: str) -> None:
    """增量更新图谱（仅重分析变化文件）。"""
    root = _validate_path(path)
    console.print(f"[bold cyan]▶ 增量更新: {root}[/]")
    stats = codereviewgraph.update(str(root))
    if stats.error:
        console.print(f"  [red]❌ {stats.error}[/]")
        return

    console.print("  [green]✅ 更新完成[/]")


@crg.command("status")
@click.argument("path", default=".")
def crg_status(path: str) -> None:
    """查看图谱统计信息。"""
    root = _validate_path(path)
    console.print(f"[bold cyan]▶ code-review-graph 状态: {root}[/]")
    stats = codereviewgraph.status(str(root))
    if stats.error:
        console.print(f"  [yellow]{stats.error}[/]")
        return
    console.print(f"  文件: {stats.total_files}")
    console.print(f"  节点: {stats.total_nodes}")
    console.print(f"  边:   {stats.total_edges}")
    db_path = codereviewgraph.get_graph_path(str(root))
    if db_path:
        console.print(f"  数据库: {db_path}")


@crg.command("visualize")
@click.argument("path", default=".")
@click.option("--output", "-o", default=None, help="输出 HTML 路径")
def crg_viz(path: str, output: str | None) -> None:
    """生成交互式 HTML 图谱可视化。"""
    root = _validate_path(path)
    console.print(f"[bold cyan]▶ 生成图谱可视化: {root}[/]")
    target = codereviewgraph.visualise(str(root), output)
    if target:
        console.print(f"  [green]✅ 已生成: {target}[/]")
        console.print(f"  浏览器打开: file://{target}")
    else:
        console.print("  [yellow]⚠️ 可视化生成失败（可能未安装 code-review-graph）[/]")
