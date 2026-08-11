"""Daemon console entry and private Unix-socket server."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer

from omlxc.api import create_app
from omlxc.config import ConfigError, load_config
from omlxc.domain import EXIT_CONFIG, EXIT_INTERNAL

from .runtime import DaemonRuntime, RuntimeComponent
from .server import DaemonServer

app = typer.Typer(
    add_completion=False,
    help="Run the private omlxcd HTTP service on a Unix Socket.",
    invoke_without_command=True,
)


@app.callback()
def command(
    config: Annotated[Path | None, typer.Option("--config")] = None,
    check: Annotated[
        bool, typer.Option("--check", help="Validate startup without binding.")
    ] = False,
) -> None:
    """Load daemon configuration, then validate or serve it."""
    try:
        loaded = load_config(config) if config is not None else load_config()
    except ConfigError:
        typer.echo(
            json.dumps(
                {
                    "schema_version": 1,
                    "error": {"code": "E100", "message": "invalid daemon configuration"},
                }
            ),
            err=True,
        )
        raise typer.Exit(EXIT_CONFIG) from None
    if check:
        typer.echo(json.dumps({"schema_version": 1, "data": {"status": "valid"}}))
        return
    server = DaemonServer(create_app(), socket_path=loaded.daemon.socket_path)
    try:
        asyncio.run(_serve(server))
    except (OSError, RuntimeError):
        typer.echo(
            json.dumps(
                {"schema_version": 1, "error": {"code": "E900", "message": "daemon startup failed"}}
            ),
            err=True,
        )
        raise typer.Exit(EXIT_INTERNAL) from None


async def _serve(server: DaemonServer) -> None:
    await server.start()
    task = asyncio.current_task()
    try:
        while task is not None and not task.cancelled():
            await asyncio.sleep(3600)
    finally:
        await server.stop()


def main() -> None:
    app()


__all__ = ["DaemonRuntime", "DaemonServer", "RuntimeComponent", "app", "main"]
