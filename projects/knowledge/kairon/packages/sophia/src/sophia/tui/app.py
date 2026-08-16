"""Sophia TUI — Rich-based interactive terminal for paradigm exploration."""

from __future__ import annotations


def main() -> int:
    """Interactive paradigm explorer TUI."""
    try:
        from rich import box
        from rich.console import Console
        from rich.panel import Panel
        from rich.prompt import Prompt
        from rich.table import Table
    except ImportError:
        print("Rich not installed. Run: pip install rich")
        return 1

    console = Console()
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]Sophia[/bold cyan] — Symbolic Research Paradigm Engine\n"
            "[dim]12 states · 10 operations · 12 transition rules[/dim]",
            border_style="cyan",
            padding=(1, 3),
        )
    )
    console.print()

    from .compiler import compile_paradigm_sync  # type: ignore[reportMissingImports]
    from .learner import ParadigmLearner  # type: ignore[reportMissingImports]
    from .symbols import BASE_TRANSITIONS, AtomicOp, ResearchState  # type: ignore[reportMissingImports]

    learner = ParadigmLearner()

    while True:
        console.print(
            "[bold]Commands:[/bold] [cyan]compile[/cyan] | [cyan]ops[/cyan] | "
            "[cyan]states[/cyan] | [cyan]transitions[/cyan] | [cyan]learn[/cyan] | "
            "[cyan]quit[/cyan]"
        )
        cmd = Prompt.ask("[bold yellow]>[/bold yellow]").strip().lower()

        if cmd in ("q", "quit", "exit"):
            break

        elif cmd == "ops":
            table = Table(title="Atomic Operations", box=box.ROUNDED, border_style="cyan")
            table.add_column("Name", style="cyan")
            table.add_column("Description", style="dim")
            descriptions = {
                "decompose": "Split question into sub-questions",
                "search": "Gather sources for a claim",
                "extract": "Extract entities/claims",
                "compare": "Compare multiple claims",
                "hypothesize": "Generate tentative answer",
                "verify": "Check claim against evidence",
                "synthesize": "Combine claims",
                "eliminate": "Remove disproven hypothesis",
                "iterate": "Re-run with refinement",
                "conclude": "Finalize answer",
            }
            for op in AtomicOp:
                table.add_row(op.value, descriptions.get(op.value, ""))
            console.print(table)

        elif cmd == "states":
            table = Table(title="Research States", box=box.ROUNDED, border_style="cyan")
            table.add_column("State", style="cyan")
            table.add_column("Value", style="dim")
            for s in ResearchState:
                table.add_row(s.name, s.value)
            console.print(table)

        elif cmd == "transitions":
            table = Table(title="Base Transition Rules", box=box.ROUNDED, border_style="cyan")
            table.add_column("From", style="yellow")
            table.add_column("Operation", style="cyan")
            table.add_column("To", style="green")
            table.add_column("Gate", style="dim")
            table.add_column("On Fail", style="red")
            for t in BASE_TRANSITIONS:
                table.add_row(
                    t.from_state.value,
                    t.operation.value,
                    t.to_state.value,
                    t.gate.__name__,
                    t.on_fail.value,
                )
            console.print(table)

        elif cmd == "compile":
            query = Prompt.ask("Research question")
            prog = compile_paradigm_sync(query)
            console.print()
            console.print(
                Panel(
                    f"[bold cyan]{prog.name}[/bold cyan]\n"
                    f"[dim]{prog.description}[/dim]\n\n"
                    f"[green]Operations:[/green] {' → '.join(op.value for op in prog.operations)}\n"
                    f"[dim]States: {prog.state_count} | Transitions: {len(prog.transitions)} | "
                    f"Max iterations: {prog.max_iterations}[/dim]",
                    border_style="cyan",
                )
            )
            issues = prog.validate()
            if issues:
                for i in issues:
                    console.print(f"  [yellow]⚠ {i}[/yellow]")
            # Record trace
            from .learner import ResearchTrace  # type: ignore[reportMissingImports]

            learner.record(
                ResearchTrace(
                    query=query,
                    paradigm_name=prog.name,
                    operations=[op.value for op in prog.operations],
                    quality_score=70,
                    completed=True,
                )
            )

        elif cmd == "learn":
            effective = learner.get_effective_ops()
            if effective:
                table = Table(title="Operation Effectiveness", box=box.ROUNDED, border_style="green")
                table.add_column("Operation", style="cyan")
                table.add_column("Score", justify="right", style="green")
                for op, score in sorted(effective.items(), key=lambda x: -x[1])[:10]:
                    table.add_row(op, f"{score:.1f}")
                console.print(table)
            else:
                console.print("[dim]No traces recorded yet. Use 'compile' first.[/dim]")

        console.print()

    console.print("[dim]Sophia session ended.[/dim]")
    return 0
