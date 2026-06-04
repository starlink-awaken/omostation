"""
omo-debt CLI 入口
Command-line interface for Pattern 09 v2.0 debt scoring tool.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from omo_debt.__version__ import __version__
from omo_debt.core.scoring import calculate_score_v2
from omo_debt.core.stage import get_normalization_factor, get_stage_weights, identify_project_stage
from omo_debt.legacy.age import calculate_age_score
from omo_debt.legacy.core import adjust_score_with_legacy, calculate_legacy_score
from omo_debt.legacy.migration import calculate_migration_path_score
from omo_debt.legacy.resistance import calculate_refactoring_resistance_score

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="omo-debt")
def cli():
    """
    omo-debt: Pattern 09 v2.0 债务评分工具

    基于项目生命周期阶段的技术债务评分与优先级管理工具。
    """
    pass


@cli.command()
@click.argument("project_path", type=click.Path(exists=True))
@click.option("--months", default=6, help="分析月数（默认 6）")
@click.option("--verbose", is_flag=True, help="显示详细信息")
def identify_stage(project_path: str, months: int, verbose: bool):
    """
    识别项目生命周期阶段

    分析 Git 提交历史，自动判断项目处于：
    - 快速演进期 (rapid_evolution): >30 commits/month
    - 稳定增长期 (stable_growth): 10-30 commits/month
    - 维护期 (maintenance): <10 commits/month

    示例：
        omo-debt identify-stage /path/to/project
        omo-debt identify-stage . --months 12 --verbose
    """
    try:
        path = Path(project_path).resolve()
        console.print(f"\n[bold cyan]分析项目：[/bold cyan]{path}")

        # 调用核心算法
        result = identify_project_stage(str(path), months=months)

        # 创建结果表格
        table = Table(title="项目阶段识别结果", show_header=True, header_style="bold magenta")
        table.add_column("指标", style="cyan", width=20)
        table.add_column("值", style="green")

        table.add_row("分析周期", f"{months} 个月")
        table.add_row("总提交数", str(result.total_commits))
        table.add_row("月均提交", f"{result.monthly_avg:.1f}")
        table.add_row("识别阶段", result.stage)
        table.add_row("置信度", result.confidence)

        console.print(table)

        weights = get_stage_weights(result.stage)
        norm_factor = get_normalization_factor(result.stage)
        panel_content = f"""
