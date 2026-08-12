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
    render_sections,
    status_sections,
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
from .diagnostics import run_direct_doctor
from .domain import EXIT_CONFIG, ErrorEnvelope, error_exit_code
from .service import (
    LaunchdController,
    LaunchdFailure,
    LaunchdPaths,
    build_launchd_plan,
)

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
            typer.echo(renderer(envelope.data))
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
    _execute(
        lambda client: client.health(),
        json_output=json_output,
        renderer=lambda data: render_sections(status_sections(data)),
        error_context=ErrorContext.STATUS,
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
        return render_sections(status_sections(data))
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
            _fail_local(
                "E100", "guide input is invalid", json_output=False, context=ErrorContext.GUIDE
            )

        state = transition.next_state
        request = transition.request
        if request is None:
            continue
        if request.operation is GuideOperation.LIFECYCLE_HELP:
            try:
                typer.echo(render_lifecycle_help(_guide_argument(request)))
            except ValueError:
                _fail_local(
                    "E100", "guide input is invalid", json_output=False, context=ErrorContext.GUIDE
                )
            return

        guide_request = request
        try:
            envelope = asyncio.run(
                _call_daemon(
                    lambda client, guide_request=guide_request: _guide_operation(
                        client, guide_request
                    )
                )
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
        _execute(
            lambda client: client.health(),
            json_output=json_output,
            renderer=lambda data: render_sections(status_sections(data)),
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
    items = _items(data)
    header = "  ".join(column.upper() for column in columns)
    rows = ["  ".join(_text(_nested(item, column)) for column in columns) for item in items]
    return "\n".join((header, *rows)) if rows else f"{header}\n(no items)"


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
    mapping = _mapping(data)
    return "\n".join(f"{key.upper()} {_text(value)}" for key, value in sorted(mapping.items()))


def _render_job(data: JsonValue | None) -> str:
    mapping = _mapping(data)
    return (
        f"JOB {_text(mapping.get('id'))}\n"
        f"KIND {_text(mapping.get('kind'))}\n"
        f"STATE {_text(mapping.get('state'))}\n"
        f"PROGRESS {_text(mapping.get('progress'))}"
    )


def _render_route(data: JsonValue | None) -> str:
    mapping = _mapping(data)
    selected = _text(mapping.get("selected_placement_id"))
    fallback = mapping.get("fallback_chain")
    fallback_text = ", ".join(map(str, fallback)) if isinstance(fallback, list) else "-"
    return f"SELECTED {selected}\nFALLBACK {fallback_text}"


def main() -> None:
    """Run the ``omlxc`` console script."""
    app()


if __name__ == "__main__":
    main()
