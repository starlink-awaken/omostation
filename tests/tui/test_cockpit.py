"""Task 8 Textual cockpit keyboard and resilience contracts."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from importlib import import_module

import pytest
from textual.widgets import ContentSwitcher, Static

from omlxc.client import DaemonClientError, DaemonEnvelope, DaemonEvent, RemoteError


def _tui_api():  # type: ignore[no-untyped-def]
    return import_module("omlxc.tui")


def _envelope(data: object, request_id: str) -> DaemonEnvelope:
    return DaemonEnvelope.model_validate(
        {"schema_version": 1, "request_id": request_id, "data": data}
    )


class CockpitClient:
    def __init__(
        self,
        name: str,
        *,
        events: tuple[DaemonEvent, ...] = (),
        disconnect: bool = False,
        disconnect_ready: asyncio.Event | None = None,
        disconnect_release: asyncio.Event | None = None,
        fail_snapshot: bool = False,
    ) -> None:
        self.name = name
        self.events = events
        self.disconnect = disconnect
        self.disconnect_ready = disconnect_ready
        self.disconnect_release = disconnect_release
        self.fail_snapshot = fail_snapshot
        self.health_calls = 0
        self.mutations: list[tuple[str, str]] = []

    async def __aenter__(self) -> CockpitClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def health(self) -> DaemonEnvelope:
        self.health_calls += 1
        if self.fail_snapshot:
            raise _disconnected()
        return _envelope(
            {"status": "ready", "degraded": False, "policy": "interactive"},
            f"req-{self.name}-health",
        )

    async def nodes(self, *, after: str | None = None, limit: int = 100) -> DaemonEnvelope:
        del after, limit
        return _envelope(
            {
                "items": [
                    {
                        "id": "mbp",
                        "display_name": "MBP",
                        "platform": "macos",
                        "health": {"state": "healthy", "stale": False},
                    }
                ],
                "next_cursor": "mbp",
            },
            f"req-{self.name}-nodes",
        )

    async def models(self, *, after: str | None = None, limit: int = 100) -> DaemonEnvelope:
        del after, limit
        return _envelope(
            {
                "items": [{"id": "local/model-a", "role": "chat", "reasoning": False}],
                "next_cursor": "local/model-a",
            },
            f"req-{self.name}-models",
        )

    async def jobs(self, *, after: str | None = None, limit: int = 100) -> DaemonEnvelope:
        del after, limit
        return _envelope(
            {"items": [{"id": "job-1", "kind": "load", "state": "running"}]},
            f"req-{self.name}-jobs",
        )

    async def metrics(self) -> DaemonEnvelope:
        return _envelope(
            {"requests": 5, "event_drops": 0},
            f"req-{self.name}-metrics",
        )

    async def load_model(self, model_id: str) -> DaemonEnvelope:
        self.mutations.append(("load", model_id))
        return _envelope({"id": "job-load", "state": "pending"}, f"req-{self.name}-load")

    async def unload_model(self, model_id: str) -> DaemonEnvelope:
        self.mutations.append(("unload", model_id))
        return _envelope({"id": "job-unload", "state": "pending"}, f"req-{self.name}-unload")

    async def cancel_job(self, job_id: str) -> DaemonEnvelope:
        self.mutations.append(("cancel", job_id))
        return _envelope({"id": job_id, "state": "cancelling"}, f"req-{self.name}-cancel")

    async def stream_events(self, *, after: int = 0) -> AsyncIterator[DaemonEvent]:
        del after
        for event in self.events:
            yield event
        if self.disconnect:
            if self.disconnect_ready is not None:
                self.disconnect_ready.set()
            if self.disconnect_release is not None:
                await self.disconnect_release.wait()
            raise _disconnected()
        await asyncio.Event().wait()
        if False:
            yield self.events[0]


class SequenceFactory:
    def __init__(self, clients: list[CockpitClient]) -> None:
        self.clients = clients
        self.calls = 0

    def __call__(self) -> CockpitClient:
        index = min(self.calls, len(self.clients) - 1)
        self.calls += 1
        return self.clients[index]


def _disconnected() -> DaemonClientError:
    return DaemonClientError(
        RemoteError(code="E200", message="daemon is unavailable", retryable=True),
        request_id="req-disconnected",
    )


def _event(
    *,
    kind: str = "job.running",
    payload: dict[str, object] | None = None,
    resource_id: str | None = None,
    job_id: str | None = "job-1",
    cursor: int = 7,
) -> DaemonEvent:
    return DaemonEvent.model_validate(
        {
            "schema_version": 1,
            "request_id": "req-event",
            "cursor": cursor,
            "event_id": f"event-{cursor}",
            "timestamp": datetime(2026, 8, 11, tzinfo=UTC),
            "priority": "high",
            "kind": kind,
            "payload": payload or {"state": "running", "progress": 0.5},
            "job_id": job_id,
            "resource_id": resource_id,
        }
    )


@pytest.mark.asyncio
async def test_cockpit_has_eight_reachable_pages_and_keyboard_overlays() -> None:
    api = _tui_api()
    client = CockpitClient("stable")
    app = api.CockpitApp(client_factory=lambda: client, reconnect_delays=(0.05,))

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.03)
        assert app.connection_state == "LIVE"
        assert len(app.query_one(ContentSwitcher).children) == 8
        for slug in api.PAGE_SLUGS:
            app.show_page(slug)
            await pilot.pause()
            assert app.query_one(ContentSwitcher).current == f"page-{slug}"

        for key, screen_type in (
            ("g", api.JumpScreen),
            ("/", api.SearchScreen),
            (":", api.CommandScreen),
            ("?", api.HelpScreen),
        ):
            await pilot.press(key)
            assert isinstance(app.screen, screen_type)
            await pilot.press("escape")
            assert app.screen is app.screen_stack[0]

        before = client.health_calls
        await pilot.press("r")
        await pilot.pause(0.03)
        assert client.health_calls > before


@pytest.mark.asyncio
async def test_confirmation_modal_reports_impact_and_refusal_runs_no_action() -> None:
    api = _tui_api()
    client = CockpitClient("stable")
    results: list[bool] = []
    app = api.CockpitApp(client_factory=lambda: client)

    async with app.run_test(size=(100, 32)) as pilot:
        app.push_screen(
            api.ConfirmationScreen(
                action="load local/model-a",
                risk="R1",
                impact="Loads the model into local memory.",
                rollback="Unload the model.",
            ),
            results.append,
        )
        await pilot.pause()
        rendered = "".join(str(s.render()) for s in app.screen.query(Static))
        assert "Impact" in rendered and "Rollback" in rendered and "R1" in rendered
        await pilot.press("n")
        assert results == [False]
        assert client.health_calls >= 1


@pytest.mark.asyncio
async def test_command_palette_reuses_confirmation_before_typed_r1_mutation() -> None:
    api = _tui_api()
    client = CockpitClient("stable")
    app = api.CockpitApp(client_factory=lambda: client)

    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.press(":")
        await pilot.press(*list("load local/model-a"), "enter")
        assert isinstance(app.screen, api.ConfirmationScreen)
        assert client.mutations == []
        await pilot.press("y")
        await pilot.pause(0.03)

    assert client.mutations == [("load", "local/model-a")]


@pytest.mark.asyncio
async def test_disconnect_keeps_snapshot_stale_and_applies_event() -> None:
    api = _tui_api()
    disconnect_ready = asyncio.Event()
    disconnect_release = asyncio.Event()
    first = CockpitClient(
        "first",
        events=(_event(),),
        disconnect=True,
        disconnect_ready=disconnect_ready,
        disconnect_release=disconnect_release,
    )
    second = CockpitClient("second")
    factory = SequenceFactory([first, second])
    app = api.CockpitApp(client_factory=factory, reconnect_delays=(1.0,))

    async with app.run_test(size=(110, 34)) as pilot:
        await asyncio.wait_for(disconnect_ready.wait(), timeout=1.0)
        assert app.connection_state == "LIVE"
        disconnect_release.set()
        await pilot.pause()
        assert app.connection_state == "STALE"
        assert app.snapshot.nodes[0]["id"] == "mbp"
        assert app.last_event_kind == "job.running"
        assert "STALE" in str(app.query_one("#conn-badge", Static).render())


@pytest.mark.asyncio
async def test_disconnect_reconnects_within_bounded_delay() -> None:
    api = _tui_api()
    first = CockpitClient("first", disconnect=True)
    second = CockpitClient("second")
    factory = SequenceFactory([first, second])
    app = api.CockpitApp(client_factory=factory, reconnect_delays=(0.12,))

    async with app.run_test(size=(110, 34)) as pilot:
        for _ in range(30):
            if app.connection_state == "LIVE" and factory.calls >= 2:
                break
            await pilot.pause(0.01)
        else:
            pytest.fail("cockpit did not reconnect within the bounded test window")
        assert "LIVE" in str(app.query_one("#conn-badge", Static).render())


@pytest.mark.asyncio
async def test_known_events_merge_snapshot_and_render_resource_state_without_rescan() -> None:
    api = _tui_api()
    client = CockpitClient("stable")
    app = api.CockpitApp(client_factory=lambda: client)

    async with app.run_test(size=(110, 34)) as pilot:
        await pilot.pause(0.03)
        health_calls = client.health_calls
        app._apply_event(
            _event(
                kind="node.health",
                payload={"state": "degraded", "stale": True},
                resource_id="mbp",
                job_id=None,
                cursor=8,
            )
        )
        app._apply_event(
            _event(
                kind="model.loaded",
                payload={"loaded": True, "state": "loaded"},
                resource_id="local/model-a",
                job_id=None,
                cursor=9,
            )
        )
        app._apply_event(
            _event(
                kind="job.succeeded",
                payload={"state": "succeeded", "progress": 1.0},
                cursor=10,
            )
        )
        app._apply_event(
            _event(
                kind="metrics.updated",
                payload={"requests": 6, "errors": 1},
                job_id=None,
                cursor=11,
            )
        )
        await pilot.pause()

        assert app.snapshot.nodes[0]["health"] == {"state": "degraded", "stale": True}
        assert app.snapshot.models[0]["loaded"] is True
        assert app.snapshot.jobs[0]["state"] == "succeeded"
        assert app.snapshot.jobs[0]["progress"] == 1.0
        assert app.snapshot.metrics["requests"] == 6
        assert client.health_calls == health_calls


@pytest.mark.asyncio
async def test_narrow_terminal_and_daemon_error_keep_core_status_visible() -> None:
    api = _tui_api()
    failing = CockpitClient("down", fail_snapshot=True)
    app = api.CockpitApp(client_factory=lambda: failing, reconnect_delays=(1.0,))

    async with app.run_test(size=(70, 20)) as pilot:
        await pilot.pause(0.03)
        assert app.has_class("narrow")
        assert app.connection_state == "STALE"
        top = str(app.query_one("#conn-badge", Static).render())
        assert "STALE" in top


@pytest.mark.asyncio
async def test_q_exits_cockpit() -> None:
    api = _tui_api()
    app = api.CockpitApp(client_factory=lambda: CockpitClient("stable"))

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("q")
        await pilot.pause()

    assert app.return_value is None
