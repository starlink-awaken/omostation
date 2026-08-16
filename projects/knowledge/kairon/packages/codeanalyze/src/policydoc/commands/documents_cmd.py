"""policydoc: documents"""

from pathlib import Path

import click
from codeanalyze.documents.official import (  # type: ignore[import-not-found]
    analyze_policy_directory,
    format_policy_graph_report,
)
from rich.panel import Panel

from policydoc.cli import _validate_path, console  # type: ignore[import-not-found]


@click.command()
@click.argument("path", default=".")
@click.option("--output", "-o", default=None, help="报告输出路径")
@click.option("--levels", is_flag=True, help="按政策层级分类展示")
def documents(path, output, levels):
    """分析公文/政策文档项目（文号/层级/关系）。"""
    root = Path(_validate_path(path)).resolve()
    console.print(Panel.fit(f"[bold cyan]📜 公文/政策分析: {root.name}[/]", border_style="cyan"))

    if not root.is_dir():
        console.print("[red]❌ 路径不是目录[/]")
        return

    policy_files = list(root.rglob("*.pdf")) + list(root.rglob("*.docx")) + list(root.rglob("*.doc"))
    if not policy_files:
        console.print("[yellow]⚠️ 未找到政策文档（PDF/DOCX/DOC）[/]")
        return
    console.print(f"  📄 发现 {len(policy_files)} 个政策文档文件")

    graph = analyze_policy_directory(str(root))
    console.print(graph.summary)

    if levels and "房山区级" in graph.level_groups:
        console.print("\n[bold]按层级分布:[/]")
        for level in ["国家级", "部委级", "北京市级", "房山区级", "其他"]:
            docs = graph.level_groups.get(level, [])
            if docs:
                console.print(f"\n  [underline]{level}[/] ({len(docs)})")

    report_content = format_policy_graph_report(graph)
    target = output or str(root / "policydoc-policy-report.md")
    Path(target).write_text(report_content, encoding="utf-8")
    console.print(f"\n[green]✅ 报告已写入: {target}[/]")
