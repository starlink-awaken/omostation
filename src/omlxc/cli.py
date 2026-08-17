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
from typer import Abort

from . import __version__
from .cli_guide import (
    DAEMON_OPERATIONS,
    MAX_GUIDE_TRANSITIONS,
    GuideOperation,
    GuideRequest,
    GuideState,
    advance,
    render_prompt,
    validate_public_identifier,
)
from .cli_presenter import (
    ErrorContext,
    render_error,
    render_lifecycle_help,
)
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
from .dataplane.semantic_cache import SemanticCacheRegistry
from .dataplane.thermal import ThermalGuard
from .dataplane.triage import TriageClassifier
from .dataplane.vram_budget import VRAMBudgetEstimator
from .diagnostics import run_direct_doctor
from .domain import EXIT_CONFIG, ErrorEnvelope, error_exit_code
from .domain.protocols import ChatMessage
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
    epilog="Quick start: omlxc status\nGuided help: omlxc guide",
    invoke_without_command=True,
    no_args_is_help=False,
    rich_markup_mode=None,
)
nodes_app = typer.Typer(help="Inspect configured compute nodes.")
models_app = typer.Typer(help="Inspect and control daemon model placements.")
routes_app = typer.Typer(help="Explain local physical placement decisions.")
jobs_app = typer.Typer(help="Inspect and control durable daemon jobs.")
metrics_app = typer.Typer(help="Inspect local runtime metrics.")
benchmark_app = typer.Typer(help="Benchmark local model latency and generation throughput.")
config_app = typer.Typer(help="Validate or migrate versioned configuration.")
daemon_app = typer.Typer(help="Inspect or plan the private launchd service.")
fabric_app = typer.Typer(help="Inspect Compute Fabric governance, triage, and VRAM budget.")

for name, group in (
    ("nodes", nodes_app),
    ("models", models_app),
    ("routes", routes_app),
    ("jobs", jobs_app),
    ("metrics", metrics_app),
    ("benchmark", benchmark_app),
    ("config", config_app),
    ("daemon", daemon_app),
    ("fabric", fabric_app),
):
    app.add_typer(group, name=name)

ClientFactory = Callable[[Path], DaemonClient]
ClientOperation = Callable[[DaemonClient], Awaitable[DaemonEnvelope]]
Renderer = Callable[[JsonValue | None], str]
PageFetcher = Callable[[str | None], Awaitable[DaemonEnvelope]]
MAX_LOOKUP_PAGES = 100

_client_factory: ClientFactory = DaemonClient
_socket_override: Path | None = None


def _launchd_controller(home: Path | None = None, config_path: Path | None = None) -> LaunchdController:
    selected_config = (config_path or default_config_path()).expanduser()
    return LaunchdController(
        LaunchdPaths.for_home(home or Path.home()),
        config_path=selected_config,
    )


def _show_version(value: bool) -> None:
    if value:
        _console.print(f"omlxc [bold cyan]v{__version__}[/bold cyan]  [dim]© 2026[/dim]")
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


def _fail_local(
    code: str,
    message: str,
    *,
    json_output: bool,
    context: ErrorContext = ErrorContext.GENERAL,
) -> Never:
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
        typer.echo(render_error(error, request_id=request_id, context=context), err=True)
    raise typer.Exit(error_exit_code(code))


def _emit_client_failure(
    error: DaemonClientError,
    *,
    json_output: bool,
    context: ErrorContext = ErrorContext.GENERAL,
) -> Never:
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
        typer.echo(
            render_error(error.error, request_id=error.request_id, context=context),
            err=True,
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
    error_context: ErrorContext = ErrorContext.GENERAL,
) -> None:
    try:
        envelope = asyncio.run(_call_daemon(operation))
        if json_output:
            _emit_envelope(envelope)
        else:
            result = renderer(envelope.data)
            if result:
                typer.echo(result)
    except DaemonClientError as exc:
        _emit_client_failure(exc, json_output=json_output, context=error_context)
    except typer.Exit:
        raise
    except Exception:
        _fail_local(
            "E900",
            "client could not process the daemon response",
            json_output=json_output,
            context=error_context,
        )


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
    _console.print(
        Panel(
            f"This action carries Risk Level 1 (R1).\\nImpact: {action}",
            title="[bold yellow]Warning[/bold yellow]",
            border_style="yellow",
        )
    )
    if not typer.confirm(typer.style(f"? Confirm {action}?", fg=typer.colors.YELLOW)):
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
            _fail_local("E700", f"impact confirmation refused for {action}", json_output=json_output)
        if not typer.confirm("Confirm the rollback point is understood?"):
            _fail_local("E700", f"rollback confirmation refused for {action}", json_output=json_output)
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
    _console.print(
        Panel(
            f"[bold]Impact:[/bold] {impact}\n[bold]Rollback:[/bold] {rollback}",
            title=f"[bold red]R2 Warning: {action}[/bold red]",
            border_style="red",
        )
    )


