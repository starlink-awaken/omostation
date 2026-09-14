"""codeanalyze CLI — 统一代码与文档分析入口

命令实现已拆分到 commands/ 目录。
"""

import sys

import click
from rich.console import Console

from codeanalyze import __version__  # type: ignore[import-not-found]

console = Console()


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """统一代码与文档分析工具箱。

    将 Graphify、GitNexus、Serena、Docling 等工具
    统一到一个命令入口，支持代码和文档的结构化分析。
    """


# 注册所有命令（按顺序控制 help 显示顺序）
from codeanalyze.commands import register_commands  # type: ignore[import-not-found]

register_commands(cli)

if __name__ == "__main__":
    print("⚠️ CodeAnalyze 独立 CLI 已弃用，请使用 cockpit 替代", file=sys.stderr)
    cli()
