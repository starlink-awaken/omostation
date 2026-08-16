"""CLI commands: install"""

import click
from rich.table import Table

from codeanalyze.commands.common import _INSTALL_GUIDE, console  # type: ignore[import-not-found]
from codeanalyze.core.registry import build_registry  # type: ignore[import-not-found]


@click.command()
@click.option("--all", "-a", "all_flag", is_flag=True, help="安装全部可选依赖")
@click.option("--minimal", is_flag=True, help="仅安装核心依赖")
@click.option("--code", is_flag=True, help="仅安装代码分析工具")
@click.option("--docs", is_flag=True, help="仅安装文档分析工具")
def install(all_flag: bool, minimal: bool, code: bool, docs: bool) -> None:
    """一键安装可选分析工具。

    探测缺失工具并打印安装命令。不会自动运行 pip/npm，
    让用户自行选择装哪些。
    """
    reg = build_registry()

    mode = "all" if all_flag else "code" if code else "docs" if docs else "missing"
    if minimal:
        mode = "minimal"

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("工具", style="white")
    table.add_column("状态", width=10)
    table.add_column("安装命令")
    table.add_column("说明")

    for name, (cmd, desc) in sorted(_INSTALL_GUIDE.items()):
        tool = reg.tools.get(name)
        installed = tool.available if tool else False
        show = (
            mode == "all"
            or mode == "missing"
            and not installed
            or mode == "code"
            and name in ("graphify", "gitnexus")
            or mode == "docs"
            and name in ("docling", "marker", "mineru", "unstructured")
        )
        if not show and mode not in ("all", "missing", "minimal"):
            continue
        if mode == "minimal" and name not in ("graphify", "docling"):
            continue
        icon = "✅" if installed else "❌"
        table.add_row(name, icon, cmd, desc)

    console.print(table)
    console.print("\n复制需要的命令到终端执行。codeanalyze 会自动检测已安装的工具。")