@app.command("status")
def status(
    json_output: Annotated[bool, typer.Option("--json", help="Emit versioned JSON.")] = False,
) -> None:
    """Show cached daemon health without probing hardware."""
    _execute(
        lambda client: client.health(),
        json_output=json_output,
        renderer=_render_status,
        error_context=ErrorContext.STATUS,
    )


@app.command("resolve")
def resolve(
    alias: Annotated[str, typer.Argument(help="The model alias or ID to resolve")],
    json_output: Annotated[bool, typer.Option("--json", help="Emit versioned JSON.")] = False,
) -> None:
    """Resolve an alias to a fully qualified model specification."""
    _execute(
        lambda client: client.resolve_model(alias),
        json_output=json_output,
        renderer=_render_mapping,
        error_context=ErrorContext.GENERAL,
    )


def _guide_argument(request: GuideRequest) -> str:
    argument = request.argument
    if not isinstance(argument, str) or not argument:
        raise ValueError("guide operation is invalid")
    return argument


async def _guide_operation(client: DaemonClient, request: GuideRequest) -> DaemonEnvelope:
    if request.operation not in DAEMON_OPERATIONS:
        raise ValueError("guide operation is invalid")
    if request.operation in {GuideOperation.HEALTH, GuideOperation.DAEMON_HEALTH}:
        return await client.health()
    if request.operation is GuideOperation.MODELS:
        return await client.models(after=None, limit=20)
    if request.operation is GuideOperation.ROUTE:
        argument = _guide_argument(request)
        body: dict[str, JsonValue] = {
            "model_id": argument,
            "profile": "interactive",
            "context_tokens": 0,
            "required_capabilities": [],
            "thinking_requested": False,
        }
        return await client.plan_route(body)
    if request.operation is GuideOperation.JOB:
        return await client.job(_guide_argument(request))
    raise ValueError("guide operation is invalid")


def _render_guide_result(operation: GuideOperation, data: JsonValue | None) -> str:
    if operation in {GuideOperation.HEALTH, GuideOperation.DAEMON_HEALTH}:
        return _render_status(data)
    if operation is GuideOperation.MODELS:
        return _render_items(data, ("id", "role", "reasoning"))
    if operation is GuideOperation.ROUTE:
        return _render_guide_route(data)
    if operation is GuideOperation.JOB:
        return _render_job(data)
    raise ValueError("guide operation is invalid")


def _render_guide_route(data: JsonValue | None) -> str:
    mapping = _mapping(data)
    selected = mapping.get("selected_placement_id")
    fallback = mapping.get("fallback_chain")
    if not isinstance(selected, str) or not isinstance(fallback, list):
        raise ValueError("guide route data is invalid")
    safe_route: dict[str, JsonValue] = {
        "selected_placement_id": validate_public_identifier(selected),
        "fallback_chain": [validate_public_identifier(value) for value in fallback],
    }
    return _render_route(safe_route)