[bold]推荐配置：[/bold]
• 权重比例：影响 {weights[0]:.2f} / 频繁度 {weights[1]:.2f} / 成本 {weights[2]:.2f}
• 归一化系数：{norm_factor:.1f}
• 使用建议：{result._get_recommendation()}
        """
        console.print(Panel(panel_content.strip(), title="[bold green]评分配置[/bold green]"))

        if verbose:
            console.print(f"\n[dim]项目路径：{path}[/dim]")

    except Exception as e:
        console.print(f"[bold red]错误：[/bold red]{e}", style="red")
        sys.exit(1)


@cli.command()
@click.option("--impact", type=float, required=True, help="影响分数 (1-10)")
@click.option("--frequency", type=float, required=True, help="频繁度分数 (1-10)")
@click.option("--cost", type=float, required=True, help="成本分数 (1-10)")
@click.option(
    "--stage",
    type=click.Choice(["rapid_evolution", "stable_growth", "maintenance"]),
    help="项目阶段（可选，不指定则自动检测）",
)
@click.option("--project-path", type=click.Path(exists=True), help="项目路径（用于自动检测阶段）")
@click.option("--enable-honesty/--no-honesty", default=False, help="启用诚实度评估 (Pattern 09 v2.1)")
@click.option("--debt-files", multiple=True, type=click.Path(exists=True), help="债务清单文件路径（用于诚实度评估）")
def score(
    impact: float,
    frequency: float,
    cost: float,
    stage: Optional[str],
    project_path: Optional[str],
    enable_honesty: bool,
    debt_files: tuple[str, ...],
):
    """
    计算技术债务加权分数

    使用 Pattern 09 v2.0/v2.1 算法，根据项目阶段动态调整权重。
    v2.1 新增：诚实度维度，评估债务披露质量。

    示例：
        # Pattern 09 v2.0 (基础评分)
        omo-debt score --impact 9 --frequency 8 --cost 7
        omo-debt score --impact 9 --frequency 8 --cost 7 --stage rapid_evolution

        # Pattern 09 v2.1 (含诚实度)
        omo-debt score --impact 9 --frequency 8 --cost 7 --enable-honesty \\
          --project-path . --debt-files debt.yaml
    """
    try:
        # 自动检测阶段（如果提供了项目路径）
        if project_path and not stage:
            console.print("[dim]自动检测项目阶段...[/dim]")
            stage_info = identify_project_stage(project_path)
            stage = stage_info.stage
            console.print(f"[dim]检测到阶段：{stage}[/dim]\n")

        # 计算基础分数
        result = calculate_score_v2(impact=impact, frequency=frequency, cost=cost, stage=stage)

        # 诚实度评估 (Pattern 09 v2.1)
        honesty_score = None
        adjusted_score = result.normalized_score

        if enable_honesty:
            if not project_path:
                console.print("[yellow]⚠️  警告：诚实度评估需要 --project-path 参数，跳过[/yellow]\n")
            else:
                from omo_debt.honesty.completeness import calculate_completeness
                from omo_debt.honesty.consistency import calculate_consistency
                from omo_debt.honesty.core import adjust_score_with_honesty, calculate_honesty_score
                from omo_debt.honesty.verifiability import calculate_verifiability

                console.print("[dim]计算诚实度分数...[/dim]")

                # 1. 计算完整性（使用项目路径和债务文件列表）
                completeness_result = calculate_completeness(
                    project_path=project_path, debt_files=list(debt_files) if debt_files else []
                )

                # 2. 计算一致性（使用当前评分作为 self_rating）
                # 简化版：没有 peer 数据时使用默认评分
                consistency_result = calculate_consistency(
                    self_rating=result.normalized_score,
                    peer_avg=None,  # 暂时没有 peer 数据
                    historical_scores=None,  # 暂时没有历史数据
                )

                # 3. 计算可验证性（需要解析债务文件获取证据）
                # 简化版：仅基于文件存在性
                verifiability_result = calculate_verifiability(
                    has_impact_evidence=bool(debt_files),
                    has_frequency_evidence=bool(debt_files),
                    has_cost_evidence=bool(debt_files),
                    evidence_commits=[],
                    evidence_issues=[],
                    evidence_refs=list(debt_files) if debt_files else [],
                    total_claims=3,  # 默认3个声明
                )

                # 4. 组合为总分
                honesty_score = calculate_honesty_score(
                    completeness=completeness_result.score,
                    consistency=consistency_result.score,
                    verifiability=verifiability_result.score,
                )

                adjusted_score = adjust_score_with_honesty(result.normalized_score, honesty_score.score)
                console.print(f"[dim]诚实度：{honesty_score.score:.1f}/10[/dim]\n")

        # 显示结果
        title = "债务评分结果 (Pattern 09 v2.1)" if enable_honesty else "债务评分结果 (Pattern 09 v2.0)"
        table = Table(title=title, show_header=True, header_style="bold magenta")
        table.add_column("指标", style="cyan", width=20)
        table.add_column("值", style="green")

        table.add_row("影响分数", f"{impact:.1f}")
        table.add_row("频繁度分数", f"{frequency:.1f}")
        table.add_row("成本分数", f"{cost:.1f}")
        table.add_row("项目阶段", result.stage or "N/A")
        table.add_row("基础分数", f"{result.base_score:.2f}")
        table.add_row("归一化系数", f"{result.normalization_factor:.1f}")

        # v2.1: 诚实度信息
        if enable_honesty and honesty_score:
            table.add_row("─" * 20, "─" * 20)

            # 诚实度状态标识
            if honesty_score.score >= 8.5:
                status = "✅ 极高"
                status_color = "bright_green"
            elif honesty_score.score >= 7.0:
                status = "✅ 高"
                status_color = "green"
            elif honesty_score.score >= 5.0:
                status = "⚠️ 中等"
                status_color = "yellow"
            elif honesty_score.score >= 3.0:
                status = "⚠️ 低"
                status_color = "orange1"
            else:
                status = "❌ 极低"
                status_color = "red"

            table.add_row("诚实度分数", f"[{status_color}]{honesty_score.score:.1f}/10 ({status})[/{status_color}]")
            table.add_row("  - 完整性", f"{honesty_score.completeness:.1f}/10")
            table.add_row("  - 一致性", f"{honesty_score.consistency:.1f}/10")
            table.add_row("  - 可验证性", f"{honesty_score.verifiability:.1f}/10")

            bonus = ((honesty_score.score - 5.0) / 20.0) * 100
            bonus_str = f"+{bonus:.1f}%" if bonus > 0 else f"{bonus:.1f}%"
            table.add_row("诚实度加成", bonus_str)
            table.add_row("调整后分数", f"[bold]{adjusted_score:.2f}[/bold]")
        else:
            table.add_row("最终分数", f"[bold]{result.normalized_score:.2f}[/bold]")

        # 优先级 (基于调整后分数重新计算)
        if adjusted_score >= 8.5:
            priority = "P0"
            priority_color = "red"
        elif adjusted_score >= 6.5:
            priority = "P1"
            priority_color = "yellow"
        else:
            priority = "P2"
            priority_color = "green"

        table.add_row("优先级", f"[bold {priority_color}]{priority}[/bold {priority_color}]")

        console.print(table)

        # 显示建议
        if priority == "P0":
            recommendation = "🔴 极高优先级债务，建议立即安排资源处理"
        elif priority == "P1":
            recommendation = "🟡 高优先级债务，建议本迭代内处理"
        else:
            recommendation = "🟢 中等优先级债务，可适当延后处理"

        if enable_honesty and honesty_score:
            if honesty_score.score < 5.0:
                recommendation += "\n\n⚠️  诚实度评分较低，建议：\n"
                if honesty_score.completeness < 5.0:
                    recommendation += "  • 补充完整的债务清单（覆盖所有问题文件）\n"
                if honesty_score.consistency < 5.0:
                    recommendation += "  • 检查评分一致性（避免主观偏差）\n"
                if honesty_score.verifiability < 5.0:
                    recommendation += "  • 增加可验证证据（代码引用、issue链接、测试案例）"

        console.print(Panel(recommendation.strip(), title="[bold green]建议[/bold green]"))

    except Exception as e:
        console.print(f"[bold red]错误：[/bold red]{e}", style="red")
        import traceback

        if "--verbose" in sys.argv:
            traceback.print_exc()
        sys.exit(1)


@cli.command("assess-legacy")
@click.option("--age-months", type=int, required=True, help="债务存在时长（月）")
@click.option("--stable-months", type=int, default=0, show_default=True, help="最近稳定期（月）")
@click.option("--dependency-score", type=float, required=True, help="依赖复杂度分数 (0-10)")
@click.option("--coupling-score", type=float, required=True, help="耦合度分数 (0-10)")
@click.option("--technical-risk", type=float, required=True, help="技术风险分数 (0-10)")
@click.option("--solution-clarity", type=float, required=True, help="方案清晰度分数 (0-10)")
@click.option("--incremental/--no-incremental", default=True, help="是否支持增量迁移")
@click.option("--has-migration-docs/--no-migration-docs", default=False, help="是否存在迁移文档")
@click.option("--base-priority", type=float, default=0.0, show_default=True, help="基础优先级分数 (0-100)")
def assess_legacy(
    age_months: int,
    stable_months: int,
    dependency_score: float,
    coupling_score: float,
    technical_risk: float,
    solution_clarity: float,
    incremental: bool,
    has_migration_docs: bool,
    base_priority: float,
):
    """评估 Legacy (L) 维度并给出优先级调整结果。"""
    try:
        age_score = calculate_age_score(age_months=age_months, stable_months=stable_months)
        resistance_score = calculate_refactoring_resistance_score(
            dependency_score=dependency_score,
            coupling_score=coupling_score,
            technical_risk=technical_risk,
        )
        path_score = calculate_migration_path_score(
            solution_clarity=solution_clarity,
            incremental=incremental,
            has_migration_docs=has_migration_docs,
        )
        legacy_score = calculate_legacy_score(
            age_score=age_score,
            resistance_score=resistance_score,
            path_score=path_score,
        )
        adjusted_priority = adjust_score_with_legacy(base_score=base_priority, legacy_score=legacy_score)

        table = Table(title="Legacy Assessment", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan", width=24)
        table.add_column("Value", style="green")
        table.add_row("Age Score", f"{age_score:.2f}")
        table.add_row("Resistance Score", f"{resistance_score:.2f}")
        table.add_row("Migration Path Score", f"{path_score:.2f}")
        table.add_row("Legacy Score", f"{legacy_score:.2f}")
        table.add_row("Adjusted Priority", f"{adjusted_priority:.2f}")
        console.print(table)
    except Exception as e:
        console.print(f"[bold red]错误：[/bold red]{e}", style="red")
        sys.exit(1)


@cli.command()
@click.argument("debt_files", nargs=-1, type=click.Path(exists=True), required=True)
@click.option("--format", type=click.Choice(["table", "json", "yaml"]), default="table", help="输出格式（默认 table）")
def compare(debt_files: tuple[str, ...], format: str):
    """
    对比多个债务项优先级

    读取多个债务 YAML 文件，按优先级排序输出。

    债务 YAML 格式：
        id: GBR-D01
        title: 未实现跨表关联查询
        impact: 9
        frequency: 8
        cost: 7
        stage: rapid_evolution  # 可选，不指定则使用 project_path 自动检测
        project: gbrain

    示例：
        omo-debt compare debt1.yaml debt2.yaml debt3.yaml
        omo-debt compare debts/*.yaml --format json
    """
    try:
        from pathlib import Path

        import yaml

        # 读取所有债务文件
        debts = []
        for file_path in debt_files:
            with open(file_path) as f:
                debt_data = yaml.safe_load(f)

                # 验证必需字段
                if not all(k in debt_data for k in ["impact", "frequency", "cost"]):
                    console.print(f"[yellow]⚠️  跳过 {file_path}：缺少必需字段（impact/frequency/cost）[/yellow]")
                    continue

                # 计算评分
                result = calculate_score_v2(
                    impact=debt_data["impact"],
                    frequency=debt_data["frequency"],
                    cost=debt_data["cost"],
                    stage=debt_data.get("stage"),
                )

                debts.append(
                    {
                        "id": debt_data.get("id", Path(file_path).stem),
                        "title": debt_data.get("title", "未命名债务"),
                        "project": debt_data.get("project", "unknown"),
                        "stage": result.stage or "N/A",
                        "impact": debt_data["impact"],
                        "frequency": debt_data["frequency"],
                        "cost": debt_data["cost"],
                        "score": result.normalized_score,
                        "priority": result.priority,
                        "file": file_path,
                    }
                )

        # 按优先级和分数排序
        debts.sort(key=lambda d: ({"P0": 0, "P1": 1, "P2": 2}[d["priority"]], -d["score"]))

        # 输出结果
        if format == "table":
            table = Table(title=f"债务对比结果（共 {len(debts)} 项）", show_header=True, header_style="bold magenta")
            table.add_column("#", style="dim", width=4)
            table.add_column("ID", style="cyan", width=12)
            table.add_column("项目", style="blue", width=12)
            table.add_column("标题", style="white", width=30)
            table.add_column("阶段", style="yellow", width=16)
            table.add_column("分数", style="green", width=8)
            table.add_column("优先级", width=8)

            for i, debt in enumerate(debts, 1):
                priority_color = {"P0": "red", "P1": "yellow", "P2": "green"}[debt["priority"]]
                table.add_row(
                    str(i),
                    debt["id"],
                    debt["project"],
                    debt["title"][:28] + "..." if len(debt["title"]) > 28 else debt["title"],
                    debt["stage"],
                    f"{debt['score']:.2f}",
                    f"[{priority_color}]{debt['priority']}[/{priority_color}]",
                )

            console.print(table)

            # 统计信息
            p0_count = sum(1 for d in debts if d["priority"] == "P0")
            p1_count = sum(1 for d in debts if d["priority"] == "P1")
            p2_count = sum(1 for d in debts if d["priority"] == "P2")

            stats = f"""
[bold]优先级分布：[/bold]
• P0（极高优先级）：{p0_count} 项
• P1（高优先级）：{p1_count} 项
• P2（中等优先级）：{p2_count} 项
            """
            console.print(Panel(stats.strip(), title="[bold green]统计信息[/bold green]"))

        elif format == "json":
            import json

            console.print(json.dumps(debts, indent=2, ensure_ascii=False))

        elif format == "yaml":
            import yaml

            console.print(yaml.dump(debts, allow_unicode=True, default_flow_style=False))

    except Exception as e:
        console.print(f"[bold red]错误：[/bold red]{e}", style="red")
        sys.exit(1)


@cli.command()
@click.argument("project_path", type=click.Path(exists=True))
@click.option("--debt-file", type=click.Path(exists=True), help="债务清单文件（YAML，包含 debts 列表）")
@click.option("--output", type=click.Path(), help="输出报告文件路径")
def analyze(project_path: str, debt_file: str | None, output: str | None):
    """
    分析项目债务健康度

    扫描项目，生成完整的债务健康报告。

    示例：
        omo-debt analyze /path/to/project
        omo-debt analyze . --debt-file debts.yaml
        omo-debt analyze . --debt-file debts.yaml --output report.md
    """
    try:
        from pathlib import Path

        path = Path(project_path).resolve()
        console.print(f"\n[bold cyan]分析项目：[/bold cyan]{path}")

        # 1. 识别项目阶段
        stage_info = identify_project_stage(str(path))
        console.print(f"[dim]项目阶段：{stage_info.stage}（月均 {stage_info.monthly_avg:.1f} 次提交）[/dim]")

        # 2. 读取债务清单
        debts = []
        if debt_file:
            import yaml

            with open(debt_file) as f:
                data = yaml.safe_load(f)
                debt_list = data.get("debts", []) if isinstance(data, dict) else data

                for debt_data in debt_list:
                    result = calculate_score_v2(
                        impact=debt_data["impact"],
                        frequency=debt_data["frequency"],
                        cost=debt_data["cost"],
                        stage=debt_data.get("stage") or stage_info.stage,
                    )

                    debts.append(
                        {
                            "id": debt_data.get("id", "未知"),
                            "title": debt_data.get("title", "未命名"),
                            "score": result.normalized_score,
                            "priority": result.priority,
                        }
                    )

        # 3. 生成报告
        if debts:
            # 按优先级分组
            p0_debts = [d for d in debts if d["priority"] == "P0"]
            p1_debts = [d for d in debts if d["priority"] == "P1"]
            p2_debts = [d for d in debts if d["priority"] == "P2"]

            # 计算健康度分数（100 - 加权债务影响）
            health_score = max(0, 100 - (len(p0_debts) * 15 + len(p1_debts) * 8 + len(p2_debts) * 3))

            # 显示结果
            table = Table(title="项目债务健康报告", show_header=True, header_style="bold magenta")
            table.add_column("指标", style="cyan", width=20)
            table.add_column("值", style="green")

            table.add_row("项目路径", str(path))
            table.add_row("生命周期阶段", stage_info.stage)
            table.add_row("月均提交数", f"{stage_info.monthly_avg:.1f}")
            table.add_row("债务总数", str(len(debts)))
            table.add_row("P0（极高优先级）", str(len(p0_debts)))
            table.add_row("P1（高优先级）", str(len(p1_debts)))
            table.add_row("P2（中等优先级）", str(len(p2_debts)))

            # 健康度评级
            if health_score >= 80:
                health_grade = "🟢 优秀"
            elif health_score >= 60:
                health_grade = "🟡 良好"
            elif health_score >= 40:
                health_grade = "🟠 一般"
            else:
                health_grade = "🔴 需改进"

            table.add_row("健康度分数", f"{health_score}/100")
            table.add_row("健康度评级", health_grade)

            console.print(table)

            # 建议
            recommendations = []
            if len(p0_debts) > 0:
                recommendations.append(f"• {len(p0_debts)} 个 P0 债务需要立即处理")
            if len(p1_debts) > 3:
                recommendations.append(f"• {len(p1_debts)} 个 P1 债务较多，建议本迭代优先处理 3-5 个")
            if health_score < 60:
                recommendations.append("• 总体健康度较低，建议制定系统性还债计划")

            if recommendations:
                console.print(Panel("\n".join(recommendations), title="[bold yellow]改进建议[/bold yellow]"))

            # 输出报告文件
            if output:
                recommendations_text = "".join(f"{r}\n" for r in recommendations)
                p0_text = (
                    "".join(f"- [{d['id']}] {d['title']} (分数: {d['score']:.2f})\n" for d in p0_debts)
                    if p0_debts
                    else "无\n"
                )
                p1_text = (
                    "".join(f"- [{d['id']}] {d['title']} (分数: {d['score']:.2f})\n" for d in p1_debts)
                    if p1_debts
                    else "无\n"
                )
                p2_text = (
                    "".join(f"- [{d['id']}] {d['title']} (分数: {d['score']:.2f})\n" for d in p2_debts)
                    if p2_debts
                    else "无\n"
                )
                report_content = f"""# 项目债务健康报告

**项目路径**：{path}
**生命周期阶段**：{stage_info.stage}
**月均提交数**：{stage_info.monthly_avg:.1f}
**分析时间**：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 债务概览

- **债务总数**：{len(debts)}
- **P0（极高优先级）**：{len(p0_debts)}
- **P1（高优先级）**：{len(p1_debts)}
- **P2（中等优先级）**：{len(p2_debts)}

## 健康度评估

- **健康度分数**：{health_score}/100
- **健康度评级**：{health_grade}

## 改进建议

{recommendations_text}

## 债务清单

### P0 债务（极高优先级）

{p0_text}

### P1 债务（高优先级）

{p1_text}

### P2 债务（中等优先级）

{p2_text}
"""
                Path(output).write_text(report_content)
                console.print(f"\n[green]✓[/green] 报告已保存到：{output}")
        else:
            console.print("[yellow]未找到债务清单，请使用 --debt-file 指定债务文件[/yellow]")

    except Exception as e:
        console.print(f"[bold red]错误：[/bold red]{e}", style="red")
        sys.exit(1)


def main():
    """CLI 入口点"""
    cli()


if __name__ == "__main__":
    main()


# Import honesty assessment command
try:
    from omo_debt.cli_honesty import assess_honesty

    cli.add_command(assess_honesty)
except ImportError:
    pass  # Honesty module not available
