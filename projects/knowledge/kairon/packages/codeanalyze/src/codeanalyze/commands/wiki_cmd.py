"""CLI commands: wiki"""

from pathlib import Path

import click
from rich.panel import Panel

from codeanalyze.analyzers import gitnexus, graphify  # type: ignore[import-not-found]
from codeanalyze.commands.common import _validate_path, console  # type: ignore[import-not-found]
from codeanalyze.core.registry import build_registry  # type: ignore[import-not-found]
from codeanalyze.documents.deepwiki import (  # type: ignore[import-not-found]
    check_deepwiki_open,
    generate_wiki_from_analysis,
    trigger_api_wiki_generation,
)


@click.command()
@click.argument("path", default=".")
@click.option("--output", "-o", default=None, help="Wiki 输出路径")
@click.option("--api", is_flag=True, help="强制使用 DeepWiki-Open API（需设置 DEEPWIKI_OPEN_URL）")
def wiki(path: str, output: str | None, api: bool) -> None:
    """生成项目 Wiki 文档。

    优先使用 DeepWiki-Open（如已部署），否则基于 Graphify/GitNexus 分析结果
    生成静态 Wiki Markdown。
    """
    reg = build_registry()
    root = _validate_path(path)
    output_path = Path(output) if output else root / "codeanalyze-wiki.md"

    console.print(Panel.fit(f"[bold cyan]📖 生成项目 Wiki: {root.name}[/]", border_style="cyan"))

    # 检查 DeepWiki-Open
    dw_info = check_deepwiki_open()

    if dw_info["available"] and dw_info["mode"] == "api" and api:
        console.print("[green]✅ DeepWiki-Open API 可用[/]")
        console.print("[bold cyan]▶ 调用 API 生成 Wiki...[/]")
        repo_url = f"file://{root}" if not root.name.startswith("http") else str(root)
        result = trigger_api_wiki_generation(repo_url, str(output_path.parent))
        if result.get("status") == "ok":
            console.print(f"[green]✅ Wiki 已生成: {result['output']}[/]")
            return
        else:
            console.print(f"[yellow]⚠️ API 调用失败: {result.get('error', 'unknown')}[/]")
            console.print("[dim]降级到本地生成模式...[/]")
    elif dw_info.get("available"):
        console.print(f"[dim]DeepWiki-Open 已检测到 ({dw_info['mode']}), 使用 --api 调用[/]")

    # 本地生成模式（默认）
    console.print("\n[bold cyan]▶ 收集分析数据...[/]")
    g_tool = reg.tools.get("graphify")
    gn_tool = reg.tools.get("gitnexus")
    g_result = graphify.analyze(str(root), g_tool) if g_tool else {"error": "graphify not installed"}
    gn_result = gitnexus.analyze(str(root), gn_tool) if gn_tool else {"status": "unavailable"}

    if g_result.get("error") and g_result["error"] != "graphify not installed":
        console.print(f"  [yellow]Graphify: {g_result['error']}[/]")

    console.print("  [green]✅ 数据收集完成[/]")

    console.print("\n[bold cyan]▶ 生成 Wiki 文档...[/]")
    wiki_content = generate_wiki_from_analysis(
        str(root),
        graphify_result=g_result,
        gitnexus_result=gn_result,
    )
    output_path.write_text(wiki_content, encoding="utf-8")
    console.print(f"[green]✅ Wiki 已生成: {output_path}[/]")

    console.print(
        Panel.fit(
            "[bold green]✅ Wiki 生成完成[/]\n"
            f"输出: {output_path}\n"
            "💡 安装 DeepWiki-Open 可获取 AI 增强版文档:\n"
            "   git clone https://github.com/AsyncFuncAI/deepwiki-open\n"
            "   cd deepwiki-open && docker-compose up\n"
            "   然后: export DEEPWIKI_OPEN_URL=http://localhost:3000\n"
            "   codeanalyze wiki --api .",
            border_style="green",
        )
    )
