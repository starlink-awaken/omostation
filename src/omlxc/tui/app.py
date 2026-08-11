"""Textual compute cockpit backed exclusively by the typed daemon client."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, Self, cast

from pydantic import JsonValue
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.events import Resize
from textual.widgets import ContentSwitcher, Label, ListItem, ListView, Static

from omlxc.client import DaemonClient, DaemonClientError, DaemonEnvelope, DaemonEvent

from .screens import CommandScreen, ConfirmationScreen, HelpScreen, JumpScreen, SearchScreen

PAGE_SLUGS = (
    "overview",
    "nodes",
    "models",
    "routes",
    "jobs",
    "performance",
    "logs",
    "settings",
)
PAGE_TITLES = {
    "overview": "总览 · Overview",
    "nodes": "节点 · Nodes",
    "models": "模型 · Models",
    "routes": "路由 · Routes",
    "jobs": "任务 · Jobs",
    "performance": "性能 · Performance",
    "logs": "日志 · Logs",
    "settings": "设置 · Settings",
}

JsonObject = dict[str, JsonValue]


class CockpitClient(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(self, *_exc: object) -> None: ...

    async def health(self) -> DaemonEnvelope: ...

    async def nodes(self, *, after: str | None = None, limit: int = 100) -> DaemonEnvelope: ...

    async def models(self, *, after: str | None = None, limit: int = 100) -> DaemonEnvelope: ...

    async def jobs(self, *, after: str | None = None, limit: int = 100) -> DaemonEnvelope: ...

    async def metrics(self) -> DaemonEnvelope: ...

    async def load_model(self, model_id: str) -> DaemonEnvelope: ...

    async def unload_model(self, model_id: str) -> DaemonEnvelope: ...

    async def cancel_job(self, job_id: str) -> DaemonEnvelope: ...

    def stream_events(self, *, after: int = 0) -> AsyncIterator[DaemonEvent]: ...


ClientFactory = Callable[[], CockpitClient]


@dataclass(slots=True)
class CockpitSnapshot:
    health: JsonObject = field(default_factory=lambda: {})
    nodes: tuple[JsonObject, ...] = ()
    models: tuple[JsonObject, ...] = ()
    jobs: tuple[JsonObject, ...] = ()
    metrics: JsonObject = field(default_factory=lambda: {})


@dataclass(frozen=True, slots=True)
class PendingMutation:
    operation: str
    resource_id: str
    action: str
    impact: str
    rollback: str


class CockpitPage(Static):
    """A consistent textual page shell; networking stays in ``CockpitApp``."""

    def __init__(self, slug: str) -> None:
        self.slug = slug
        super().__init__(PAGE_TITLES[slug], id=f"page-{slug}", classes="cockpit-page")


class CockpitApp(App[None]):
    """Keyboard-first local compute dashboard with explicit freshness state."""

    TITLE = "omlxc · Local Compute Hub"
    BINDINGS = [
        Binding("g", "quick_jump", "Jump"),
        Binding("slash", "search", "Search"),
        Binding("colon", "command_palette", "Command"),
        Binding("r", "refresh", "Refresh"),
        Binding("question_mark", "show_help", "Help"),
        Binding("q", "quit", "Quit"),
        Binding("escape", "escape_overlay", "Close", show=False),
    ]
    CSS = """
    Screen {
        background: #0b1018;
        color: #dce7f5;
    }
    #topbar {
        height: 3;
        padding: 1 2;
        background: #142236;
        color: #f2f7ff;
        text-style: bold;
    }
    #body {
        height: 1fr;
    }
    #nav {
        width: 24;
        min-width: 18;
        border-right: solid #294361;
        background: #101a28;
    }
    #nav ListItem {
        padding: 0 1;
    }
    #nav ListItem.--highlight {
        background: #23466d;
    }
    #pages {
        width: 1fr;
        height: 1fr;
    }
    .cockpit-page {
        width: 1fr;
        height: 1fr;
        padding: 1 2;
        border-top: solid #294361;
    }
    #footerbar {
        height: 3;
        padding: 1 2;
        background: #101a28;
        color: #a9bdd4;
    }
    .narrow #nav {
        display: none;
    }
    .narrow #topbar, .narrow #footerbar, .narrow .cockpit-page {
        padding-left: 1;
        padding-right: 1;
    }
    """

    def __init__(
        self,
        *,
        socket_path: Path | None = None,
        client_factory: ClientFactory | None = None,
        reconnect_delays: tuple[float, ...] = (0.25, 0.5, 1.0, 2.0),
    ) -> None:
        super().__init__()
        if not reconnect_delays or any(delay <= 0 for delay in reconnect_delays):
            raise ValueError("reconnect delays must be positive")
        selected_socket = socket_path or Path("/tmp/omlxc/omlxcd.sock")
        self._client_factory: ClientFactory = client_factory or (
            lambda: DaemonClient(selected_socket)
        )
        self._reconnect_delays = reconnect_delays
        self.snapshot = CockpitSnapshot()
        self.connection_state = "CONNECTING"
        self.policy = "interactive"
        self.event_cursor = 0
        self.last_event_kind: str | None = None
        self._event_log: list[str] = []
        self._pending_mutation: PendingMutation | None = None

    def compose(self) -> ComposeResult:
        yield Static("omlxc · CONNECTING · interactive", id="topbar")
        with Horizontal(id="body"):
            yield ListView(
                *(ListItem(Label(PAGE_TITLES[slug]), id=f"nav-{slug}") for slug in PAGE_SLUGS),
                id="nav",
            )
            yield ContentSwitcher(
                *(CockpitPage(slug) for slug in PAGE_SLUGS),
                initial="page-overview",
                id="pages",
            )
        yield Static("g 跳转 · / 搜索 · : 命令 · r 刷新 · ? 帮助 · q 退出", id="footerbar")

    def on_mount(self) -> None:
        self._set_narrow(self.size.width < 80 or self.size.height < 24)
        self._render_snapshot()
        self.run_worker(
            self._connection_loop(),
            name="daemon-events",
            group="daemon",
            exclusive=True,
            exit_on_error=False,
        )

    def on_resize(self, event: Resize) -> None:
        self._set_narrow(event.size.width < 80 or event.size.height < 24)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item.id is not None and event.item.id.startswith("nav-"):
            self.show_page(event.item.id.removeprefix("nav-"))

    def show_page(self, slug: str) -> None:
        if slug not in PAGE_SLUGS:
            raise ValueError("unknown cockpit page")
        self.query_one(ContentSwitcher).current = f"page-{slug}"
        nav = self.query_one("#nav", ListView)
        nav.index = PAGE_SLUGS.index(slug)

    def action_quick_jump(self) -> None:
        self.push_screen(JumpScreen(), self._jump_to)

    def _jump_to(self, slug: str | None) -> None:
        if slug is not None:
            self.show_page(slug)

    def action_search(self) -> None:
        self.push_screen(SearchScreen())

    def action_command_palette(self) -> None:
        self.push_screen(CommandScreen(), self._command_submitted)

    def _command_submitted(self, command: str | None) -> None:
        if command is None:
            return
        parts = command.split()
        if len(parts) != 2 or parts[0] not in {"load", "unload", "cancel"}:
            self._event_log.append("command rejected: use load/unload MODEL or cancel JOB")
            self._render_snapshot()
            return
        operation, resource_id = parts
        if operation == "load":
            mutation = PendingMutation(
                operation,
                resource_id,
                f"load {resource_id}",
                "Loads the model into backend memory.",
                "Unload the same model placement.",
            )
        elif operation == "unload":
            mutation = PendingMutation(
                operation,
                resource_id,
                f"unload {resource_id}",
                "Releases the model and may affect queued requests.",
                "Load the same model placement again.",
            )
        else:
            mutation = PendingMutation(
                operation,
                resource_id,
                f"cancel {resource_id}",
                "Requests cancellation of a durable job.",
                "Submit a new job if cancellation completes.",
            )
        self._pending_mutation = mutation
        self.push_screen(
            ConfirmationScreen(
                action=mutation.action,
                risk="R1",
                impact=mutation.impact,
                rollback=mutation.rollback,
            ),
            self._mutation_confirmed,
        )

    def _mutation_confirmed(self, confirmed: bool | None) -> None:
        mutation, self._pending_mutation = self._pending_mutation, None
        if not confirmed or mutation is None:
            return
        self.run_worker(
            self._execute_mutation(mutation),
            name="confirmed-mutation",
            group="mutation",
            exclusive=True,
            exit_on_error=False,
        )

    async def _execute_mutation(self, mutation: PendingMutation) -> None:
        try:
            async with self._client_factory() as client:
                if mutation.operation == "load":
                    result = await client.load_model(mutation.resource_id)
                elif mutation.operation == "unload":
                    result = await client.unload_model(mutation.resource_id)
                else:
                    result = await client.cancel_job(mutation.resource_id)
                data = _object(result.data)
                self._event_log.append(
                    f"command accepted: {mutation.action} job={data.get('id', '-')}"
                )
                await self._load_snapshot(client)
        except asyncio.CancelledError:
            raise
        except (DaemonClientError, OSError, ValueError):
            self._event_log.append(f"command failed: {mutation.action}")
            self._render_snapshot()

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_refresh(self) -> None:
        self.run_worker(
            self._refresh_once(),
            name="manual-refresh",
            group="refresh",
            exclusive=True,
            exit_on_error=False,
        )

    def action_escape_overlay(self) -> None:
        if self.screen is not self.screen_stack[0]:
            self.pop_screen()

    async def _connection_loop(self) -> None:
        attempt = 0
        while True:
            try:
                async with self._client_factory() as client:
                    await self._load_snapshot(client)
                    self._set_connection_state("LIVE")
                    attempt = 0
                    async for event in client.stream_events(after=self.event_cursor):
                        self._apply_event(event)
                self._set_connection_state("STALE")
            except asyncio.CancelledError:
                raise
            except (DaemonClientError, OSError, ValueError):
                self._set_connection_state("STALE")
            delay = self._reconnect_delays[min(attempt, len(self._reconnect_delays) - 1)]
            attempt += 1
            await asyncio.sleep(delay)

    async def _refresh_once(self) -> None:
        try:
            async with self._client_factory() as client:
                await self._load_snapshot(client)
            self._set_connection_state("LIVE")
        except asyncio.CancelledError:
            raise
        except (DaemonClientError, OSError, ValueError):
            self._set_connection_state("STALE")

    async def _load_snapshot(self, client: CockpitClient) -> None:
        health, nodes, models, jobs, metrics = await asyncio.gather(
            client.health(),
            client.nodes(),
            client.models(),
            client.jobs(),
            client.metrics(),
        )
        health_data = _object(health.data)
        self.snapshot = CockpitSnapshot(
            health=health_data,
            nodes=_page_items(nodes.data),
            models=_page_items(models.data),
            jobs=_page_items(jobs.data),
            metrics=_object(metrics.data),
        )
        policy = health_data.get("policy")
        self.policy = str(policy) if isinstance(policy, str) else "interactive"
        self._render_snapshot()

    def _apply_event(self, event: DaemonEvent) -> None:
        if event.cursor is not None:
            self.event_cursor = max(self.event_cursor, event.cursor)
        self.last_event_kind = event.kind
        self._merge_known_event(event)
        label = f"{event.timestamp.isoformat()}  {event.kind}"
        if event.job_id is not None:
            label += f"  job={event.job_id}"
        self._event_log.append(label)
        del self._event_log[:-50]
        self._render_snapshot()

    def _merge_known_event(self, event: DaemonEvent) -> None:
        payload = _event_payload(event.payload)
        family, _, state = event.kind.partition(".")
        if family == "node":
            identifier = event.resource_id or _event_identifier(payload, "node_id", "id")
            if identifier is None:
                return
            nodes = _merge_resource(self.snapshot.nodes, identifier, payload, health=True)
            self.snapshot = _snapshot_with(self.snapshot, nodes=nodes)
            return
        if family == "model":
            identifier = event.resource_id or _event_identifier(payload, "model_id", "id")
            if identifier is None:
                return
            changes = dict(payload)
            if state == "loaded":
                changes.setdefault("loaded", True)
            elif state == "unloaded":
                changes.setdefault("loaded", False)
            models = _merge_resource(self.snapshot.models, identifier, changes)
            self.snapshot = _snapshot_with(self.snapshot, models=models)
            return
        if family == "job":
            identifier = (
                event.job_id or event.resource_id or _event_identifier(payload, "job_id", "id")
            )
            if identifier is None:
                return
            changes = dict(payload)
            if state in {
                "pending",
                "planning",
                "awaiting_confirmation",
                "running",
                "succeeded",
                "failed",
                "cancelling",
                "cancelled",
            }:
                changes.setdefault("state", state)
            jobs = _merge_resource(self.snapshot.jobs, identifier, changes)
            self.snapshot = _snapshot_with(self.snapshot, jobs=jobs)
            return
        if family in {"metric", "metrics"}:
            metrics = dict(self.snapshot.metrics)
            metrics.update(payload)
            self.snapshot = _snapshot_with(self.snapshot, metrics=metrics)

    def _set_connection_state(self, state: str) -> None:
        self.connection_state = state
        self._render_snapshot()

    def _set_narrow(self, narrow: bool) -> None:
        self.set_class(narrow, "narrow")

    def _render_snapshot(self) -> None:
        active_jobs = sum(
            item.get("state") in {"pending", "planning", "running", "cancelling"}
            for item in self.snapshot.jobs
        )
        self.query_one("#topbar", Static).update(
            f"omlxc · {self.connection_state} · policy {self.policy} · active jobs {active_jobs}"
        )
        for slug in PAGE_SLUGS:
            self.query_one(f"#page-{slug}", CockpitPage).update(self._page_text(slug))

    def _page_text(self, slug: str) -> str:
        title = PAGE_TITLES[slug]
        prefix = f"[b]{title}[/b]\nSTATE {self.connection_state}\n"
        if slug == "overview":
            health = self.snapshot.health.get("status", "unknown")
            return (
                prefix
                + f"\nDaemon {health}\nNodes {len(self.snapshot.nodes)}\n"
                + f"Models {len(self.snapshot.models)}\nJobs {len(self.snapshot.jobs)}"
            )
        if slug == "nodes":
            return (
                prefix
                + "\n"
                + _rows(self.snapshot.nodes, ("id", "display_name", "platform", "state"))
            )
        if slug == "models":
            return prefix + "\n" + _rows(self.snapshot.models, ("id", "role", "loaded", "state"))
        if slug == "routes":
            return prefix + f"\nPolicy {self.policy}\nPhysical placement is explained by omlxcd."
        if slug == "jobs":
            event = self.last_event_kind or "none"
            return (
                prefix
                + f"\nLast event {event}\n"
                + _rows(self.snapshot.jobs, ("id", "kind", "state", "progress"))
            )
        if slug == "performance":
            return prefix + "\n" + _key_values(self.snapshot.metrics)
        if slug == "logs":
            return prefix + "\n" + ("\n".join(self._event_log[-12:]) or "No events yet.")
        return prefix + f"\nDefault policy {self.policy}\nThinking OFF by default."


def _object(value: JsonValue | None) -> JsonObject:
    if not isinstance(value, dict):
        raise ValueError("expected object response")
    return cast(JsonObject, value)


def _page_items(value: JsonValue | None) -> tuple[JsonObject, ...]:
    items = _object(value).get("items")
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise ValueError("expected paginated object items")
    return tuple(cast(list[JsonObject], items))


def _rows(items: tuple[JsonObject, ...], columns: tuple[str, ...]) -> str:
    header = "  ".join(column.upper() for column in columns)
    rows = ["  ".join(str(_row_value(item, column)) for column in columns) for item in items]
    return "\n".join((header, *rows)) if rows else f"{header}\n(no items)"


def _row_value(item: JsonObject, column: str) -> JsonValue:
    if column == "state" and "state" not in item:
        health = item.get("health")
        if isinstance(health, dict):
            return cast(JsonObject, health).get("state", "-")
    return item.get(column, "-")


def _event_payload(value: JsonValue) -> JsonObject:
    return cast(JsonObject, value) if isinstance(value, dict) else {}


def _event_identifier(payload: JsonObject, *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _merge_resource(
    items: tuple[JsonObject, ...],
    identifier: str,
    changes: JsonObject,
    *,
    health: bool = False,
) -> tuple[JsonObject, ...]:
    result: list[JsonObject] = []
    matched = False
    for item in items:
        if item.get("id") != identifier:
            result.append(item)
            continue
        result.append(_merged_item(item, identifier, changes, health=health))
        matched = True
    if not matched:
        result.append(_merged_item({"id": identifier}, identifier, changes, health=health))
    return tuple(result)


def _merged_item(
    item: JsonObject,
    identifier: str,
    changes: JsonObject,
    *,
    health: bool,
) -> JsonObject:
    merged = dict(item)
    merged["id"] = identifier
    ignored = {"id", "node_id", "model_id", "job_id"}
    if not health:
        merged.update({key: value for key, value in changes.items() if key not in ignored})
        return merged
    health_keys = {"state", "stale", "detail", "observed_at"}
    health_update = {key: value for key, value in changes.items() if key in health_keys}
    nested = changes.get("health")
    if isinstance(nested, dict):
        health_update.update(cast(JsonObject, nested))
    existing = merged.get("health")
    current_health = dict(cast(JsonObject, existing)) if isinstance(existing, dict) else {}
    current_health.update(health_update)
    merged["health"] = current_health
    merged.update(
        {
            key: value
            for key, value in changes.items()
            if key not in ignored | health_keys | {"health"}
        }
    )
    return merged


def _snapshot_with(
    snapshot: CockpitSnapshot,
    *,
    nodes: tuple[JsonObject, ...] | None = None,
    models: tuple[JsonObject, ...] | None = None,
    jobs: tuple[JsonObject, ...] | None = None,
    metrics: JsonObject | None = None,
) -> CockpitSnapshot:
    return CockpitSnapshot(
        health=snapshot.health,
        nodes=snapshot.nodes if nodes is None else nodes,
        models=snapshot.models if models is None else models,
        jobs=snapshot.jobs if jobs is None else jobs,
        metrics=snapshot.metrics if metrics is None else metrics,
    )


def _key_values(values: JsonObject) -> str:
    if not values:
        return "No metrics yet."
    return "\n".join(f"{key.upper()} {value}" for key, value in sorted(values.items()))
