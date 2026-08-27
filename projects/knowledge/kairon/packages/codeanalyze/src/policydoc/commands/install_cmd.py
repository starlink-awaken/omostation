"""policydoc: install — 文档工具安装指南"""

import click
from codeanalyze.core.registry import build_registry  # type: ignore[import-not-found]
from rich.table import Table

from policydoc.cli import console  # type: ignore[import-not-found]

_INSTALL_GUIDE = {
    "docling": ("pip install docling docling-graph", "文档→知识图谱 (IBM)"),
    "marker": ("pip install marker-pdf", "高精度 PDF→Markdown"),
    "mineru": ("pip install mineru", "中文 PDF 解析 (OpenDataLab)"),
    "unstructured": ("pip install unstructured", "文档分块与分区"),
    "graphify": ("pip install graphifyy", "语义知识图谱 (Tree-sitter AST + LLM)"),
}


@click.command()
@click.option("--all", "-a", "all_flag", is_flag=True, help="安装全部可选依赖")
def install(all_flag: bool):
    """显示文档分析工具的安装指南。

    探测缺失工具并打印安装命令。让用户自行选择装哪些。
    """
    reg = build_registry()

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("工具", style="white")
    table.add_column("状态", width=10)
    table.add_column("安装命令")
    table.add_column("说明")

    for name, (cmd, desc) in sorted(_INSTALL_GUIDE.items()):
        tool = reg.tools.get(name)
        installed = tool.available if tool else False
        if not all_flag and installed:
            continue
        icon = "✅" if installed else "❌"
        table.add_row(name, icon, cmd, desc)

    console.print(table)
    console.print("\n复制需要的命令到终端执行。policydoc 会自动检测已安装的工具。")
