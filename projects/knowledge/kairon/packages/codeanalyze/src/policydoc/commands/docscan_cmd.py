"""policydoc: docscan — 政策文档项目扫描"""

from pathlib import Path

import click
from codeanalyze.documents.scanner import analyze_wiki_structure, scan_directory  # type: ignore[import-not-found]
from rich.panel import Panel

from policydoc.cli import console  # type: ignore[import-not-found]


def _validate_path(path: str) -> Path:
    root = Path(path).resolve()
    if not root.exists():
        raise click.BadParameter(f"path does not exist: {path}")
    return root


@click.command()
@click.argument("path", default=".")
@click.option("--wiki", is_flag=True, help="详细分析 wiki 结构完整性")
@click.option("--versions", is_flag=True, help="列出版本链")
@click.option("--output", "-o", default=None, help="报告输出路径")
def docscan(path: str, wiki: bool, versions: bool, output: str | None):
    """扫描政策文档项目（如国转中心）的结构并生成分析报告。

    自动识别文件类型、分类目录、版本链、wiki 结构完整性。
    """
    root = _validate_path(path)
    console.print(Panel.fit(f"[bold cyan]📋 政策文档项目扫描: {root.name}[/]", border_style="cyan"))

    console.print("\n[bold]▶ 扫描目录结构...[/]")
    dm = scan_directory(str(root))
    console.print(dm.summary)

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
            for s in wiki_info.get("sections") or []:
                console.print(f"    - {s}")
        else:
            console.print("  ⏭️ 无 _工作机制/wiki 目录")

    if versions and dm.version_chains:
        console.print(f"\n[bold]▶ 版本链 ({len(dm.version_chains)} 组)[/]")
        for chain in dm.version_chains[:10]:
            base = Path(chain[0].path).stem
            clean_name = base.rsplit("v", 1)[0] if "v" in base else base
            console.print(f"  📎 {clean_name}")
            for doc in chain:
                rel = Path(doc.path).relative_to(root)
                console.print(f"    v{doc.version}: {rel}")

    # 生成报告
    lines = [
        f"# 政策文档扫描报告 — {root.name}",
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

    content = "\n".join(lines)
    target = output or str(root / "policydoc-docscan-report.md")
    Path(target).write_text(content, encoding="utf-8")
    console.print(f"\n[green]✅ 扫描报告已写入: {target}[/]")
