"""CLI commands: cgc (CodeGraphContext)"""

import json as _json
from pathlib import Path

import click

from codeanalyze.analyzers import cgc  # type: ignore[import-not-found]
from codeanalyze.commands.common import console  # type: ignore[import-not-found]
from codeanalyze.core.registry import build_registry  # type: ignore[import-not-found]


@click.group(name="cgc")
def cgc_group() -> None:
    """CodeGraphContext 语义属性图操作。

    使用 tree-sitter 和 SCIP 构建支持大语言模型精确查询的代码知识图谱。
    """
    pass


@cgc_group.command("init")
@click.argument("path", default=".")
def cgc_init(path: str) -> None:
    """初始化或更新代码库的语义图。"""
    reg = build_registry()
    tool = reg.tools.get("codegraphcontext")

    if not tool or not tool.available:
        console.print("[red]❌ codegraphcontext 未安装. 安装: pip install codegraphcontext[/]")
        return

    root = Path(path).resolve()
    console.print(f"[cyan]🔄 正在索引代码库:[/] {root.name}")

    with console.status("[dim]构建/更新语义图中...[/]"):
        result = cgc.init_graph(str(root))

    if not result.success:
        console.print(f"[red]❌ 索引失败: {result.error}[/]")
        return

    console.print("[green]✅ 索引完成![/]")
    if isinstance(result.data, str):
        console.print(result.data)


@cgc_group.command("query")
@click.argument("query_str")
@click.argument("path", default=".")
def cgc_query(query_str: str, path: str) -> None:
    """执行 Cypher/Kuzu 查询获取代码关系。"""
    result = cgc.query(query_str, path)

    if not result.success:
        console.print(f"[red]❌ 查询失败: {result.error}[/]")
        return

    console.print(
        _json.dumps(
            result.data,
            ensure_ascii=False,
            indent=2,
        )
    )
