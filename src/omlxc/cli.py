"""Thin Typer client for the private ``omlxcd`` control plane."""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path
from typing import Annotated, Any, Never, cast
from uuid import uuid4

import typer
from pydantic import JsonValue
from rich.console import Console
from rich.panel import Panel
from rich.table import Table, box
from rich.text import Text

from . import __version__
from .client import DaemonClient, DaemonClientError, DaemonEnvelope, RemoteError
from .config import (
    AtomicWriteError,
    ConfigError,
    build_migration_plan,
    default_config_path,
    load_config,
    load_user_config,
    migrate_legacy_json,
    render_toml,
    write_config_atomic,
)
from .diagnostics import run_direct_doctor
from .domain import EXIT_CONFIG, ErrorEnvelope, error_exit_code
from .service import (
    LaunchdController,
    LaunchdFailure,
    LaunchdPaths,
    build_launchd_plan,
)

_console = Console(highlight=False)
_err_console = Console(stderr=True, highlight=False)

# State → (symbol, rich style)
_STATE_STYLES: dict[str, tuple[str, str]] = {
    "healthy": ("●", "bold green"),
    "online": ("●", "bold green"),
    "ok": ("●", "bold green"),
    "loaded": ("◆", "bold cyan"),
    "running": ("▶", "bold yellow"),
    "planning": ("◌", "yellow"),
    "pending": ("○", "dim"),
    "awaiting_confirmation": ("?", "yellow"),
    "cancelling": ("◐", "magenta"),
    "succeeded": ("✔", "bold green"),
    "failed": ("✖", "bold red"),
    "cancelled": ("⊘", "dim"),
    "degraded": ("◑", "yellow"),
    "offline": ("○", "dim"),
    "stale": ("◌", "dim"),
    "unknown": ("·", "dim"),
}


def _rich_state(state: str) -> Text:
    sym, style = _STATE_STYLES.get(state.lower(), ("·", "dim"))
    return Text(f"{sym} {state}", style=style)


def _rich_bool(value: object) -> Text:
    if value is True:
        return Text("yes", style="green")
    if value is False:
        return Text("no", style="red")
    return Text("—", style="dim")



app = typer.Typer(
    add_completion=False,
    help="Private local compute-hub CLI and keyboard-first cockpit.",
    invoke_without_command=True,
    no_args_is_help=False,
)
nodes_app = typer.Typer(help="Inspect configured compute nodes.")
models_app = typer.Typer(help="Inspect and control daemon model placements.")
routes_app = typer.Typer(help="Explain local physical placement decisions.")
jobs_app = typer.Typer(help="Inspect and control durable daemon jobs.")
metrics_app = typer.Typer(help="Inspect local runtime metrics.")
config_app = typer.Typer(help="Validate or migrate versioned configuration.")
daemon_app = typer.Typer(help="Inspect or plan the private launchd service.")

for name, group in (
    ("nodes", nodes_app),
    ("models", models_app),
    ("routes", routes_app),
    ("jobs", jobs_app),
    ("metrics", metrics_app),
    ("config", config_app),
    ("daemon", daemon_app),
):
    app.add_typer(group, name=name)

ClientFactory = Callable[[Path], DaemonClient]
ClientOperation = Callable[[DaemonClient], Awaitable[DaemonEnvelope]]
Renderer = Callable[[JsonValue | None], str]
PageFetcher = Callable[[str | None], Awaitable[DaemonEnvelope]]
MAX_LOOKUP_PAGES = 100

_client_factory: ClientFactory = DaemonClient
_socket_override: Path | None = None


def _launchd_controller(
    home: Path | None = None, config_path: Path | None = None
) -> LaunchdController:
    selected_config = (config_path or default_config_path()).expanduser()
    return LaunchdController(
        LaunchdPaths.for_home(home or Path.home()),
        config_path=selected_config,
    )


