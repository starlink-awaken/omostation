"""Temporary command-line entry point for the v3 package skeleton."""

from __future__ import annotations

from typing import Annotated

import typer

from . import __version__

app = typer.Typer(
    add_completion=False,
    help="Private local compute-hub CLI (Task 2 package skeleton).",
    no_args_is_help=True,
)


def _show_version(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def command(
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=_show_version, is_eager=True),
    ] = None,
) -> None:
    """Expose only help and version while Task 2 establishes packaging."""


def main() -> None:
    """Run the ``omlxc`` console script."""
    app()
