"""CLI commands: docscan"""

from pathlib import Path

import click
from rich.panel import Panel

from codeanalyze.commands.common import _validate_path, console  # type: ignore[import-not-found]
from codeanalyze.documents.scanner import analyze_wiki_structure, scan_directory  # type: ignore[import-not-found]


@click.command()
@click.argument("path", default=".")
@click.option("--wiki", is_flag=True, help="详细分析 wiki 结构完整性")
@click.option("--versions", is_flag=True, help="列出版本链")
@click.option("--output", "-o", default=None, help="报告输出路径")
def docscan(path: str, wiki: bool, versions: bool, output: str | None) -> None:
    """扫描文档项目（如国转中心）的结构并生成分析报告。

    自动识别文件类型、分类目录、版本链、wiki 结构完整性.
    适合既有代码又有文档的混合项目.
    """
    root = _validate_path(path)
    console.print(Panel.fit(f"[bold cyan]📋 文档项目扫描: {root.name}[/]", border_style="cyan"))

    # — 目录扫描 —
    console.print("\n[bold]▶ 扫描目录结构...[/]")
    dm = scan_directory(str(root))
    console.print(dm.summary)

    # — Wiki 结构 —
    wiki_info = None
    if wiki or (root / "_工作机制" / "wiki").is_dir():
        console.print("\n[bold]▶ 分析 Wiki 知识库完整性...[/]")
        wiki_info = analyze_wiki_structure(str(root))
        if wiki_info.get("available"):
            req = wiki_info["required_files"]
            meta = wiki_info["meta_files"]
            console.print(f"  ✅ Wiki 根: {wiki_info['wiki_root']}")
            console.print(f"  核心文件: {req['found']}/{req['total']}")
            if req["missing"]:
                console.print(f"  [yellow]  缺失: {', '.join(req['missing'])}[/]")
            console.print(f"  元文件: {meta['found']}/{meta['total']}")
            console.print(f"  板块: {wiki_info['section_count']} 个")
            if wiki_info["sections"]:
                for s in wiki_info["sections"]:
                    console.print(f"    - {s}")
        else:
            console.print("  ⏭️ 无 _工作机制/wiki 目录")

    # — 版本链 —
    if versions and dm.version_chains:
        console.print(f"\n[bold]▶ 版本链 ({len(dm.version_chains)} 组)[/]")
        for chain in dm.version_chains[:10]:
            base = Path(chain[0].path).stem
            clean_name = base.rsplit("v", 1)[0] if "v" in base else base
            console.print(f"  📎 {clean_name}")
            for doc in chain:
                rel = Path(doc.path).relative_to(root)
                console.print(f"    v{doc.version}: {rel}")
    elif versions:
        console.print("\n[bold]▶ 版本链: 未发现[/]")

    # — 生成完整报告 —
    lines = [
        f"# 文档项目扫描报告 — {root.name}",
        f"> 生成时间: ... | 路径: {root}",
        "",
        "## 目录概览",
        f"- 总文件: {dm.total_files}",
        f"- Wiki 文件: {dm.wiki_files}",
        f"- 原始文档 (PDF/DOCX/DOC): {dm.raw_docs}",
        f"- 表格 (XLSX/XLS): {dm.spreadsheets}",
        f"- 文本 (MD/TXT): {dm.text_files}",
        "",
        "## 分类分布",
    ]
    for cat, files in sorted(dm.categories.items()):
        lines.append(f"- **{cat}**: {len(files)} 文件")
    lines.append("")

    if wiki_info and wiki_info.get("available"):
        lines.extend(
            [
                "## Wiki 知识库",
                f"- 核心文件: {wiki_info['required_files']['found']}/{wiki_info['required_files']['total']}",
                f"- 元文件: {wiki_info['meta_files']['found']}/{wiki_info['meta_files']['total']}",
                f"- 板块数: {wiki_info['section_count']}",
                "",
            ]
        )

    if dm.version_chains:
        lines.append("## 版本链")
        for chain in dm.version_chains[:10]:
            base = Path(chain[0].path).stem
            clean_name = base.rsplit("v", 1)[0] if "v" in base else base
            lines.append(f"- {clean_name}: {' → '.join(f'v{d.version}' for d in chain)}")
        lines.append("")

    lines.extend(["## 分析建议"])
    if dm.raw_docs > 0:
        lines.append("- 安装 Docling 将原始文档转为 Markdown: `pip install docling`")
    if dm.spreadsheets > 0:
        lines.append("- XLSX 文件可转为结构化数据，建议用 WPS MCP 或 pandas 抽取")
    if versions and dm.version_chains:
        lines.append("- 版本链较多，建议清理冗余版本或统一版本号规范")
    lines.append("")

    content = "\n".join(lines)
    target = output or str(root / "codeanalyze-docscan-report.md")
    Path(target).write_text(content, encoding="utf-8")
    console.print(f"\n[green]✅ 扫描报告已写入: {target}[/]")

    # 路由建议
    if dm.code_files > 0 and dm.raw_docs > 0:
        console.print(
            Panel.fit(
                "[bold yellow]🔀 混合项目检测[/]\n"
                "既有代码又有文档，推荐: codeanalyze analyze --docs .\n"
                "先装依赖: pip install graphifyy docling && npm install -g gitnexus",
                border_style="yellow",
            )
        )
    elif dm.raw_docs > 0:
        console.print(
            Panel.fit(
                "[bold cyan]💡 文档项目分析建议[/]\n"
                "安装 Docling-Graph 做文档→知识图谱抽取:\n"
                "  pip install docling docling-graph\n"
                "然后: codeanalyze docs .",
                border_style="cyan",
            )
        )
    elif dm.code_files > 0:
        console.print(
            Panel.fit(
                "[bold green]💡 代码项目分析建议[/]\n"
                "安装 Graphify + GitNexus 做全链路分析:\n"
                "  pip install graphifyy && npm install -g gitnexus\n"
                "然后: codeanalyze analyze .",
                border_style="green",
            )
        )