def _show_version(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def command(
    ctx: typer.Context,
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=_show_version, is_eager=True),
    ] = None,
    socket: Annotated[
        Path | None,
        typer.Option("--socket", dir_okay=False, help="Override the private daemon socket."),
    ] = None,
) -> None:
    """Open the TUI in a terminal, or run one versioned client command."""
    del version
    global _socket_override
    _socket_override = socket
    if ctx.invoked_subcommand is not None:
        return
    if _stdio_is_tty():
        _run_tui(socket)
        return
    _fail_local(
        "E100",
        "non-interactive use requires a command; run 'omlxc --help'",
        json_output=False,
    )


def _request_id() -> str:
    return uuid4().hex


def _socket_path() -> Path:
    if _socket_override is not None:
        return _socket_override
    try:
        return load_user_config().daemon.socket_path
    except ConfigError:
        return default_config_path().parent / "omlxcd.sock"


def _stdio_is_tty() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _run_tui(socket: Path | None) -> None:
    from .tui import CockpitApp

    CockpitApp(socket_path=socket or _socket_path()).run()


def _emit_success(data: dict[str, Any], *, request_id: str) -> None:
    typer.echo(
        json.dumps(
            {"schema_version": "1", "request_id": request_id, "data": data},
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


def _emit_envelope(envelope: DaemonEnvelope) -> None:
    typer.echo(
        json.dumps(
            envelope.model_dump(mode="json", exclude_none=True),
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


def _fail_local(code: str, message: str, *, json_output: bool) -> Never:
    request_id = _request_id()
    error = RemoteError(code=code, message=message, retryable=False)
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "schema_version": 1,
                    "request_id": request_id,
                    "error": error.model_dump(mode="json", exclude_none=True),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            err=True,
        )
    else:
        _err_console.print(
            f"[bold red]✖  [{code}][/bold red] {message}"
            f"  [dim](request_id={request_id})[/dim]"
        )
    raise typer.Exit(error_exit_code(code))


def _emit_client_failure(error: DaemonClientError, *, json_output: bool) -> Never:
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "schema_version": 1,
                    "request_id": error.request_id,
                    "error": error.error.model_dump(mode="json", exclude_none=True),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            err=True,
        )
    else:
        _err_console.print(
            f"[bold red]✖  [{error.error.code}][/bold red] {error.error.message}"
            f"  [dim](request_id={error.request_id})[/dim]"
        )
    raise typer.Exit(error.exit_code)


async def _call_daemon(operation: ClientOperation) -> DaemonEnvelope:
    async with _client_factory(_socket_path()) as client:
        return await operation(client)


def _execute(
    operation: ClientOperation,
    *,
    json_output: bool,
    renderer: Renderer,
) -> None:
    try:
        envelope = asyncio.run(_call_daemon(operation))
        if json_output:
            _emit_envelope(envelope)
        else:
            typer.echo(renderer(envelope.data))
    except DaemonClientError as exc:
        _emit_client_failure(exc, json_output=json_output)
    except typer.Exit:
        raise
    except Exception:
        _fail_local("E900", "client could not process the daemon response", json_output=json_output)


def _unsupported(action: str, *, json_output: bool) -> Never:
    _fail_local(
        "E100",
        f"unsupported: daemon API does not expose '{action}' yet",
        json_output=json_output,
    )


def _require_r1(action: str, *, yes: bool, json_output: bool) -> None:
    if yes:
        return
    if not _stdio_is_tty():
        _fail_local("E700", f"safety confirmation required for {action}", json_output=json_output)
    if not typer.confirm(f"Confirm {action}?"):
        _fail_local("E700", f"safety confirmation refused for {action}", json_output=json_output)


def _require_r2(
    action: str,
    *,
    yes: bool,
    confirm_impact: bool,
    json_output: bool,
) -> None:
    impact = f"{action} may interrupt active local inference."
    rollback = "Restore the previous service/config snapshot."
    _emit_r2_plan(action, impact=impact, rollback=rollback, json_output=json_output)
    if _stdio_is_tty():
        if not typer.confirm("Proceed with the service-impacting action?"):
            _fail_local(
                "E700", f"impact confirmation refused for {action}", json_output=json_output
            )
        if not typer.confirm("Confirm the rollback point is understood?"):
            _fail_local(
                "E700", f"rollback confirmation refused for {action}", json_output=json_output
            )
        return
    if not yes or not confirm_impact:
        _fail_local(
            "E700",
            f"{action} requires --yes and --confirm-impact outside a TTY",
            json_output=json_output,
        )


def _emit_r2_plan(action: str, *, impact: str, rollback: str, json_output: bool) -> None:
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "schema_version": 1,
                    "request_id": _request_id(),
                    "data": {
                        "risk": "R2",
                        "action": action,
                        "impact": impact,
                        "rollback": rollback,
                    },
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        return
    typer.echo(f"Impact: {impact}")
    typer.echo(f"Rollback: {rollback}")


@app.command("status")
def status(
    json_output: Annotated[bool, typer.Option("--json", help="Emit versioned JSON.")] = False,
) -> None:
    """Show cached daemon health without probing hardware."""
    _execute(lambda client: client.health(), json_output=json_output, renderer=_render_status)


@nodes_app.command("list")
def nodes_list(
    json_output: Annotated[bool, typer.Option("--json")] = False,
    after: Annotated[str | None, typer.Option("--after")] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, max=100)] = 100,
) -> None:
    _execute(
        lambda client: client.nodes(after=after, limit=limit),
        json_output=json_output,
        renderer=lambda data: _render_items(data, ("id", "display_name", "platform", "state")),
    )


