"""Command-line entry point for the incremental v3 control plane."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Never
from uuid import uuid4

import typer

from . import __version__
from .config import (
    AtomicWriteError,
    ConfigError,
    build_migration_plan,
    default_config_path,
    load_config,
    migrate_legacy_json,
    render_toml,
    write_config_atomic,
)
from .domain import EXIT_CONFIG, ErrorEnvelope

app = typer.Typer(
    add_completion=False,
    help="Private local compute-hub CLI.",
    no_args_is_help=True,
)
config_app = typer.Typer(help="Validate or migrate versioned configuration.")
app.add_typer(config_app, name="config")


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
    """Expose versioned local control-plane commands."""


def _request_id() -> str:
    return uuid4().hex


def _emit_success(data: dict[str, Any], *, request_id: str) -> None:
    typer.echo(
        json.dumps(
            {"schema_version": "1", "request_id": request_id, "data": data},
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


def _fail_config(message: str, *, request_id: str, detail: str | None = None) -> Never:
    error = ErrorEnvelope(
        code="E100",
        message=message,
        technical_detail=detail,
        suggested_action="Correct the configuration input and retry.",
        request_id=request_id,
    )
    typer.echo(
        json.dumps(
            {
                "schema_version": "1",
                "request_id": request_id,
                "error": error.model_dump(mode="json"),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        err=True,
    )
    raise typer.Exit(EXIT_CONFIG)


@config_app.command("validate")
def config_validate(
    path: Annotated[
        Path | None,
        typer.Option("--path", help="TOML file to validate."),
    ] = None,
) -> None:
    """Validate config schema v1 without contacting a daemon or backend."""
    request_id = _request_id()
    selected_path = path or default_config_path()
    try:
        config = load_config(selected_path)
    except ConfigError as exc:
        _fail_config("configuration validation failed", request_id=request_id, detail=str(exc))
    _emit_success(
        {"config_schema_version": config.schema_version, "status": "valid"},
        request_id=request_id,
    )


@config_app.command("migrate")
def config_migrate(
    source: Annotated[
        Path,
        typer.Option("--from", exists=False, dir_okay=False, help="Legacy models.json."),
    ],
    target: Annotated[
        Path | None,
        typer.Option("--target", dir_okay=False, help="Explicit destination TOML path."),
    ] = None,
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Write the generated TOML configuration."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Confirm the persistent configuration change."),
    ] = False,
) -> None:
    """Plan a legacy JSON migration; write only with ``--apply --yes``."""
    request_id = _request_id()
    selected_target = target or default_config_path()
    if apply and not yes:
        _fail_config("--apply requires explicit --yes", request_id=request_id)
    try:
        plan = build_migration_plan(source, target=selected_target)
        data = plan.model_dump(mode="json")
        if apply:
            config = migrate_legacy_json(source)
            result = write_config_atomic(selected_target, render_toml(config))
            data["will_write"] = True
            data["snapshot_created"] = result.snapshot_path is not None
        _emit_success(data, request_id=request_id)
    except (AtomicWriteError, ConfigError) as exc:
        _fail_config("configuration migration failed", request_id=request_id, detail=str(exc))


def main() -> None:
    """Run the ``omlxc`` console script."""
    app()
