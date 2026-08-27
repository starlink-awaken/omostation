"""CLI commands: status"""

import click
from rich.table import Table

from codeanalyze.commands.common import console  # type: ignore[import-not-found]
from codeanalyze.core.registry import build_registry  # type: ignore[import-not-found]


@click.command()
def status() -> None:
    """显示已安装/可用的分析工具。"""
    from rich.panel import Panel

    console.print(Panel.fit("[bold cyan]🔍 工具可用性状态[/]", border_style="cyan"))

    registry = build_registry()
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("工具", style="white")
    table.add_column("状态", width=10)
    table.add_column("版本")
    table.add_column("说明")

    for name, tool in sorted(registry.tools.items(), key=lambda x: x[0]):
        status_icon = "✅" if tool.available else "❌"
        version = tool.version or "-"
        table.add_row(name, status_icon, version, tool.description)

    console.print(table)

    available = sum(1 for t in registry.tools.values() if t.available)
    console.print(f"\n{'─' * 50}")
    gitnexus_tool = registry.tools.get("gitnexus")
    path_str = gitnexus_tool.path if gitnexus_tool and gitnexus_tool.path else "(N/A)"
    console.print(f"可用: {available}/{len(registry.tools)} | 路径: {path_str}")
    if not available:
        console.print(
            "[yellow]💡 建议安装:\n"
            "  pip install graphifyy docling docling-graph unstructured\n"
            "  npm install -g gitnexus\n"
            "  pip install marker-pdf[/]"
        )