@nodes_app.command("show")
def nodes_show(
    node_id: Annotated[str, typer.Argument()],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _execute(
        lambda client: _selected_node(client, node_id),
        json_output=json_output,
        renderer=_render_mapping,
    )


@nodes_app.command("probe")
def nodes_probe(
    node_id: Annotated[str | None, typer.Argument()] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    del node_id
    _unsupported("nodes probe", json_output=json_output)


@models_app.command("list")
def models_list(
    json_output: Annotated[bool, typer.Option("--json")] = False,
    after: Annotated[str | None, typer.Option("--after")] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, max=100)] = 100,
) -> None:
    _execute(
        lambda client: client.models(after=after, limit=limit),
        json_output=json_output,
        renderer=lambda data: _render_items(data, ("id", "role", "reasoning")),
    )


@models_app.command("show")
def models_show(
    model_id: Annotated[str, typer.Argument()],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _execute(
        lambda client: _selected_model(client, model_id),
        json_output=json_output,
        renderer=_render_mapping,
    )


def _model_mutation(model_id: str, *, load: bool, yes: bool, json_output: bool) -> None:
    action = f"{'load' if load else 'unload'} model {model_id}"
    _require_r1(action, yes=yes, json_output=json_output)

    async def operation(client: DaemonClient) -> DaemonEnvelope:
        if load:
            return await client.load_model(model_id)
        return await client.unload_model(model_id)

    _execute(operation, json_output=json_output, renderer=_render_job)


@models_app.command("load")
def models_load(
    model_id: Annotated[str, typer.Argument()],
    yes: Annotated[bool, typer.Option("--yes", help="Confirm the R1 mutation.")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _model_mutation(model_id, load=True, yes=yes, json_output=json_output)


@models_app.command("unload")
def models_unload(
    model_id: Annotated[str, typer.Argument()],
    yes: Annotated[bool, typer.Option("--yes", help="Confirm the R1 mutation.")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _model_mutation(model_id, load=False, yes=yes, json_output=json_output)


@models_app.command("reconcile")
def models_reconcile(
    yes: Annotated[bool, typer.Option("--yes")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _require_r1("reconcile models", yes=yes, json_output=json_output)
    _unsupported("models reconcile", json_output=json_output)


@routes_app.command("show")
def routes_show(
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _unsupported("routes show", json_output=json_output)


@routes_app.command("plan")
def routes_plan(
    model_id: Annotated[str, typer.Argument()],
    profile: Annotated[str, typer.Option("--profile")] = "interactive",
    context_tokens: Annotated[int, typer.Option("--context-tokens", min=0)] = 0,
    capability: Annotated[list[str] | None, typer.Option("--capability")] = None,
    thinking: Annotated[bool, typer.Option("--thinking")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    capabilities = cast(list[JsonValue], list(capability or ()))
    body: dict[str, JsonValue] = {
        "model_id": model_id,
        "profile": profile,
        "context_tokens": context_tokens,
        "required_capabilities": capabilities,
        "thinking_requested": thinking,
    }
    _execute(
        lambda client: client.plan_route(body),
        json_output=json_output,
        renderer=_render_route,
    )


@routes_app.command("test")
def routes_test(
    model_id: Annotated[str, typer.Argument()],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    del model_id
    _unsupported("routes test", json_output=json_output)


@routes_app.command("pin")
def routes_pin(
    model_id: Annotated[str, typer.Argument()],
    placement_id: Annotated[str, typer.Argument()],
    yes: Annotated[bool, typer.Option("--yes")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    del model_id, placement_id
    _require_r1("pin route", yes=yes, json_output=json_output)
    _unsupported("routes pin", json_output=json_output)


@jobs_app.command("list")
def jobs_list(
    json_output: Annotated[bool, typer.Option("--json")] = False,
    after: Annotated[str | None, typer.Option("--after")] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, max=100)] = 100,
) -> None:
    _execute(
        lambda client: client.jobs(after=after, limit=limit),
        json_output=json_output,
        renderer=lambda data: _render_items(data, ("id", "kind", "state", "progress")),
    )


@jobs_app.command("show")
def jobs_show(
    job_id: Annotated[str, typer.Argument()],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _execute(lambda client: client.job(job_id), json_output=json_output, renderer=_render_job)


@jobs_app.command("cancel")
def jobs_cancel(
    job_id: Annotated[str, typer.Argument()],
    yes: Annotated[bool, typer.Option("--yes")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _require_r1(f"cancel job {job_id}", yes=yes, json_output=json_output)
    _execute(
        lambda client: client.cancel_job(job_id),
        json_output=json_output,
        renderer=_render_job,
    )


@jobs_app.command("watch")
def jobs_watch(
    job_id: Annotated[str | None, typer.Argument()] = None,
    after: Annotated[int, typer.Option("--after", min=0)] = 0,
    output: Annotated[str, typer.Option("--output")] = "ndjson",
) -> None:
    if output != "ndjson":
        _fail_local("E100", "jobs watch only supports --output ndjson", json_output=True)

    async def watch() -> None:
        async with _client_factory(_socket_path()) as client:
            async for event in client.stream_events(after=after):
                if job_id is None or event.job_id == job_id:
                    typer.echo(
                        json.dumps(
                            event.model_dump(mode="json"),
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                    )

    try:
        asyncio.run(watch())
    except DaemonClientError as exc:
        _emit_client_failure(exc, json_output=True)
    except typer.Exit:
        raise
    except Exception:
        _fail_local("E900", "event stream failed", json_output=True)


@metrics_app.command("show")
def metrics_show(
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _execute(lambda client: client.metrics(), json_output=json_output, renderer=_render_mapping)


@metrics_app.command("export")
def metrics_export() -> None:
    _execute(lambda client: client.metrics(), json_output=True, renderer=_render_mapping)


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


@config_app.command("diff")
def config_diff(
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _unsupported("config diff", json_output=json_output)


@config_app.command("apply")
def config_apply(
    yes: Annotated[bool, typer.Option("--yes")] = False,
    confirm_impact: Annotated[bool, typer.Option("--confirm-impact")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _require_r2(
        "apply persistent configuration",
        yes=yes,
        confirm_impact=confirm_impact,
        json_output=json_output,
    )
    _unsupported("config apply", json_output=json_output)


@config_app.command("rollback")
def config_rollback(
    yes: Annotated[bool, typer.Option("--yes")] = False,
    confirm_impact: Annotated[bool, typer.Option("--confirm-impact")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _require_r2(
        "rollback persistent configuration",
        yes=yes,
        confirm_impact=confirm_impact,
        json_output=json_output,
    )
    _unsupported("config rollback", json_output=json_output)


@daemon_app.command("status")
def daemon_status(
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    try:
        asyncio.run(_launchd_controller().status())
    except LaunchdFailure as exc:
        _fail_local(exc.code, str(exc), json_output=json_output)
    data = {"label": "com.omlxc.daemon", "status": "running"}
    if json_output:
        _emit_success(data, request_id=_request_id())
    else:
        typer.echo("com.omlxc.daemon running")


@daemon_app.command("install")
def daemon_install(
    home: Annotated[Path | None, typer.Option("--home", file_okay=False)] = None,
    config: Annotated[Path | None, typer.Option("--config", dir_okay=False)] = None,
    apply: Annotated[bool, typer.Option("--apply")] = False,
    yes: Annotated[bool, typer.Option("--yes")] = False,
    confirm_impact: Annotated[bool, typer.Option("--confirm-impact")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    selected_config = (config or default_config_path()).expanduser()
    try:
        plan = build_launchd_plan(LaunchdPaths.for_home(home or Path.home()), selected_config)
    except LaunchdFailure as exc:
        _fail_local(exc.code, str(exc), json_output=json_output)
    data = {
        "label": "com.omlxc.daemon",
        "executable": str(plan.paths.executable),
        "plist_path": str(plan.paths.plist_path),
        "config_identity": plan.config_identity,
        "will_write": apply,
    }
    if apply:
        _require_r2(
            "install daemon",
            yes=yes,
            confirm_impact=confirm_impact,
            json_output=json_output,
        )
        try:
            result = asyncio.run(_launchd_controller(home, plan.config_path).install())
        except LaunchdFailure as exc:
            _fail_local(exc.code, str(exc), json_output=json_output)
        data.update(
            {
                "status": "installed",
                "plist_path": str(result.plist_path),
                "snapshot_created": result.snapshot_path is not None,
            }
        )
    if json_output:
        _emit_success(data, request_id=_request_id())
    else:
        text = (
            f"INSTALL PLAN\nexecutable {data['executable']}\n"
            f"plist {data['plist_path']}\nwill_write {'yes' if apply else 'no'}"
        )
        typer.echo(text)


@daemon_app.command("uninstall")
def daemon_uninstall(
    yes: Annotated[bool, typer.Option("--yes")] = False,
    confirm_impact: Annotated[bool, typer.Option("--confirm-impact")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _require_r2(
        "uninstall daemon",
        yes=yes,
        confirm_impact=confirm_impact,
        json_output=json_output,
    )
    try:
        result = asyncio.run(_launchd_controller().uninstall())
    except LaunchdFailure as exc:
        _fail_local(exc.code, str(exc), json_output=json_output)
    data = {
        "status": "uninstalled",
        "backup_path": str(result.backup_path) if result.backup_path is not None else None,
        "preserved": [str(path) for path in result.preserved_paths],
    }
    if json_output:
        _emit_success(data, request_id=_request_id())
    else:
        typer.echo(f"uninstalled {data['backup_path'] or '(no plist)'}")


def _daemon_action(action: str, *, yes: bool, confirm_impact: bool, json_output: bool) -> None:
    _require_r2(
        f"{action} daemon",
        yes=yes,
        confirm_impact=confirm_impact,
        json_output=json_output,
    )
    try:
        controller = _launchd_controller()
        if action == "start":
            asyncio.run(controller.start())
        elif action == "stop":
            asyncio.run(controller.stop())
        else:
            asyncio.run(controller.restart())
    except LaunchdFailure as exc:
        _fail_local(exc.code, str(exc), json_output=json_output)
    data = {"label": "com.omlxc.daemon", "status": action}
    if json_output:
        _emit_success(data, request_id=_request_id())
    else:
        typer.echo(f"com.omlxc.daemon {action}")


@daemon_app.command("start")
def daemon_start(
    yes: Annotated[bool, typer.Option("--yes")] = False,
    confirm_impact: Annotated[bool, typer.Option("--confirm-impact")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _daemon_action("start", yes=yes, confirm_impact=confirm_impact, json_output=json_output)


@daemon_app.command("stop")
def daemon_stop(
    yes: Annotated[bool, typer.Option("--yes")] = False,
    confirm_impact: Annotated[bool, typer.Option("--confirm-impact")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _daemon_action("stop", yes=yes, confirm_impact=confirm_impact, json_output=json_output)


@daemon_app.command("restart")
def daemon_restart(
    yes: Annotated[bool, typer.Option("--yes")] = False,
    confirm_impact: Annotated[bool, typer.Option("--confirm-impact")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _daemon_action("restart", yes=yes, confirm_impact=confirm_impact, json_output=json_output)


@app.command("doctor")
def doctor(
    direct: Annotated[bool, typer.Option("--direct")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    if not direct:
        _execute(lambda client: client.health(), json_output=json_output, renderer=_render_status)
        return
    try:
        config = load_user_config()
        data = asyncio.run(run_direct_doctor(config))
    except ConfigError as exc:
        _fail_local("E100", str(exc), json_output=json_output)
    except Exception:
        _fail_local("E900", "direct diagnostics failed", json_output=json_output)
    if json_output:
        _emit_success(data, request_id=_request_id())
    else:
        typer.echo(_render_mapping(cast(JsonValue, data)))


@app.command("benchmark")
def benchmark(
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _unsupported("benchmark", json_output=json_output)


def _mapping(data: JsonValue | None) -> dict[str, JsonValue]:
    if not isinstance(data, dict):
        raise ValueError("expected an object")
    return cast(dict[str, JsonValue], data)


def _items(data: JsonValue | None) -> list[dict[str, JsonValue]]:
    values = _mapping(data).get("items")
    if not isinstance(values, list):
        raise ValueError("expected paginated items")
    if any(not isinstance(item, dict) for item in values):
        raise ValueError("expected object items")
    return cast(list[dict[str, JsonValue]], values)


def _text(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _nested(item: Mapping[str, JsonValue], key: str) -> JsonValue | None:
    if key != "state":
        return item.get(key)
    health = item.get("health")
    return cast(dict[str, JsonValue], health).get("state") if isinstance(health, dict) else None


def _render_items(data: JsonValue | None, columns: Sequence[str]) -> str:
    """Rich-formatted table output for list commands."""
    items = _items(data)
    if not items:
        _console.print("[dim](no items)[/dim]")
        return ""

    table = Table(
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style="bold #2a7ab5",
        border_style="#122035",
        row_styles=["#c8d8ec", "dim #c8d8ec"],
        pad_edge=False,
        expand=False,
    )
    for col in columns:
        table.add_column(col.upper(), no_wrap=True, min_width=8)

    for item in items:
        row: list[Text | str] = []
        for col in columns:
            val = _nested(item, col)
            if col in ("state", "health"):
                row.append(_rich_state(_text(val)))
            elif col == "loaded":
                row.append(_rich_bool(val))
            else:
                row.append(_text(val) if val is not None else Text("—", style="dim"))
        table.add_row(*row)

    _console.print(table)
    return ""


async def _selected_node(client: DaemonClient, identifier: str) -> DaemonEnvelope:
    return await _select_from_pages(
        lambda after: client.nodes(after=after, limit=100), identifier, "node"
    )


async def _selected_model(client: DaemonClient, identifier: str) -> DaemonEnvelope:
    return await _select_from_pages(
        lambda after: client.models(after=after, limit=100), identifier, "model"
    )


async def _select_from_pages(fetch: PageFetcher, identifier: str, resource: str) -> DaemonEnvelope:
    cursor: str | None = None
    seen: set[str] = set()
    request_id = _request_id()
    for _page in range(MAX_LOOKUP_PAGES):
        envelope = await fetch(cursor)
        request_id = envelope.request_id
        for item in _items(envelope.data):
            if item.get("id") == identifier:
                return DaemonEnvelope(
                    schema_version=envelope.schema_version,
                    request_id=envelope.request_id,
                    data=cast(JsonValue, item),
                )
        next_cursor = _mapping(envelope.data).get("next_cursor")
        if next_cursor is None:
            raise DaemonClientError(
                RemoteError(code="E100", message=f"{resource} was not found", retryable=False),
                request_id=request_id,
            )
        if not isinstance(next_cursor, str) or not next_cursor or next_cursor in seen:
            raise DaemonClientError(
                RemoteError(code="E900", message="daemon pagination cursor is invalid"),
                request_id=request_id,
            )
        seen.add(next_cursor)
        cursor = next_cursor
    raise DaemonClientError(
        RemoteError(code="E900", message="daemon pagination exceeded its page limit"),
        request_id=request_id,
    )


def _render_mapping(data: JsonValue | None) -> str:
    """Rich key-value panel output for show/detail commands."""
    mapping = _mapping(data)
    lines: list[str] = []
    for key, value in sorted(mapping.items()):
        key_text = f"[#5a7a9a]{key.upper():<20}[/#5a7a9a]"
        val_s = _text(value)
        if key == "state":
            val_text = _rich_state(val_s).markup
        elif isinstance(value, bool):
            val_text = _rich_bool(value).markup
        else:
            val_text = f"[#c8d8ec]{val_s}[/#c8d8ec]"
        lines.append(f"{key_text}  {val_text}")
    _console.print("\n".join(lines))
    return ""


def _render_status(data: JsonValue | None) -> str:
    """Rich status panel for 'omlxc status'."""
    mapping = _mapping(data)
    status_s = _text(mapping.get("status", "unknown"))
    policy = _text(mapping.get("policy", "interactive"))
    sym, style = _STATE_STYLES.get(status_s.lower(), ("·", "dim"))
    _console.print(
        f"[bold #7dd3f5]omlxcd[/bold #7dd3f5]  "
        f"[{style}]{sym} {status_s.upper()}[/{style}]"
        f"  [dim]policy={policy}[/dim]"
    )
    return ""


def _render_job(data: JsonValue | None) -> str:
    """Rich panel for a single job."""
    mapping = _mapping(data)
    state_s = _text(mapping.get("state", "unknown"))
    sym, style = _STATE_STYLES.get(state_s.lower(), ("·", "dim"))
    _console.print(
        Panel(
            f"[#5a7a9a]kind    [/#5a7a9a] [#c8d8ec]{_text(mapping.get('kind'))}[/#c8d8ec]\n"
            f"[#5a7a9a]state   [/#5a7a9a] [{style}]{sym} {state_s}[/{style}]\n"
            f"[#5a7a9a]progress[/#5a7a9a] [#c8d8ec]{_text(mapping.get('progress'))}[/#c8d8ec]",
            title=f"[bold #7dd3f5]job  {_text(mapping.get('id'))}[/bold #7dd3f5]",
            border_style="#1a4d80",
            expand=False,
        )
    )
    return ""


def _render_route(data: JsonValue | None) -> str:
    """Rich output for route planning."""
    mapping = _mapping(data)
    selected = _text(mapping.get("selected_placement_id"))
    fallback = mapping.get("fallback_chain")
    fallback_text = ", ".join(map(str, fallback)) if isinstance(fallback, list) else "—"
    _console.print(
        f"[#5a7a9a]selected[/#5a7a9a]  [cyan]{selected}[/cyan]\n"
        f"[#5a7a9a]fallback[/#5a7a9a]  [dim]{fallback_text}[/dim]"
    )
    return ""


def main() -> None:
    """Run the ``omlxc`` console script."""
    app()


if __name__ == "__main__":
    main()
