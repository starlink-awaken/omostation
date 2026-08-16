"""CLI commands: documents (公文/政策分析)"""

from pathlib import Path

import click
from rich.panel import Panel

from codeanalyze.commands.common import _validate_path, console  # type: ignore[import-not-found]
from codeanalyze.documents.official import (  # type: ignore[import-not-found]
    analyze_policy_directory,
    format_policy_graph_report,
)


@click.command()
@click.argument("path", default=".")
@click.option("--output", "-o", default=None, help="报告输出路径")
@click.option("--levels", is_flag=True, help="按政策层级分类展示")
def documents(path: str, output: str | None, levels: bool) -> None:
    """分析公文/政策文档项目（如国转中心政策法规目录）。

    自动提取：
    - 政策元数据（文号/发文机关/日期/层级）
    - 政策层级归类（国家/部委/北京市/房山区）
    - 业务领域分类
    - 政策间关系
    - 与现有政策图谱结构对齐
    """
    root = _validate_path(path)
    console.print(Panel.fit(f"[bold cyan]📜 公文/政策分析: {root.name}[/]", border_style="cyan"))

    if not root.is_dir():
        console.print("[red]❌ 路径不是目录[/]")
        return

    # 检查是否为政策文档目录
    policy_files = list(root.rglob("*.pdf")) + list(root.rglob("*.docx")) + list(root.rglob("*.doc"))
    if not policy_files:
        console.print("[yellow]⚠️ 未找到政策文档（PDF/DOCX/DOC）。确认路径是否正确？[/]")
        console.print("  建议: codeanalyze documents ./path/to/policy-documents")
        return

    console.print(f"  📄 发现 {len(policy_files)} 个政策文档文件")

    # 运行分析
    console.print("\n[bold cyan]▶ 提取政策元数据...[/]")
    graph = analyze_policy_directory(str(root))
    console.print(graph.summary)

    # 按层级展示
    if levels and "房山区级" in graph.level_groups:
        console.print("\n[bold]按层级分布:[/]")
        for level in ["国家级", "部委级", "北京市级", "房山区级", "其他"]:
            docs = graph.level_groups.get(level, [])
            if docs:
                console.print(f"\n  [underline]{level}[/] ({len(docs)})")
                for doc in docs[:6]:
                    dn = f" | {doc.doc_number}" if doc.doc_number else ""
                    console.print(f"    - {doc.title}{dn}")

    # 生成报告
    report_content = format_policy_graph_report(graph)
    target = output or str(root / "codeanalyze-policy-report.md")
    Path(target).write_text(report_content, encoding="utf-8")
    console.print(f"\n[green]✅ 报告已写入: {target}[/]")

    # 建议
    console.print(
        Panel.fit(
            "[bold cyan]💡 公文项目分析建议[/]\n"
            "1. 安装 MinerU 提升中文 PDF 解析精度: pip install mineru\n"
            "2. 已有政策图谱(_工作机制/wiki/30-政策与申报/00-政策图谱.md)\n"
            "   可与自动提取结果交叉验证，更新图谱\n"
            "3. Docling-Graph 可用于提取政策实体间深层关系:\n"
            "   pip install docling-graph && codeanalyze docs .",
            border_style="cyan",
        )
    )
