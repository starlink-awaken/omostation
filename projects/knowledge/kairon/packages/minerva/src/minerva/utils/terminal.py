"""Rich terminal output — progress bars, colors, stage visualization."""
# rich is optional; rich symbols degrade to None.
# pyright: reportOptionalCall=false
# pyright: reportOptionalMemberAccess=false

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

try:
    from rich import box
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None  # type: ignore[assignment]
    Layout = None  # type: ignore[assignment]
    Live = None  # type: ignore[assignment]
    Panel = None  # type: ignore[assignment]
    Table = None  # type: ignore[assignment]
    box = None  # type: ignore[assignment]

console = Console() if RICH_AVAILABLE else None


def print_banner() -> None:
    """Print Minerva startup banner."""
    if not RICH_AVAILABLE:
        print("=== Minerva Deep Research ===")
        return
    assert console is not None
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]Minerva[/bold cyan] [dim]— Local-First Deep Research[/dim]\n[dim]Ollama MLX · 7 Backends · Neo4j · spaCy · MCP[/dim]",
            border_style="cyan",
            padding=(1, 3),
        )
    )
    console.print()


def print_pipeline_header(query: str, level: str) -> None:
    """Print research pipeline start."""
    if not RICH_AVAILABLE:
        print(f"\nResearch: {query} [Level: {level}]")
        print("-" * 60)
        return
    assert console is not None
    console.print()
    console.print(f"  [bold]Query:[/bold] {query[:100]}")
    console.print(
        f"  [bold]Level:[/bold] [cyan]{level}[/cyan]  |  [bold]Backends:[/bold] [dim]DDG · Scholar · arXiv · Metaso · Exa[/dim]"
    )
    console.print()


@contextmanager
def live_pipeline_display() -> Generator[Any]:
    """Show live pipeline progress with stage status + scrolling log panel."""
    if not RICH_AVAILABLE:
        yield None
        return

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=1),
        Layout(name="body", size=12),
        Layout(name="footer", size=1),
    )
    layout["body"].split_row(
        Layout(name="stages", ratio=2),
        Layout(name="log", ratio=3),
    )

    header = Panel("[bold cyan]Minerva Research Pipeline[/bold cyan]", style="cyan", padding=(0, 1))
    footer = Panel("[dim]Running...[/dim]", style="dim", padding=(0, 1))

    stage_info: dict[str, Any] = {"stages": [], "current": ""}
    log_lines: list[str] = []

    def render_stages() -> Any:
        lines = []
        for s in stage_info["stages"][-9:]:
            icon = "✓" if s.get("done") else ("✗" if s.get("failed") else "◌")
            color = "green" if s.get("done") else ("red" if s.get("failed") else "yellow")
            elapsed = f"[dim]({s['elapsed']:.1f}s)[/dim]" if s.get("elapsed") else ""
            lines.append(f"  [{color}]{icon} {s['name']:<20} {elapsed}[/{color}]")
        return Panel(
            "\n".join(lines) if lines else "[dim]Initializing...[/dim]",
            title="Stages",
            border_style="blue",
        )

    def render_log() -> Any:
        visible = log_lines[-10:] or ["[dim]Waiting for stages...[/dim]"]
        return Panel("\n".join(visible), title="Log", border_style="green")

    with Live(layout, refresh_per_second=4, transient=False):
        layout["header"].update(header)
        layout["stages"].update(render_stages())
        layout["log"].update(render_log())
        layout["footer"].update(footer)

        class StageTracker:
            def add_stage(self, name: Any, elapsed: Any = 0, done: Any = False) -> None:
                stage_info["stages"].append({"name": name, "elapsed": elapsed, "done": done})
                stage_info["current"] = name
                layout["stages"].update(render_stages())

            def mark_done(self, name: Any, elapsed: Any = 0) -> None:
                for s in stage_info["stages"]:
                    if s["name"] == name:
                        s["done"] = True
                        s["elapsed"] = elapsed
                        break
                log_lines.append(f"[green]✓[/green] {name} completed in {elapsed:.1f}s")
                layout["stages"].update(render_stages())
                layout["log"].update(render_log())
                completed = sum(1 for s in stage_info["stages"] if s["done"])
                total = len(stage_info["stages"])
                layout["footer"].update(
                    Panel(f"[dim]Completed: {completed}/{total}[/dim]", style="dim", padding=(0, 1))
                )

            def mark_failed(self, name: Any, error: Any = "") -> None:
                for s in stage_info["stages"]:
                    if s["name"] == name:
                        s["failed"] = True
                        break
                log_lines.append(f"[red]✗[/red] {name} failed: {error[:80]}")
                layout["stages"].update(render_stages())
                layout["log"].update(render_log())

            def log(self, message: Any) -> None:
                log_lines.append(f"[dim]{message}[/dim]")
                layout["log"].update(render_log())

        yield StageTracker()