@app.command("guide")
def guide() -> None:
    """Choose a bounded, read-only workflow for a common compute goal."""
    if not _stdio_is_tty():
        _fail_local(
            "E100",
            "guide requires an interactive terminal",
            json_output=False,
            context=ErrorContext.GUIDE,
        )

    state = GuideState.GOAL
    for _ in range(MAX_GUIDE_TRANSITIONS):
        try:
            typer.echo(render_prompt(state))
            answer = typer.prompt("Select")
            transition = advance(state, answer)
        except (Abort, EOFError, KeyboardInterrupt):
            _fail_local("E100", "guide cancelled", json_output=False, context=ErrorContext.GUIDE)
        except ValueError:
            _fail_local("E100", "guide input is invalid", json_output=False, context=ErrorContext.GUIDE)

        state = transition.next_state
        request = transition.request
        if request is None:
            continue
        if request.operation is GuideOperation.LIFECYCLE_HELP:
            try:
                typer.echo(render_lifecycle_help(_guide_argument(request)))
            except ValueError:
                _fail_local("E100", "guide input is invalid", json_output=False, context=ErrorContext.GUIDE)
            return

        guide_request = request
        try:
            envelope = asyncio.run(
                _call_daemon(lambda client, guide_request=guide_request: _guide_operation(client, guide_request))
            )
        except DaemonClientError as exc:
            _emit_client_failure(exc, json_output=False, context=ErrorContext.GUIDE)
        except ValueError:
            _fail_local(
                "E900",
                "guide could not safely process the daemon response",
                json_output=False,
                context=ErrorContext.GUIDE,
            )

        try:
            typer.echo(_render_guide_result(guide_request.operation, envelope.data))
        except Abort:
            _fail_local("E100", "guide cancelled", json_output=False, context=ErrorContext.GUIDE)
        except Exception:
            _fail_local(
                "E900",
                "guide could not safely process the daemon response",
                json_output=False,
                context=ErrorContext.GUIDE,
            )
        return

    _fail_local(
        "E900",
        "guide transition limit exceeded",
        json_output=False,
        context=ErrorContext.GUIDE,
    )


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
    node_id: Annotated[str, typer.Argument()],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _execute(
        lambda client: client.probe_node(node_id),
        json_output=json_output,
        renderer=_render_mapping,
    )


