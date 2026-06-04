"""
CLI commands for honesty dimension assessment.

Extends CLI with --honesty and --audit commands.
"""

from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from omo_debt.honesty.completeness import calculate_completeness
from omo_debt.honesty.consistency import calculate_consistency
from omo_debt.honesty.core import calculate_honesty_score
from omo_debt.honesty.verifiability import (
    calculate_verifiability,
    count_claims,
    detect_cost_evidence,
    detect_frequency_evidence,
    detect_impact_evidence,
)

console = Console()


@click.command()
@click.option(
    "--project-path",
    "-p",
    default=".",
    help="Path to project root",
)
@click.option(
    "--debt-files",
    "-f",
    multiple=True,
    help="Files referenced in debt (can specify multiple)",
)
@click.option(
    "--disclosed-issues",
    "-i",
    multiple=True,
    help="Disclosed issue IDs (can specify multiple)",
)
@click.option(
    "--description",
    "-d",
    help="Debt description (for verifiability analysis)",
)
@click.option(
    "--evidence-commits",
    multiple=True,
    help="Commit references (can specify multiple)",
)
@click.option(
    "--evidence-issues",
    multiple=True,
    help="Issue references (can specify multiple)",
)
@click.option(
    "--evidence-refs",
    multiple=True,
    help="Document references (can specify multiple)",
)
@click.option(
    "--peer-avg",
    type=float,
    help="Average score of similar debts (for consistency)",
)
@click.option(
    "--historical-scores",
    help="Historical scores (comma-separated, e.g., '7.0,7.5,8.0')",
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["table", "json", "yaml"]),
    default="table",
    help="Output format",
)
def assess_honesty(
    project_path: str,
    debt_files: tuple[str, ...],
    disclosed_issues: tuple[str, ...],
    description: Optional[str],
    evidence_commits: tuple[str, ...],
    evidence_issues: tuple[str, ...],
    evidence_refs: tuple[str, ...],
    peer_avg: Optional[float],
    historical_scores: Optional[str],
    output: str,
):
    """Assess honesty dimension of technical debt disclosure.

    Examples:
        # Basic assessment
        omo-debt assess-honesty --debt-files src/main.py --disclosed-issues "#42"

        # Full assessment with evidence
        omo-debt assess-honesty \\
            --debt-files src/auth.py --debt-files src/session.py \\
            --disclosed-issues "#1" --disclosed-issues "#2" \\
            --description "Authentication module has security vulnerabilities" \\
            --evidence-commits abc123 --evidence-issues "#1" \\
            --peer-avg 7.5
    """
    console.print("[bold cyan]🔍 Assessing Honesty Dimension...[/bold cyan]\n")

    # 1. Calculate completeness
    console.print("[dim]→ Calculating completeness...[/dim]")
    completeness_result = calculate_completeness(
        project_path=project_path,
        debt_files=list(debt_files) if debt_files else None,
        disclosed_issues=list(disclosed_issues) if disclosed_issues else None,
    )

    # 2. Calculate consistency
    console.print("[dim]→ Calculating consistency...[/dim]")
    hist_scores = None
    if historical_scores:
        hist_scores = [float(s.strip()) for s in historical_scores.split(",")]

    # For consistency, we need a self_rating; use a placeholder if not provided
    self_rating = 7.0  # Default placeholder

    consistency_result = calculate_consistency(
        self_rating=self_rating,
        peer_avg=peer_avg,
        historical_scores=hist_scores,
    )

    # 3. Calculate verifiability
    console.print("[dim]→ Calculating verifiability...[/dim]")

    has_impact_evidence = False
    has_frequency_evidence = False
    has_cost_evidence = False
    total_claims = 1

    if description:
        has_impact_evidence = detect_impact_evidence(description, list(evidence_refs))
        has_frequency_evidence = detect_frequency_evidence(description, list(evidence_commits), list(evidence_refs))
        has_cost_evidence = detect_cost_evidence(description, list(evidence_refs))
        total_claims = count_claims(description)

    verifiability_result = calculate_verifiability(
        has_impact_evidence=has_impact_evidence,
        has_frequency_evidence=has_frequency_evidence,
        has_cost_evidence=has_cost_evidence,
        evidence_commits=list(evidence_commits) if evidence_commits else None,
        evidence_issues=list(evidence_issues) if evidence_issues else None,
        evidence_refs=list(evidence_refs) if evidence_refs else None,
        total_claims=total_claims,
    )

    # 4. Calculate overall honesty
    console.print("[dim]→ Calculating overall honesty...[/dim]\n")
    honesty_result = calculate_honesty_score(
        completeness=completeness_result.score,
        consistency=consistency_result.score,
        verifiability=verifiability_result.score,
        evidence_commits=list(evidence_commits) if evidence_commits else None,
        evidence_issues=list(evidence_issues) if evidence_issues else None,
        evidence_refs=list(evidence_refs) if evidence_refs else None,
    )

    # Output results
    if output == "table":
        _print_honesty_table(
            honesty_result,
            completeness_result,
            consistency_result,
            verifiability_result,
        )
    elif output == "json":
        import json

        result_dict = {
            "honesty": {
                "score": honesty_result.score,
                "grade": honesty_result.grade,
                "bonus": honesty_result.bonus,
                "completeness": completeness_result.score,
                "consistency": consistency_result.score,
                "verifiability": verifiability_result.score,
            }
        }
        console.print(json.dumps(result_dict, indent=2, ensure_ascii=False))
    elif output == "yaml":
        import yaml

        result_dict = {
            "honesty": {
                "score": honesty_result.score,
                "grade": honesty_result.grade,
                "bonus": honesty_result.bonus,
                "completeness": completeness_result.score,
                "consistency": consistency_result.score,
                "verifiability": verifiability_result.score,
            }
        }
        console.print(yaml.dump(result_dict, allow_unicode=True, default_flow_style=False))


