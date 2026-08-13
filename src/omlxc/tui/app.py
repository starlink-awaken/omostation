"""Textual compute cockpit backed exclusively by the typed daemon client."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, Self, cast

from pydantic import JsonValue
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.coordinate import Coordinate
from textual.events import Resize
from textual.widget import Widget
from textual.widgets import (
    ContentSwitcher,
    DataTable,
    Footer,
    Header,
    Label,
    ListItem,
    ListView,
    Static,
)

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
    "overview": "总览",
    "nodes": "节点",
    "models": "模型",
    "routes": "路由",
    "jobs": "任务",
    "performance": "性能",
    "logs": "日志",
    "settings": "设置",
}
PAGE_ICONS = {
    "overview": "⬡",
    "nodes": "◈",
    "models": "⬢",
    "routes": "⟡",
    "jobs": "⟳",
    "performance": "◬",
    "logs": "≡",
    "settings": "✦",
}

# Status → (symbol, color-markup)
STATE_ICONS: dict[str, tuple[str, str]] = {
    "healthy": ("●", "green"),
    "online": ("●", "green"),
    "ok": ("●", "green"),
    "loaded": ("◆", "cyan"),
    "running": ("▶", "yellow"),
    "planning": ("◌", "yellow"),
    "pending": ("○", "bright_black"),
    "awaiting_confirmation": ("?", "yellow"),
    "cancelling": ("◐", "magenta"),
    "succeeded": ("✔", "green"),
    "failed": ("✖", "red"),
    "cancelled": ("⊘", "bright_black"),
    "degraded": ("◑", "yellow"),
    "offline": ("○", "bright_black"),
    "stale": ("◌", "bright_black"),
    "unknown": ("·", "bright_black"),
}

JsonObject = dict[str, JsonValue]


def _state_markup(state: str) -> str:
    sym, color = STATE_ICONS.get(state.lower(), ("·", "bright_black"))
    return f"[{color}]{sym} {state}[/{color}]"


def _bool_markup(value: object) -> str:
    if value is True:
        return "[green]yes[/green]"
    if value is False:
        return "[red]no[/red]"
    return "[bright_black]-[/bright_black]"


def _cell(value: object) -> str:
    if value is None or value == "-":
        return "[bright_black]—[/bright_black]"
    if isinstance(value, bool):
        return _bool_markup(value)
    s = str(value)
    if s in STATE_ICONS:
        return _state_markup(s)
    return s


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


# ─── Overview page ────────────────────────────────────────────────────────────


class OverviewPage(Static):
    """Animated summary card grid."""

    DEFAULT_CSS = """
    OverviewPage {
        layout: grid;
        grid-size: 2 3;
        grid-gutter: 1 2;
        padding: 1 2;
        height: 1fr;
        width: 1fr;
    }
    OverviewPage .stat-card {
        background: #0d1f35;
        border: solid #1c3a5e;
        padding: 1 2;
        height: 7;
    }
    OverviewPage .stat-card .stat-value {
        text-style: bold;
        color: #7dd3f5;
        margin-top: 1;
    }
    OverviewPage .stat-card .stat-label {
        color: #5a7a9a;
        text-style: italic;
    }
    OverviewPage .stat-footer {
        column-span: 2;
        text-align: right;
        color: #5a7a9a;
        margin-top: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__(id="page-overview", classes="cockpit-page")

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("[bright_black]daemon[/bright_black]", classes="stat-label"),
            Label("—", id="ov-daemon", classes="stat-value"),
            classes="stat-card",
        )
        yield Vertical(
            Label("[bright_black]nodes[/bright_black]", classes="stat-label"),
            Label("—", id="ov-nodes", classes="stat-value"),
            classes="stat-card",
        )
        yield Vertical(
            Label("[bright_black]models[/bright_black]", classes="stat-label"),
            Label("—", id="ov-models", classes="stat-value"),
            classes="stat-card",
        )
        yield Vertical(
            Label("[bright_black]active jobs[/bright_black]", classes="stat-label"),
            Label("—", id="ov-jobs", classes="stat-value"),
            classes="stat-card",
        )
        yield Label("Last refresh: —", id="ov-last-refresh", classes="stat-footer")

    def refresh_data(self, snapshot: CockpitSnapshot, conn: str, last_update: str) -> None:
        status = str(snapshot.health.get("status", "unknown"))
        active = sum(
            item.get("state") in {"pending", "planning", "running", "cancelling"}
            for item in snapshot.jobs
        )
        sym, color = STATE_ICONS.get(status.lower(), ("·", "bright_black"))
        self.query_one("#ov-daemon", Label).update(f"[{color}]{sym}  {status}[/{color}]")
        daemon_card = self.query_one("#ov-daemon").parent
        if daemon_card is None:
            return
        card = cast(Widget, daemon_card)
        if status.lower() not in ("healthy", "online", "ok"):
            card.set_styles("border: solid red;")
        else:
            card.set_styles("border: solid #1c3a5e;")
        self.query_one("#ov-nodes", Label).update(f"[cyan]{len(snapshot.nodes)}[/cyan]")
        self.query_one("#ov-models", Label).update(f"[cyan]{len(snapshot.models)}[/cyan]")
        job_color = "yellow" if active else "bright_black"
        self.query_one("#ov-jobs", Label).update(f"[{job_color}]{active}[/{job_color}]")

        self.query_one("#ov-last-refresh", Label).update(f"[dim]Last refresh: {last_update}[/dim]")


