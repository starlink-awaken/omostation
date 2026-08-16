"""policydoc: analyze"""

from pathlib import Path

import click
from codeanalyze.core.registry import build_registry  # type: ignore[import-not-found]
from codeanalyze.documents import pipeline as doc_pipeline  # type: ignore[import-not-found]
from codeanalyze.documents.official import (  # type: ignore[import-not-found]
    analyze_policy_directory,
    format_policy_graph_report,
)
from codeanalyze.documents.scanner import analyze_wiki_structure  # type: ignore[import-not-found]
from rich.panel import Panel

from policydoc.cli import _validate_path, console  # type: ignore[import-not-found]


@click.command()
@click.argument("path", default=".")
@click.option("--output", "-o", default=None, help="报告输出路径")
@click.option("--wiki", is_flag=True, help="同步分析 Wiki 结构完整性")
def analyze(path, output, wiki):
    """对公文/政策文档项目运行全量分析。"""
    root = Path(_validate_path(path)).resolve()
    reg = build_registry()
    console.print(Panel.fit(f"[bold green]📁 {root.name}[/]", border_style="green"))
    console.print(
        f"  📄 政策文件: {len(list(root.rglob('*.pdf')) + list(root.rglob('*.docx')) + list(root.rglob('*.doc')))}"
    )

    pg = analyze_policy_directory(str(root))
    console.print(pg.summary)

    if wiki:
        wiki_info = analyze_wiki_structure(str(root))
        if wiki_info.get("available"):
            console.print(
                f"  ✅ Wiki 核心文件: {wiki_info['required_files']['found']}/{wiki_info['required_files']['total']}"
            )

    doc_result = doc_pipeline.analyze_path(str(root), reg)
    console.print(doc_pipeline.format_analysis_summary(doc_result)[:300])

    report_content = format_policy_graph_report(pg)
    target = output or str(root / "policydoc-report.md")
    Path(target).write_text(report_content, encoding="utf-8")
    console.print(f"\n[green]✅ 报告已写入: {target}[/]")