def print_stats_panel(
    stage_timings: dict[str, float],
    quality_score: str,
    source_count: int,
    entity_count: int,
    total_time: float,
    cost: float = 0.0,
) -> None:
    """Print post-run statistics panel with ASCII bar chart."""
    if not RICH_AVAILABLE:
        print(f"\nTotal: {total_time:.1f}s | Sources: {source_count} | Entities: {entity_count} | Cost: ${cost:.2f}")
        return

    assert console is not None
    console.print()
    # Stage timing bars
    table = Table(title="[bold]Pipeline Statistics[/bold]", box=box.ROUNDED, border_style="cyan")
    table.add_column("Stage", style="cyan")
    table.add_column("Time", justify="right", style="green")
    table.add_column("Bar", justify="left")
    table.add_column("%", justify="right", style="dim")

    max_time = max(stage_timings.values()) if stage_timings else 1
    for name, elapsed in stage_timings.items():
        pct = elapsed / total_time * 100 if total_time > 0 else 0
        bar_width = int(elapsed / max_time * 20)
        bar = "[green]" + "█" * bar_width + "[/green]" + "░" * (20 - bar_width)
        table.add_row(name, f"{elapsed:.1f}s", bar, f"{pct:.0f}%")

    table.add_row("─" * 15, "─" * 8, "─" * 22, "─" * 4)
    table.add_row("[bold]TOTAL[/bold]", f"[bold green]{total_time:.1f}s[/bold green]", "", "100%")

    console.print(table)
    console.print(
        f"  [dim]Sources: {source_count}[/dim]  |  [dim]Entities: {entity_count}[/dim]  |  [bold]Quality: {quality_score}/100[/bold]  |  [bold yellow]Cost: ${cost:.4f}[/bold yellow]"
    )
    console.print()


def print_summary_table(
    stage_timings: dict[str, float],
    quality_score: str,
    source_count: int,
    entity_count: int,
    total_time: float,
) -> None:
    """Print a rich summary table."""
    if not RICH_AVAILABLE:
        print(f"\nTotal: {total_time:.1f}s | Sources: {source_count} | Entities: {entity_count}")
        return

    assert console is not None
    table = Table(title="Pipeline Summary", box=box.ROUNDED, border_style="cyan")
    table.add_column("Stage", style="cyan")
    table.add_column("Time", justify="right", style="green")
    table.add_column("Bar", justify="left")

    max_time = max(stage_timings.values()) if stage_timings else 1
    for name, elapsed in stage_timings.items():
        bar_width = int(elapsed / max_time * 20)
        bar = "█" * bar_width + "░" * (20 - bar_width)
        table.add_row(name, f"{elapsed:.1f}s", f"[dim]{bar}[/dim]")

    table.add_row("─" * 15, "─" * 8, "─" * 22)
    table.add_row("[bold]TOTAL[/bold]", f"[bold green]{total_time:.1f}s[/bold green]", "")

    console.print()
    console.print(table)
    console.print(
        f"  [dim]Sources: {source_count}[/dim]  |  [dim]Entities: {entity_count}[/dim]  |  [bold]Score: {quality_score}/100[/bold]"
    )
    console.print()