# ─── Table pages ──────────────────────────────────────────────────────────────


class TablePage(Static):
    """A page backed by a DataTable widget."""

    COLUMNS: tuple[str, ...] = ()
    COLUMN_LABELS: tuple[str, ...] = ()

    def __init__(self, slug: str) -> None:
        self.slug = slug
        super().__init__(id=f"page-{slug}", classes="cockpit-page")

    def compose(self) -> ComposeResult:
        yield DataTable(id=f"dt-{self.slug}", zebra_stripes=True, cursor_type="row")
        yield Label(f"No {self.slug}", id=f"empty-{self.slug}", classes="empty-state")

    def on_mount(self) -> None:
        table = cast(DataTable[str], self.query_one(DataTable))
        table.add_columns(*self.COLUMN_LABELS)

    def _sync_rows(self, rows: list[tuple[str, ...]]) -> None:
        table = cast(DataTable[str], self.query_one(DataTable))
        empty_lbl = self.query_one(f"#empty-{self.slug}", Label)
        if not rows:
            table.display = False
            empty_lbl.display = True
        else:
            table.display = True
            empty_lbl.display = False
            table.clear()
            for row in rows:
                table.add_row(*row)


class NodesPage(TablePage):
    COLUMNS = ("id", "display_name", "platform", "state")
    COLUMN_LABELS = ("  ID", "  DISPLAY NAME", "  PLATFORM", "  STATE")

    def __init__(self) -> None:
        super().__init__("nodes")

    def refresh_data(self, snapshot: CockpitSnapshot) -> None:
        rows = [
            (
                _cell(item.get("id")),
                _cell(item.get("display_name")),
                _cell(item.get("platform")),
                _state_markup(
                    str(
                        cast(JsonObject, item.get("health", {})).get("state", "unknown")
                        if isinstance(item.get("health"), dict)
                        else item.get("state", "unknown")
                    )
                ),
            )
            for item in snapshot.nodes
        ]
        self._sync_rows(rows)


