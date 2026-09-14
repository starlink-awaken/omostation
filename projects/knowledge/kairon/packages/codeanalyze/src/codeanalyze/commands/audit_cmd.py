"""CLI commands: audit"""

from pathlib import Path

import click
from rich.panel import Panel

from codeanalyze.commands.common import _validate_path, console  # type: ignore[import-not-found]
from codeanalyze.reports.audit import run_audit  # type: ignore[import-not-found]


@click.command()
@click.argument("path", default=".")
@click.option("--output", "-o", default=None, help="报告输出路径")
def audit(path: str, output: str | None) -> None:
    """运行知识审计——交叉验证原始文档与 Wiki 知识库的一致性。

    检查以下维度:
    1. 政策文件 vs 政策图谱+TIMELINE（文号/日期/事件匹配）
    2. 数字化方案 vs 知识库（核心概念覆盖）
    3. 组织文件 vs ENTITIES.md（角色覆盖率）
    4. 平台情况表 vs 平台全景（平台名称覆盖率）
    5. Wiki 结构完整性（核心文件是否存在）
    """
    root = _validate_path(path)
    console.print(
        Panel.fit(
            f"[bold cyan]📋 知识审计: {root.name}[/]",
            border_style="cyan",
        )
    )

    report = run_audit(str(root))
    content = report.to_markdown()

    target = output or str(root / "codeanalyze-audit-report.md")
    Path(target).write_text(content, encoding="utf-8")

    console.print(f"  检查组: {len(report.groups)}")
    console.print(f"  检查项: {report.total_checks}")
    console.print(f"  通过:   {report.total_passed} ({report.score:.0f}%)")
    console.print(f"  未通过: {report.total_failed}")
    console.print(f"\n  📄 {target}")

    if report.total_failed > 0:
        console.print(
            Panel.fit(
                f"[bold yellow]审计发现知识缺口[/]\n{report.total_failed} 项未通过，详见报告",
                border_style="yellow",
            )
        )
    else:
        console.print(
            Panel.fit(
                "[bold green]✅ 全部检查通过[/]",
                border_style="green",
            )
        )
