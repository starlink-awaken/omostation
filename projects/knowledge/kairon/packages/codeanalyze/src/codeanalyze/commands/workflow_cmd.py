"""CLI commands: workflow"""

from pathlib import Path

import click

from codeanalyze.commands.common import console  # type: ignore[import-not-found]
from codeanalyze.workflows import analyze_impact, generate_onboarding_context  # type: ignore[import-not-found]


@click.group(name="workflow")
def workflow_group() -> None:
    """高级分析工作流 (组合多种工具)。"""
    pass


@workflow_group.command("onboarding")
@click.argument("path", default=".")
@click.option("--output", "-o", help="输出目录")
def onboarding(path: str, output: str | None) -> None:
    """为 AI 构建项目全貌上下文。"""
    root = Path(path).resolve()
    console.print(f"[cyan]🚀 正在为 {root.name} 构建 Onboarding 上下文...[/]")

    with console.status("[dim]执行 repomix 与入口提取...[/]"):
        res = generate_onboarding_context(path=str(root), output_dir=output)

    if res.get("error"):
        console.print(f"[red]❌ 工作流失败: {res['error']}[/]")
        return

    console.print("[green]✅ 上下文构建完成![/]")
    console.print(f"  入口点: {len(res['entry_points_found'])} 个")
    console.print(f"  上下文文件: [underline]{res['context_file']}[/]")
    console.print(f"  预估 Tokens: [bold yellow]{res['token_estimate']}[/]")


@workflow_group.command("impact")
@click.argument("symbol")
@click.argument("path", default=".")
@click.option("--lang", "-l", required=True, help="代码语言 (py, js, ts 等)")
def impact(symbol: str, path: str, lang: str) -> None:
    """分析符号的变更影响面。"""
    console.print(f"[cyan]🔍 分析符号 '{symbol}' 的影响面...[/]")

    with console.status("[dim]执行结构化查找与图查询...[/]"):
        res = analyze_impact(symbol_name=symbol, language=lang, path=path)

    console.print("[green]✅ 分析完成![/]")
    console.print(f"  直接使用位置: {res['total_usages_found']} 处 (分布在 {len(res['files_affected'])} 个文件)")

    for usage in res.get("usages", [])[:5]:
        console.print(f"    - [dim]{usage['file']}:{usage['line']}[/] {usage['text']}")
    if len(res.get("usages", [])) > 5:
        console.print("    - ... 更多")

    if "graph_callers" in res:
        console.print(f"  图谱中识别的调用方: {len(res['graph_callers'])}")
