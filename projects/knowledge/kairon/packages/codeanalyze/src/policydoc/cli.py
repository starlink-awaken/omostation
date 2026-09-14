"""policydoc CLI commands (click)."""

from pathlib import Path

import click
from rich.console import Console

console = Console()


def _validate_path(path: str) -> str:
    root = Path(path).resolve()
    if not root.exists():
        raise click.BadParameter(f"path does not exist: {path}")
    return str(root)


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """公文/政策文档分析工具。

    基于 codeanalyze 引擎，专注于政策文档的：
    元数据提取、层级归类、知识图谱构建和交叉审计。
    """


# Register commands
from policydoc.commands import load_commands  # type: ignore[import-not-found]

load_commands(cli)

if __name__ == "__main__":
    cli()