@nodes_app.command("diagnose")
def nodes_diagnose(
    node_id: Annotated[str, typer.Argument()],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Explain cached node availability without refreshing backend hardware."""
    _execute(
        lambda client: client.node_diagnostics(node_id),
        json_output=json_output,
        renderer=_render_mapping,
    )


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

    _execute(
        operation,
        json_output=json_output,
        renderer=_render_job,
        error_context=ErrorContext.ROUTE,
    )


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
    explain: Annotated[
        bool,
        typer.Option("--explain", help="Show scoring breakdown and rejections."),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    del explain
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
        error_context=ErrorContext.ROUTE,
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


@benchmark_app.command("run")
def benchmark_run(
    model_id: Annotated[str | None, typer.Argument()] = None,
    all_models: Annotated[bool, typer.Option("--all")] = False,
    quick: Annotated[bool, typer.Option("--quick")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    target_model = model_id or "coding"
    del all_models, quick
    _execute(
        lambda client: client.benchmark_model(target_model),
        json_output=json_output,
        renderer=_render_benchmark_result,
        error_context=ErrorContext.GENERAL,
    )


@benchmark_app.command("report")
def benchmark_report(
    model_id: Annotated[str | None, typer.Option("--model")] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, max=100)] = 20,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _execute(
        lambda client: client.benchmark_report(model_id=model_id, limit=limit),
        json_output=json_output,
        renderer=_render_benchmark_report,
        error_context=ErrorContext.GENERAL,
    )


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
    output: Annotated[str, typer.Option("--output")] = "text",
) -> None:
    async def watch() -> None:
        async with _client_factory(_socket_path()) as client:
            async for event in client.stream_events(after=after):
                if job_id is None or event.job_id == job_id:
                    if output == "ndjson":
                        typer.echo(
                            json.dumps(
                                event.model_dump(mode="json"),
                                ensure_ascii=False,
                                separators=(",", ":"),
                            )
                        )
                    else:
                        data = event.model_dump(mode="json")
                        ts = data.get("timestamp", 0)
                        kind = data.get("type", "unknown")
                        jid = data.get("job_id", "?")
                        c = "yellow" if "job" in kind else "blue"
                        c = "cyan" if "model" in kind else c
                        c = "red" if "error" in kind.lower() else c
                        _console.print(f"[dim]{ts}[/dim] [{c}]{kind}[/{c}] [dim]job=[/dim]{jid}")

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
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Validate config schema v1 without contacting a daemon or backend."""
    request_id = _request_id()
    selected_path = path or default_config_path()
    try:
        config = load_config(selected_path)
    except ConfigError as exc:
        if json_output:
            _fail_config("configuration validation failed", request_id=request_id, detail=str(exc))
        _console.print(f"[bold red]✖  validation failed[/bold red]  {str(exc)}")
        raise typer.Exit(1) from None

    if json_output:
        _emit_success(
            {"config_schema_version": config.schema_version, "status": "valid"},
            request_id=request_id,
        )
    else:
        v = config.schema_version
        _console.print(f"[bold green]✔  config valid[/bold green]  schema_version={v}")


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
        p = Panel("[green]● running[/green]", title="[bold]com.omlxc.daemon[/bold]", expand=False)
        _console.print(p)


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
        _console.print(
            Panel(
                f"[dim]executable[/dim]  {data['executable']}\n"
                f"[dim]plist[/dim]       {data['plist_path']}\n"
                f"[dim]will_write[/dim]  "
                f"{'[green]yes[/green]' if apply else '[yellow]no[/yellow]'}",
                title="[bold]Install Plan[/bold]",
                expand=False,
            )
        )


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
        _console.print(f"[bold green]✔[/bold green] com.omlxc.daemon {action} succeeded")


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


@daemon_app.command("reload")
def daemon_reload(
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Reload daemon configuration in-place without dropping existing connections."""
    _execute(
        lambda client: client.reload_daemon(),
        json_output=json_output,
        renderer=_render_daemon_reload,
        error_context=ErrorContext.GENERAL,
    )


@app.command("doctor")
def doctor(
    direct: Annotated[bool, typer.Option("--direct")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    if not direct:
        _execute(
            lambda client: client.health(),
            json_output=json_output,
            renderer=_render_status,
            error_context=ErrorContext.STATUS,
        )
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
        mapping = _mapping(data)
        passed = 0
        failed = 0
        table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold #7dd3f5")
        table.add_column("Status")
        table.add_column("Check")

        for k, v in mapping.items():
            if k in ("items", "summary"):
                continue
            vs = str(v).lower()
            if vs in ("ok", "passed", "true"):
                table.add_row("[green]✔[/green]", f"[#c8d8ec]{k}[/#c8d8ec]")
                passed += 1
            elif vs in ("warn", "warning"):
                table.add_row("[yellow]⚠[/yellow]", f"[#c8d8ec]{k}[/#c8d8ec]")
            else:
                table.add_row("[red]✖[/red]", f"[#c8d8ec]{k}[/#c8d8ec]")
                failed += 1

        _console.print(table)
        _console.print(f"\n[bold]{passed} passed, {failed} failed[/bold]")


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
        box=box.SIMPLE_HEAVY,
        header_style="bold #7dd3f5",
        show_edge=False,
        row_styles=["none", "dim"],
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
    return await _select_from_pages(lambda after: client.nodes(after=after, limit=100), identifier, "node")


async def _selected_model(client: DaemonClient, identifier: str) -> DaemonEnvelope:
    """Match by model id or configured alias so users can select canonicalized aliases."""
    return await _select_from_pages(
        lambda after: client.models(after=after, limit=100),
        identifier,
        "model",
        item_matches=lambda item: _selected_model_identifier_matches(item, identifier),
    )


def _selected_model_identifier_matches(item: Mapping[str, JsonValue], identifier: str) -> bool:
    item_id = item.get("id")
    if item_id == identifier:
        return True
    aliases = item.get("aliases")
    if not isinstance(aliases, (list, tuple)):
        return False
    return any(alias == identifier for alias in aliases if isinstance(alias, str))


async def _select_from_pages(
    fetch: PageFetcher,
    identifier: str,
    resource: str,
    *,
    item_matches: Callable[[Mapping[str, JsonValue]], bool] | None = None,
) -> DaemonEnvelope:
    cursor: str | None = None
    seen: set[str] = set()
    request_id = _request_id()

    def default_match(item: Mapping[str, JsonValue]) -> bool:
        return item.get("id") == identifier

    matches = item_matches or default_match
    for _page in range(MAX_LOOKUP_PAGES):
        envelope = await fetch(cursor)
        request_id = envelope.request_id
        for item in _items(envelope.data):
            if matches(item):
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
    if not mapping:
        _console.print("[dim italic]No details available.[/dim italic]")
        return ""

    table = Table(box=None, show_header=False, padding=(0, 2))
    table.add_column("Property", style="#5a7a9a bold")
    table.add_column("Value")

    for key, value in sorted(mapping.items()):
        val_s = _text(value)
        if key == "state":
            val_text = _rich_state(val_s)
        elif isinstance(value, bool):
            val_text = _rich_bool(value)
        else:
            val_text = Text(val_s, style="#c8d8ec")
        table.add_row(key.upper(), val_text)

    _console.print(Panel(table, title="[bold]Details[/bold]", border_style="#1a4d80", expand=False))
    return ""


def _render_job(data: JsonValue | None) -> str:
    """Rich panel for a single job."""
    mapping = _mapping(data)
    state_s = _text(mapping.get("state", "unknown"))

    table = Table(box=None, show_header=False, padding=(0, 2))
    table.add_column("Property", style="#5a7a9a bold")
    table.add_column("Value", style="#c8d8ec")

    table.add_row("KIND", _text(mapping.get("kind")))
    table.add_row("STATE", _rich_state(state_s))
    table.add_row("PROGRESS", _text(mapping.get("progress")))

    _console.print(
        Panel(
            table,
            title=f"[bold #7dd3f5]Job: {_text(mapping.get('id'))}[/bold #7dd3f5]",
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

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="#5a7a9a bold")
    grid.add_column()
    grid.add_row("SELECTED", f"[bold cyan]{selected}[/bold cyan]")
    grid.add_row("FALLBACK", f"[dim]{fallback_text}[/dim]")

    scores = mapping.get("candidate_scores")
    if isinstance(scores, dict) and scores:
        grid.add_row("", "")
        grid.add_row("SCORES", "")
        for pid, sc in scores.items():
            sc_val = f"{float(sc):.3f}" if isinstance(sc, (int, float)) else str(sc)
            prefix = "[bold green]●[/bold green]" if pid == selected else "[dim]○[/dim]"
            grid.add_row(f"  {prefix} {pid}", f"[bold cyan]{sc_val}[/bold cyan]")

    rejected = mapping.get("rejected")
    if isinstance(rejected, dict) and rejected:
        grid.add_row("", "")
        grid.add_row("REJECTED", "")
        for pid, reason in rejected.items():
            grid.add_row(f"  [red]✖[/red] {pid}", f"[dim red]{reason}[/dim red]")

    explanation = mapping.get("explanation")
    if explanation:
        grid.add_row("", "")
        grid.add_row("EXPLANATION", f"[dim]{explanation}[/dim]")

    _console.print(
        Panel(
            grid,
            title="[bold]Route Plan[/bold]",
            border_style="#1a4d80",
            expand=False,
        )
    )
    return ""


def _render_benchmark_result(data: JsonValue | None) -> str:
    mapping = _mapping(data)
    model_id = _text(mapping.get("model_id"))
    placement_id = _text(mapping.get("placement_id"))
    node_id = _text(mapping.get("node_id"))
    ttft_ms = mapping.get("ttft_ms")
    tps = mapping.get("tps")
    cold_load_ms = mapping.get("cold_load_ms")
    warm_load_ms = mapping.get("warm_load_ms")

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="#5a7a9a bold")
    grid.add_column()
    grid.add_row("MODEL", f"[bold cyan]{model_id}[/bold cyan]")
    grid.add_row("PLACEMENT", f"{placement_id} [dim]({node_id})[/dim]")
    grid.add_row("TTFT", f"[bold green]{ttft_ms} ms[/bold green]")
    grid.add_row("THROUGHPUT", f"[bold cyan]{tps} tok/s[/bold cyan]")
    if cold_load_ms is not None:
        grid.add_row("COLD LOAD", f"{cold_load_ms} ms")
    if warm_load_ms is not None:
        grid.add_row("WARM LOAD", f"{warm_load_ms} ms")

    _console.print(
        Panel(
            grid,
            title="[bold]⚡ Benchmark Result[/bold]",
            border_style="#1a4d80",
            expand=False,
        )
    )
    return ""


def _render_benchmark_report(data: JsonValue | None) -> str:
    if isinstance(data, list):
        items = cast(list[dict[str, JsonValue]], data)
    elif isinstance(data, dict):
        raw_items = data.get("items")
        if isinstance(raw_items, list):
            items = cast(list[dict[str, JsonValue]], raw_items)
        else:
            items = [data]
    else:
        items = []

    if not items:
        _console.print("[dim]No benchmark runs recorded yet. Run `omlxc benchmark run` first.[/dim]")
        return ""

    table = Table(
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="#5a7a9a bold",
        border_style="#1a3d60",
    )
    table.add_column("MODEL ID", style="bold")
    table.add_column("PLACEMENT", style="dim")
    table.add_column("NODE")
    table.add_column("TTFT (ms)", justify="right", style="bold green")
    table.add_column("TPS (tok/s)", justify="right", style="bold cyan")
    table.add_column("TESTED AT", justify="right", style="dim")

    for item in items:
        m = _mapping(item)
        tested_at = _text(m.get("tested_at"))
        if "T" in tested_at:
            tested_at = tested_at.split("T")[1][:8]
        ttft = m.get("ttft_ms", 0)
        tps = m.get("tps", 0)
        ttft_str = f"{float(ttft):.1f}" if isinstance(ttft, (int, float)) else str(ttft)
        tps_str = f"{float(tps):.1f}" if isinstance(tps, (int, float)) else str(tps)
        table.add_row(
            _text(m.get("model_id")),
            _text(m.get("placement_id")),
            _text(m.get("node_id")),
            ttft_str,
            tps_str,
            tested_at,
        )

    _console.print(
        Panel(
            table,
            title="[bold]📊 Benchmark Leaderboard[/bold]",
            border_style="#1a4d80",
            expand=False,
        )
    )
    return ""


def _render_daemon_reload(data: JsonValue | None) -> str:
    mapping = _mapping(data)
    status = _text(mapping.get("status", "reloaded"))
    nodes_count = mapping.get("nodes_count", 0)
    models_count = mapping.get("models_count", 0)
    detail = f"(nodes={nodes_count}, models={models_count})"
    _console.print(f"[bold green]✔[/bold green] com.omlxc.daemon {status} {detail}")
    return ""


def _render_status(data: JsonValue | None) -> str:
    """Rich status panel for 'omlxc status'."""
    mapping = _mapping(data)
    status_s = _text(mapping.get("status", "unknown"))
    degraded = mapping.get("degraded", False)
    policy = _text(mapping.get("policy", "interactive"))

    if status_s == "ready" and not degraded:
        sym, style = ("●", "bold green")
        state_label = "HEALTHY"
    else:
        sym, style = ("◑", "bold yellow")
        state_label = "DEGRADED"

    grid = Table.grid(expand=True)
    grid.add_column()
    grid.add_column(justify="right")
    grid.add_row(f"[{style}]{sym} {state_label}[/{style}]", f"[dim]policy:[/dim] {policy}")
    warnings = mapping.get("warnings")
    if isinstance(warnings, list):
        for raw in warnings:
            item = _mapping(raw)
            if _text(item.get("code")) != "inventory_drop":
                continue
            grid.add_row(
                (
                    f"[bold yellow]inventory_drop[/bold yellow] "
                    f"{_text(item.get('node_id'))}/{_text(item.get('backend_id'))} "
                    f"{item.get('baseline')}→{item.get('current')}"
                ),
                "",
            )

    _console.print(
        Panel(
            grid,
            title="[bold #7dd3f5]omlxcd[/bold #7dd3f5]",
            border_style="#5a7a9a",
            expand=False,
        )
    )
    return ""


@fabric_app.command("inspect")
def fabric_inspect(
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Inspect Compute Fabric thermal status, triage capability, and memory estimators."""
    guard = ThermalGuard()
    state = guard.probe()
    estimator = VRAMBudgetEstimator()
    cache = SemanticCacheRegistry()

    payload = {
        "thermal_pressure": state.thermal_level.value,
        "power_source": state.power_source.value,
        "battery_percent": state.battery_percent,
        "penalty_multiplier": state.penalty_multiplier,
        "supported_tiers": ["fast", "standard", "reasoning"],
        "known_arch_profiles": list(estimator.registered_models),
        "cache_stats": cache.get_stats(),
    }

    if json_output:
        _emit_success(payload, request_id=_request_id())
        return

    grid = Table.grid(expand=True)
    grid.add_column()
    grid.add_column(justify="right")
    grid.add_row(
        f"[bold cyan]Thermal Guard[/bold cyan]: {state.thermal_level.value.upper()}",
        f"power: {state.power_source.value} (penalty: {state.penalty_multiplier:.2f}x)",
    )
    grid.add_row(
        ("[bold cyan]Semantic Triage[/bold cyan]: FAST (2B~4B) | STANDARD (9B~14B) | REASONING (27B~70B)"),
        "zero-latency AST classifier",
    )
    grid.add_row(
        (f"[bold cyan]VRAM Estimator[/bold cyan]: {len(estimator.registered_models)} architectures registered"),
        "dynamic KV cache budgeting",
    )
    grid.add_row(
        "[bold cyan]Two-Tier Cache[/bold cyan]: L1 Prefix-Hash + L2 Semantic Invariant",
        "LRU capacity bounded",
    )

    _console.print(
        Panel(
            grid,
            title="[bold #7dd3f5]omlxc Compute Fabric[/bold #7dd3f5]",
            border_style="#5a7a9a",
            expand=False,
        )
    )


@fabric_app.command("triage")
def fabric_triage(
    prompt: Annotated[str, typer.Argument(help="Prompt text to classify")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Classify prompt complexity tier (FAST / STANDARD / REASONING)."""
    classifier = TriageClassifier()
    msg = (ChatMessage(role="user", content=prompt),)
    # Estimate token count as words * 1.3
    est_tokens = int(len(prompt.split()) * 1.3)
    result = classifier.classify(messages=msg, context_tokens=est_tokens)

    payload = {
        "tier": result.tier.value,
        "confidence": result.confidence,
        "reason": result.reason,
        "heuristic_matched": result.heuristic_matched,
        "estimated_tokens": est_tokens,
    }

    if json_output:
        _emit_success(payload, request_id=_request_id())
        return

    if result.tier.value == "fast":
        color = "green"
    elif result.tier.value == "standard":
        color = "yellow"
    else:
        color = "magenta"

    _console.print(
        Panel(
            f"Tier: [bold {color}]{result.tier.value.upper()}[/bold {color}]\n"
            f"Confidence: [cyan]{result.confidence * 100:.0f}%[/cyan]\n"
            f"Reason: [dim]{result.reason}[/dim]",
            title="[bold #7dd3f5]Intent Triage Result[/bold #7dd3f5]",
            border_style="#5a7a9a",
            expand=False,
        )
    )


@fabric_app.command("vram")
def fabric_vram(
    model_id: Annotated[str, typer.Argument(help="Model identifier")],
    tokens: Annotated[int, typer.Argument(help="Context tokens count")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Estimate dynamic KV Cache and total VRAM footprint for a given context length."""
    estimator = VRAMBudgetEstimator()
    kv_mb = estimator.estimate_kv_cache_mb(model_id, tokens)
    total_mb = estimator.estimate_total_vram_mb(model_id, tokens)
    profile = estimator.get_profile(model_id)

    payload = {
        "model_id": model_id,
        "context_tokens": tokens,
        "kv_cache_mb": kv_mb,
        "weights_vram_mb": profile.weights_vram_mb,
        "total_estimated_vram_mb": total_mb,
        "bytes_per_token": profile.bytes_per_token,
    }

    if json_output:
        _emit_success(payload, request_id=_request_id())
        return

    arch_info = f"({profile.num_layers}L / {profile.num_kv_heads}KV / {profile.head_dim}D)"
    ctx_info = f"{tokens:,} tokens ({profile.bytes_per_token:,} bytes/token)"
    _console.print(
        Panel(
            f"Model: [bold cyan]{model_id}[/bold cyan] {arch_info}\n"
            f"Context: [bold]{ctx_info}[/bold]\n"
            f"KV Cache: [bold yellow]{kv_mb:,.1f} MB[/bold yellow]\n"
            f"Base Weights: [dim]{profile.weights_vram_mb:,.1f} MB[/dim]\n"
            f"Total Est. VRAM: [bold green]{total_mb:,.1f} MB[/bold green]",
            title="[bold #7dd3f5]VRAM Budget Estimation[/bold #7dd3f5]",
            border_style="#5a7a9a",
            expand=False,
        )
    )


@fabric_app.command("warm")
def fabric_warm(
    model_id: Annotated[str, typer.Option("--model", "-m", help="Target model identifier")] = "coding",
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Pre-warm high-frequency system prompt prefixes into cache registry to achieve 0ms TTFT."""
    from omlxc.dataplane.semantic_cache import SemanticCacheRegistry, warm_system_prefixes

    registry = SemanticCacheRegistry()
    res = warm_system_prefixes(registry, model_id=model_id)

    if json_output:
        _emit_success(res, request_id=_request_id())
        return

    prefix_names = ", ".join(res["prefixes"])
    tokens_saved = res["estimated_saved_tokens"]
    _console.print(
        Panel(
            f"Model: [bold cyan]{model_id}[/bold cyan]\n"
            f"Warmed Prefixes: [bold green]{res['warmed_count']}[/bold green] ({prefix_names})\n"
            f"Estimated Token Savings: [bold yellow]{tokens_saved:,} tokens[/bold yellow]\n"
            f"Status: [bold green]✔ Prefix Cache Ready (0ms TTFT)[/bold green]",
            title="[bold #7dd3f5]System Prefix Warmer[/bold #7dd3f5]",
            border_style="#5a7a9a",
            expand=False,
        )
    )


@fabric_app.command("compact")
def fabric_compact(
    model_id: Annotated[str, typer.Option("--model", "-m", help="Target model identifier")] = "coding",
    context_tokens: Annotated[int, typer.Option("--tokens", "-t", help="Current context token size")] = 32768,
    available_mb: Annotated[float, typer.Option("--available-mb", "-a", help="Available node VRAM in MB")] = 8192.0,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Evaluate context compaction and simulate sliding-window memory self-healing."""
    from omlxc.dataplane.vram_budget import ContextCompactor, VRAMBudgetEstimator

    estimator = VRAMBudgetEstimator()
    admission = estimator.check_headroom_admission(
        model_id=model_id,
        context_tokens=context_tokens,
        available_node_vram_mb=available_mb,
    )

    # Scale simulated message content to match requested context_tokens load
    chunk = "context details specifications "
    multiplier = max(1, context_tokens // 4)
    user_payload = f"Task goal specification with {context_tokens} tokens load: " + (chunk * multiplier)
    sample_messages = [
        {"role": "system", "content": "You are a coding assistant with full compute fabric."},
        {"role": "user", "content": user_payload},
        {"role": "assistant", "content": "Executing task step 1: initial AST triage."},
        {"role": "user", "content": "Proceed with step 2 implementation."},
        {"role": "assistant", "content": "Implemented step 2 with unit tests and type checks."},
        {"role": "user", "content": "Final verification and benchmark."},
        {"role": "assistant", "content": "Verification succeeded with 100% pass rate."},
    ]

    target_tokens = admission.max_safe_tokens if admission.compaction_advised else context_tokens
    compaction = ContextCompactor.compact_messages(
        sample_messages,
        target_safe_tokens=target_tokens,
    )

    payload = {
        "model_id": model_id,
        "admitted": admission.admitted,
        "estimated_kv_mb": admission.estimated_kv_mb,
        "compaction_advised": admission.compaction_advised,
        "max_safe_tokens": admission.max_safe_tokens,
        "recommended_compaction_ratio": admission.recommended_compaction_ratio,
        "original_tokens": compaction.original_tokens,
        "compacted_tokens": compaction.compacted_tokens,
        "pruned_tokens": compaction.pruned_tokens,
        "compression_ratio": compaction.compression_ratio,
        "distilled_summary": compaction.distilled_summary,
    }

    if json_output:
        _emit_success(payload, request_id=_request_id())
        return

    status_str = (
        "[bold red]Compaction Advised (KV Cache Exceeds Budget)[/bold red]"
        if admission.compaction_advised
        else "[bold green]Safe Headroom (No Compaction Needed)[/bold green]"
    )
    ratio_pct = compaction.compression_ratio * 100
    summary_txt = compaction.distilled_summary or "Full context retained intact"
    _console.print(
        Panel(
            f"Model: [bold cyan]{model_id}[/bold cyan] | Context: [bold]{context_tokens:,}[/bold] "
            f"tokens | Free VRAM: [bold]{available_mb:,.1f}[/bold] MB\n"
            f"Status: {status_str}\n"
            f"Max Safe Tokens: [bold yellow]{admission.max_safe_tokens:,}[/bold yellow] tokens\n"
            f"Compression Ratio: [bold yellow]{ratio_pct:.1f}%[/bold yellow] "
            f"(Pruned {compaction.pruned_tokens:,} tokens)\n"
            f"Summary: [dim]{summary_txt}[/dim]",
            title="[bold #7dd3f5]Context Window Compactor & Memory Self-Healing[/bold #7dd3f5]",
            border_style="#5a7a9a",
            expand=False,
        )
    )


def main() -> None:
    """Run the ``omlxc`` console script."""
    app()


if __name__ == "__main__":
    main()
