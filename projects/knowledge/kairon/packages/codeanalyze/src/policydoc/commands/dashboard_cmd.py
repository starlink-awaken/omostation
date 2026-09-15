"""policydoc: dashboard — 政策文档知识图谱仪表盘"""

import os
import webbrowser
from pathlib import Path

import click
from rich.panel import Panel

from policydoc.cli import console  # type: ignore[import-not-found]


def _validate_path(path: str) -> Path:
    root = Path(path).resolve()
    if not root.exists():
        raise click.BadParameter(f"path does not exist: {path}")
    return root


@click.command()
@click.argument("path", default=".")
@click.option("--port", default=int(os.environ.get("DASHBOARD_PORT", "3456")), help="仪表盘端口")
@click.option("--force", is_flag=True, help="强制生成独立 HTML")
@click.option("--open", "-o", "open_browser", is_flag=True, help="生成后自动在浏览器中打开")
def dashboard(path: str, port: int, force: bool, open_browser: bool = False):
    """启动政策文档知识图谱仪表盘。

    优先使用 Understand Anything 的原生仪表盘。
    降级为基于 D3.js 的独立 HTML 页面。
    """
    root = _validate_path(path)
    console.print(Panel.fit(f"[bold cyan]📊 政策文档知识图谱仪表盘: {root.name}[/]", border_style="cyan"))

    from codeanalyze.reports.understand import (  # type: ignore[import-not-found]
        generate_standalone_html,
        launch_dashboard,
    )

    if not force:
        result = launch_dashboard(str(root), port=port)
        if result["status"] == "launched":
            console.print("  [green]✅ Understand Anything 仪表盘已启动[/]")
            console.print(f"  🌐 {result['url']}")
            return
        elif result["status"] == "graph_available":
            console.print(f"  [yellow]⚠️ {result['error']}[/]")

    console.print("\n[bold cyan]▶ 从 Graphify 图谱生成仪表盘...[/]")
    target = generate_standalone_html(str(root))
    if target:
        console.print(f"  [green]✅ 独立仪表盘已生成: {target}[/]")
        console.print(f"  🌐 file://{target}")
        if open_browser:
            webbrowser.open(f"file://{target}")
    else:
        console.print("  [red]❌ 未找到图谱数据。先运行: policydoc analyze .[/]")