def _print_honesty_table(honesty, completeness, consistency, verifiability):
    """Print honesty assessment results as rich table."""

    # Main summary table
    table = Table(title="📊 Honesty Assessment Results", show_header=True, header_style="bold magenta")
    table.add_column("Dimension", style="cyan", width=20)
    table.add_column("Score", justify="right", style="green", width=10)
    table.add_column("Grade", justify="center", width=10)
    table.add_column("Details", style="dim", width=40)

    # Overall honesty
    grade_color = _get_grade_color(honesty.grade)
    table.add_row(
        "Overall Honesty",
        f"{honesty.score:.2f}",
        f"[{grade_color}]{honesty.grade}[/{grade_color}]",
        f"Bonus: {honesty.bonus:+.2%} (priority adjustment)",
    )

    table.add_section()

    # Completeness
    table.add_row(
        "Completeness (40%)",
        f"{completeness.score:.2f}",
        "",
        f"{completeness.debt_files_count} debt files, {completeness.disclosed_issues} disclosed issues",
    )

    # Consistency
    table.add_row(
        "Consistency (35%)",
        f"{consistency.score:.2f}",
        "",
        f"Volatility: {consistency.score_volatility:.2f}, Peer avg: {consistency.peer_avg or 'N/A'}",
    )

    # Verifiability
    evidence_count = sum(
        [
            verifiability.has_impact_evidence,
            verifiability.has_frequency_evidence,
            verifiability.has_cost_evidence,
        ]
    )
    refs_count = verifiability.referenced_commits + verifiability.referenced_issues + verifiability.referenced_docs
    table.add_row(
        "Verifiability (25%)",
        f"{verifiability.score:.2f}",
        "",
        f"Evidence: {evidence_count}/3, Refs: {refs_count}",
    )

    console.print(table)

    # Interpretation
    console.print()
    if honesty.score >= 8.5:
        console.print("✅ [bold green]Excellent disclosure quality![/bold green] Priority boost applies.")
    elif honesty.score >= 7.0:
        console.print("✅ [green]Good disclosure quality.[/green] Minor priority adjustment.")
    elif honesty.score >= 5.0:
        console.print("⚠️  [yellow]Average disclosure quality.[/yellow] No priority adjustment.")
    elif honesty.score >= 3.0:
        console.print("⚠️  [orange]Poor disclosure quality.[/orange] Priority penalty applies.")
    else:
        console.print("❌ [bold red]Dangerous disclosure quality![/bold red] Significant priority penalty.")


def _get_grade_color(grade: str) -> str:
    """Get color for grade."""
    if grade == "优秀":
        return "bold green"
    elif grade == "良好":
        return "green"
    elif grade == "一般":
        return "yellow"
    elif grade == "较差":
        return "orange"
    else:
        return "bold red"


if __name__ == "__main__":
    assess_honesty()