class ModelsPage(TablePage):
    COLUMNS = ("id", "role", "loaded", "state")
    COLUMN_LABELS = ("  ID", "  ROLE", "  LOADED", "  STATE")

    def __init__(self) -> None:
        super().__init__("models")

    def refresh_data(self, snapshot: CockpitSnapshot) -> None:
        rows = [
            (
                _cell(item.get("id")),
                _cell(item.get("role")),
                _bool_markup(item.get("loaded")),
                _state_markup(str(item.get("state", "unknown"))),
            )
            for item in snapshot.models
        ]
        self._sync_rows(rows)


class JobsPage(TablePage):
    COLUMNS = ("id", "kind", "state", "progress")
    COLUMN_LABELS = ("  ID", "  KIND", "  STATE", "  PROGRESS")

    def __init__(self) -> None:
        super().__init__("jobs")

    def refresh_data(self, snapshot: CockpitSnapshot) -> None:
        rows = [
            (
                _cell(item.get("id")),
                _cell(item.get("kind")),
                _state_markup(str(item.get("state", "unknown"))),
                _cell(item.get("progress")),
            )
            for item in snapshot.jobs
        ]
        self._sync_rows(rows)


class MetricsPage(TablePage):
    COLUMNS = ("key", "value")
    COLUMN_LABELS = ("  METRIC", "  VALUE")

    def __init__(self) -> None:
        super().__init__("performance")

    def refresh_data(self, snapshot: CockpitSnapshot) -> None:
        rows: list[tuple[str, ...]] = []
        for key, value in sorted(snapshot.metrics.items()):
            val_str = str(value)
            if isinstance(value, (int, float)):
                val_str = f"[cyan]{val_str}[/cyan]"
            rows.append((f"[#5a7a9a]{key}[/#5a7a9a]", val_str))
        self._sync_rows(rows)


class LogsPage(Static):
    """Scrolling event log."""

    DEFAULT_CSS = """
    LogsPage {
        padding: 1 2;
        height: 1fr;
        width: 1fr;
        overflow-y: auto;
    }
    """

    def __init__(self) -> None:
        super().__init__(id="page-logs", classes="cockpit-page")

    def refresh_data(self, event_log: list[str]) -> None:
        lines: list[str] = []
        for entry in event_log[-40:]:
            ts, _, rest = entry.partition("  ")
            parts = rest.split("  ", 1)
            kind = parts[0]
            extra = parts[1] if len(parts) > 1 else ""
            c = "yellow" if "job." in kind else "blue"
            c = "cyan" if "model." in kind else c
            c = "red" if "error" in kind.lower() else c
            lines.append(f"[dim]{ts}[/dim]  [{c}]{kind}[/{c}]  {extra}")
        self.update("\n".join(lines) if lines else "[dim]No events yet.[/dim]")


class RoutesPage(Static):
    DEFAULT_CSS = """
    RoutesPage { padding: 1 2; height: 1fr; width: 1fr; }
    """

    def __init__(self) -> None:
        super().__init__(id="page-routes", classes="cockpit-page")

    def refresh_data(self, policy: str) -> None:
        self.update(
            f"[#5a7a9a]Policy[/#5a7a9a]  [cyan]{policy}[/cyan]\n\n"
            "[bright_black]Physical placement is resolved by omlxcd.[/bright_black]"
        )


class SettingsPage(Static):
    DEFAULT_CSS = """
    SettingsPage { padding: 1 2; height: 1fr; width: 1fr; }
    """

    def __init__(self) -> None:
        super().__init__(id="page-settings", classes="cockpit-page")

    def refresh_data(self, policy: str) -> None:
        self.update(
            f"[#5a7a9a]Default policy[/#5a7a9a]  [cyan]{policy}[/cyan]\n\n"
            "[bright_black]Thinking OFF by default.[/bright_black]"
        )


# ─── Nav item ─────────────────────────────────────────────────────────────────


class NavItem(ListItem):
    def __init__(self, slug: str) -> None:
        icon = PAGE_ICONS[slug]
        title = PAGE_TITLES[slug]
        super().__init__(
            Label(f"  {icon}  {title}", id=f"nav-label-{slug}"),
            id=f"nav-{slug}",
        )


