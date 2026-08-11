"""Explicit daemon placeholder for the v3 package skeleton."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from . import __version__

app = typer.Typer(
    add_completion=False,
    help="Private local compute-hub daemon (Task 2 placeholder only).",
    invoke_without_command=True,
)


def _show_version(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def command(
    context: typer.Context,
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=_show_version, is_eager=True),
    ] = None,
) -> None:
    """Report a stable placeholder until the daemon is implemented in Task 7."""
    if context.invoked_subcommand is None:
        typer.echo(
            json.dumps(
                {
                    "component": "omlxcd",
                    "status": "placeholder",
                    "version": __version__,
                },
                sort_keys=True,
            )
        )


def main() -> None:
    """Run the ``omlxcd`` console script."""
    app()


if __name__ == "__main__":
    main()
