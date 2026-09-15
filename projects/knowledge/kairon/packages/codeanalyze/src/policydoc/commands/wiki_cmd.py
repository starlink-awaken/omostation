"""policydoc: wiki — 政策文档 Wiki 生成"""

from pathlib import Path

import click
from codeanalyze.core.registry import build_registry  # type: ignore[import-not-found]
from codeanalyze.documents.deepwiki import (  # type: ignore[import-not-found]
    check_deepwiki_open,
    generate_wiki_from_analysis,
    trigger_api_wiki_generation,
)
from rich.panel import Panel

from policydoc.cli import console  # type: ignore[import-not-found]


def _validate_path(path: str) -> Path:
    root = Path(path).resolve()
    if not root.exists():
        raise click.BadParameter(f"path does not exist: {path}")
    return root


@click.command()
@click.argument("path", default=".")
@click.option("--output", "-o", default=None, help="Wiki 输出路径")
@click.option("--api", is_flag=True, help="使用 DeepWiki-Open API（需设置 DEEPWIKI_OPEN_URL）")
def wiki(path: str, output: str | None, api: bool):
    """生成政策文档项目的 Wiki。

    优先使用 DeepWiki-Open（如已部署），否则基于文档分析结果
    生成静态 Wiki Markdown。
    """
    root = _validate_path(path)
    output_path = Path(output) if output else root / "policydoc-wiki.md"

    console.print(Panel.fit(f"[bold cyan]📖 生成政策文档 Wiki: {root.name}[/]", border_style="cyan"))

    dw_info = check_deepwiki_open()
    if dw_info["available"] and dw_info["mode"] == "api" and api:
        console.print("[green]✅ DeepWiki-Open API 可用[/]")
        repo_url = f"file://{root}"
        result = trigger_api_wiki_generation(repo_url, str(output_path.parent))
        if result.get("status") == "ok":
            console.print(f"[green]✅ Wiki 已生成: {result['output']}[/]")
            return
        console.print(f"[yellow]⚠️ API 失败: {result.get('error', 'unknown')}[/]")

    # 本地生成模式
    console.print("\n[bold cyan]▶ 收集分析数据...[/]")
    reg = build_registry()
    g_result = {}
    if reg.tools.get("graphify", None):
        from codeanalyze.analyzers.graphify import analyze  # type: ignore[import-not-found]

        g_result = analyze(str(root), reg.tools["graphify"])

    if g_result.get("error"):
        console.print(f"  [yellow]Graphify: {g_result['error']}[/]")

    console.print("  [green]✅ 数据收集完成[/]")
    console.print("\n[bold cyan]▶ 生成 Wiki 文档...[/]")
    wiki_content = generate_wiki_from_analysis(str(root), graphify_result=g_result)
    output_path.write_text(wiki_content, encoding="utf-8")
    console.print(f"[green]✅ Wiki 已生成: {output_path}[/]")