# ─── Main app ─────────────────────────────────────────────────────────────────


class CockpitApp(App[None]):
    """Keyboard-first local compute dashboard with explicit freshness state."""

    TITLE = "omlxc"
    SUB_TITLE = "Local Compute Hub"

    BINDINGS = [
        Binding("g", "quick_jump", "Jump", show=True),
        Binding("slash", "search", "Search", show=True),
        Binding("colon", "command_palette", "Command", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("question_mark", "show_help", "Help", show=True),
        Binding("q", "quit", "Quit", show=True),
        Binding("escape", "escape_overlay", "Close", show=False),
    ]

    CSS = """
    /* ── Global ── */
    Screen {
        background: #060d18;
        color: #c8d8ec;
        layers: base overlay;
    }

    /* ── Header override ── */
    Header {
        background: #091525;
        color: #7dd3f5;
        border-bottom: solid #1a3550;
        text-style: bold;
        height: 3;
    }
    Header .header--icon { color: #2a6090; }

    /* ── Connection badge in topbar ── */
    #conn-badge {
        dock: right;
        width: auto;
        padding: 0 2;
        height: 3;
        content-align: right middle;
        color: #5a7a9a;
    }

    /* ── Body ── */
    #body {
        height: 1fr;
        width: 1fr;
    }

    /* ── Nav sidebar ── */
    #nav {
        width: 22;
        min-width: 16;
        border-right: solid #122035;
        background: #080f1c;
        padding-top: 1;
    }
    #nav ListView {
        background: transparent;
    }
    #nav ListItem {
        padding: 0 0;
        height: 2;
        background: transparent;
        color: #506a85;
    }
    #nav ListItem Label {
        height: 2;
        content-align: left middle;
        color: #506a85;
    }
    #nav ListItem:hover {
        background: #0d1f35;
        color: #a8c8e8;
    }
    #nav ListItem:hover Label {
        color: #a8c8e8;
    }
    #nav ListItem.--highlight {
        background: #102840;
        border-left: solid #2a7ab5;
        color: #7dd3f5;
    }
    #nav ListItem.--highlight Label {
        color: #7dd3f5;
        text-style: bold;
    }

    /* ── Pages area ── */
    #pages {
        width: 1fr;
        height: 1fr;
        border-left: solid #0f2035;
    }

    /* ── Common page shell ── */
    .cockpit-page {
        width: 1fr;
        height: 1fr;
        background: #060d18;
    }

    /* ── DataTable theming ── */
    DataTable {
        height: 1fr;
        width: 1fr;
        background: #060d18;
    }
    DataTable > .datatable--header {
        background: #0b1e30;
        color: #2a7ab5;
        text-style: bold;
    }
    DataTable > .datatable--odd-row {
        background: #060d18;
    }
    DataTable > .datatable--even-row {
        background: #080f1c;
    }
    DataTable > .datatable--cursor {
        background: #102840;
        color: #7dd3f5;
    }
    DataTable > .datatable--highlight {
        background: #0d1f35;
    }

    /* ── Footer ── */
    Footer {
        background: #080f1c;
        color: #3d6080;
        border-top: solid #122035;
        height: 1;
    }
    Footer > .footer--highlight {
        background: #102840;
        color: #7dd3f5;
    }

    /* ── Narrow layout ── */
    .narrow #nav {
        display: none;
    }
    .narrow #topbar-title, .narrow .cockpit-page {
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
        self._last_update_str = "00:00:00"
        self._flash_tick = False
        self.event_cursor = 0
        self.last_event_kind: str | None = None
        self._event_log: list[str] = []
        self._pending_mutation: PendingMutation | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="conn-badge")
        with Horizontal(id="body"):
            yield ListView(
                *(NavItem(slug) for slug in PAGE_SLUGS),
                id="nav",
            )
            yield ContentSwitcher(
                OverviewPage(),
                NodesPage(),
                ModelsPage(),
                RoutesPage(),
                JobsPage(),
                MetricsPage(),
                LogsPage(),
                SettingsPage(),
                initial="page-overview",
                id="pages",
            )
        yield Footer()

    def on_mount(self) -> None:
        self._set_narrow(self.size.width < 80 or self.size.height < 24)
        self._render_snapshot()
        self.set_interval(0.5, self._tick_flash)
        self.run_worker(
            self._connection_loop(),
            name="daemon-events",
            group="daemon",
            exclusive=True,
            exit_on_error=False,
        )

    def _tick_flash(self) -> None:
        self._flash_tick = not getattr(self, "_flash_tick", False)
        if self.connection_state == "CONNECTING":
            self._render_snapshot()

    def on_resize(self, event: Resize) -> None:
        self._set_narrow(event.size.width < 80 or event.size.height < 24)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item.id is not None and event.item.id.startswith("nav-"):
            self.show_page(event.item.id.removeprefix("nav-"))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        # Textual publishes the event table without propagating its cell generic.
        table = cast(DataTable[str], event.data_table)  # pyright: ignore[reportUnknownMemberType]
        if not table.is_valid_row_index(event.cursor_row):
            return
        try:
            value = table.get_cell_at(Coordinate(event.cursor_row, 0))
            import re

            identifier = re.sub(r"\[.*?\]", "", value).strip()
            self.sub_title = f"Selected ID: {identifier}"
        except Exception:
            pass

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
        import datetime

        conn = self.connection_state
        if conn == "LIVE":
            self._last_update_str = datetime.datetime.now().strftime("%H:%M:%S")
            conn_markup = "[green]● LIVE[/green]"
        elif conn == "STALE":
            st = getattr(self, "_last_update_str", "00:00:00")
            conn_markup = f"[yellow]◌ STALE — last update {st}[/yellow]"
        else:
            sym = "⟳" if getattr(self, "_flash_tick", False) else " "
            conn_markup = f"[bright_black]{sym} CONNECTING…[/bright_black]"

        active_jobs = sum(
            item.get("state") in {"pending", "planning", "running", "cancelling"}
            for item in self.snapshot.jobs
        )
        badge_text = (
            f"{conn_markup}"
            f"  [bright_black]policy {self.policy}[/bright_black]"
            f"  [yellow]jobs {active_jobs}[/yellow]"
            if active_jobs
            else f"{conn_markup}  [bright_black]policy {self.policy}[/bright_black]"
        )
        self.query_one("#conn-badge", Static).update(badge_text)

        # Per-page updates
        with contextlib.suppress(Exception):
            self.query_one(OverviewPage).refresh_data(self.snapshot, conn, self._last_update_str)
        with contextlib.suppress(Exception):
            self.query_one(NodesPage).refresh_data(self.snapshot)
        with contextlib.suppress(Exception):
            self.query_one(ModelsPage).refresh_data(self.snapshot)
        with contextlib.suppress(Exception):
            self.query_one(JobsPage).refresh_data(self.snapshot)
        with contextlib.suppress(Exception):
            self.query_one(MetricsPage).refresh_data(self.snapshot)
        with contextlib.suppress(Exception):
            self.query_one(LogsPage).refresh_data(self._event_log)
        with contextlib.suppress(Exception):
            self.query_one(RoutesPage).refresh_data(self.policy)
        with contextlib.suppress(Exception):
            self.query_one(SettingsPage).refresh_data(self.policy)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _object(value: JsonValue | None) -> JsonObject:
    if not isinstance(value, dict):
        raise ValueError("expected object response")
    return cast(JsonObject, value)


def _page_items(value: JsonValue | None) -> tuple[JsonObject, ...]:
    items = _object(value).get("items")
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise ValueError("expected paginated object items")
    return tuple(cast(list[JsonObject], items))


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
