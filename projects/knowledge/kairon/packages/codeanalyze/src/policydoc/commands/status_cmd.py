"""policydoc: status"""

import click
from codeanalyze.core.registry import build_registry  # type: ignore[import-not-found]
from rich.panel import Panel
from rich.table import Table

from policydoc.cli import console  # type: ignore[import-not-found]


@click.command()
def status():
    """显示文档分析工具的安装状态。"""
    registry = build_registry()
    doc_tools = ["ripgrep", "graphify", "docling", "docling_graph", "marker", "mineru", "unstructured", "deepwiki_open"]
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("工具", style="white")
    table.add_column("状态", width=10)
    table.add_column("版本")
    table.add_column("说明")

    for name in doc_tools:
        t = registry.tools.get(name)
        if t:
            status_icon = "✅" if t.available else "❌"
            table.add_row(name, status_icon, t.version or "-", t.description)
        else:
            table.add_row(name, "❌", "-", "未检测")

    console.print(Panel.fit("[bold cyan]📜 文档工具可用性状态[/]", border_style="cyan"))
    console.print(table)
    available = sum(1 for n in doc_tools if (t := registry.tools.get(n)) and t.available)
    console.print(f"\n可用: {available}/{len(doc_tools)}")
