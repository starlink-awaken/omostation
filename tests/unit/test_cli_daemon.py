"""Task 8 CLI command, output, and risk-gate contracts."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

import omlxc.cli as cli_module
from omlxc.cli import app
from omlxc.client import DaemonClientError, DaemonEnvelope, DaemonEvent, RemoteError

runner = CliRunner()


def _envelope(data: object, request_id: str = "req-cli-1") -> DaemonEnvelope:
    return DaemonEnvelope.model_validate(
        {"schema_version": 1, "request_id": request_id, "data": data}
    )


class FakeClient:
    def __init__(self, *, health_error: DaemonClientError | None = None) -> None:
        self.health_error = health_error
        self.calls: list[tuple[object, ...]] = []
        self.entered = 0

    async def __aenter__(self) -> FakeClient:
        self.entered += 1
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def health(self) -> DaemonEnvelope:
        self.calls.append(("health",))
        if self.health_error is not None:
            raise self.health_error
        return _envelope({"status": "ready", "degraded": False, "policy": "interactive"})

    async def nodes(self, *, after: str | None = None, limit: int = 100) -> DaemonEnvelope:
        self.calls.append(("nodes", after, limit))
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
            }
        )

    async def models(self, *, after: str | None = None, limit: int = 100) -> DaemonEnvelope:
        self.calls.append(("models", after, limit))
        return _envelope(
            {
                "items": [{"id": "local/model-a", "role": "chat", "reasoning": False}],
                "next_cursor": "local/model-a",
            }
        )

    async def jobs(self, *, after: str | None = None, limit: int = 100) -> DaemonEnvelope:
        self.calls.append(("jobs", after, limit))
        return _envelope({"items": [], "next_cursor": None})

    async def job(self, job_id: str) -> DaemonEnvelope:
        self.calls.append(("job", job_id))
        return _envelope({"id": job_id, "state": "running", "progress": 0.5})

    async def plan_route(self, body: dict[str, object]) -> DaemonEnvelope:
        self.calls.append(("plan", body))
        return _envelope(
            {
                "selected_placement_id": "mbp-omlx-a",
                "fallback_chain": ["mbp-omlx-a"],
                "rejected": {},
            }
        )

    async def load_model(
        self, model_id: str, *, idempotency_key: str | None = None
    ) -> DaemonEnvelope:
        self.calls.append(("load", model_id, idempotency_key))
        return _envelope({"id": "job-load", "state": "pending", "kind": "load"})

    async def unload_model(
        self, model_id: str, *, idempotency_key: str | None = None
    ) -> DaemonEnvelope:
        self.calls.append(("unload", model_id, idempotency_key))
        return _envelope({"id": "job-unload", "state": "pending", "kind": "unload"})

    async def cancel_job(self, job_id: str) -> DaemonEnvelope:
        self.calls.append(("cancel", job_id))
        return _envelope({"id": job_id, "state": "cancelling"})

    async def metrics(self) -> DaemonEnvelope:
        self.calls.append(("metrics",))
        return _envelope({"requests": 7, "event_drops": 0})

    async def stream_events(self, *, after: int = 0) -> AsyncIterator[DaemonEvent]:
        self.calls.append(("events", after))
        yield DaemonEvent.model_validate(
            {
                "schema_version": 1,
                "request_id": "req-events",
                "cursor": 2,
                "event_id": "job-2",
                "timestamp": datetime(2026, 8, 11, tzinfo=UTC),
                "priority": "high",
                "kind": "job.running",
                "payload": {"state": "running"},
                "job_id": "job-1",
                "resource_id": None,
            }
        )


class PagedClient(FakeClient):
    def __init__(self, *, cycle: bool = False) -> None:
        super().__init__()
        self.cycle = cycle

    async def nodes(self, *, after: str | None = None, limit: int = 100) -> DaemonEnvelope:
        self.calls.append(("nodes", after, limit))
        if self.cycle:
            return _envelope({"items": [{"id": "node-000"}], "next_cursor": "same-cursor"})
        start = 0 if after is None else int(after.removeprefix("node-")) + 1
        items = [
            {"id": f"node-{index:03d}", "display_name": f"Node {index}"}
            for index in range(start, min(start + limit, 101))
        ]
        return _envelope(
            {
                "items": items,
                "next_cursor": items[-1]["id"] if items else None,
            }
        )

    async def models(self, *, after: str | None = None, limit: int = 100) -> DaemonEnvelope:
        self.calls.append(("models", after, limit))
        start = 0 if after is None else int(after.removeprefix("model-")) + 1
        items = [
            {"id": f"model-{index:03d}", "role": "chat"}
            for index in range(start, min(start + limit, 101))
        ]
        return _envelope(
            {
                "items": items,
                "next_cursor": items[-1]["id"] if items else None,
            }
        )


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> FakeClient:
    client = FakeClient()
    monkeypatch.setattr(cli_module, "_client_factory", lambda _path: client, raising=False)
    monkeypatch.setattr(cli_module, "_stdio_is_tty", lambda: False, raising=False)
    return client


def test_help_exposes_complete_public_command_tree() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in (
        "status",
        "nodes",
        "models",
        "routes",
        "jobs",
        "metrics",
        "config",
        "daemon",
        "doctor",
        "benchmark",
    ):
        assert command in result.stdout

    expected = {
        "nodes": ("list", "show", "probe"),
        "models": ("list", "show", "load", "unload", "reconcile"),
        "routes": ("show", "plan", "test", "pin"),
        "jobs": ("list", "show", "watch", "cancel"),
        "metrics": ("show", "export"),
        "config": ("validate", "diff", "migrate", "apply", "rollback"),
        "daemon": ("install", "uninstall", "status", "start", "stop", "restart"),
    }
    for group, commands in expected.items():
        help_result = runner.invoke(app, [group, "--help"])
        assert help_result.exit_code == 0
        assert all(command in help_result.stdout for command in commands)


def test_no_args_uses_tui_only_for_interactive_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    launched: list[Path | None] = []
    monkeypatch.setattr(cli_module, "_run_tui", launched.append, raising=False)
    monkeypatch.setattr(cli_module, "_stdio_is_tty", lambda: True, raising=False)

    interactive = runner.invoke(app, [])
    assert interactive.exit_code == 0
    assert launched == [None]

    launched.clear()
    monkeypatch.setattr(cli_module, "_stdio_is_tty", lambda: False, raising=False)
    pipeline = runner.invoke(app, [])
    assert pipeline.exit_code == 2
    assert launched == []
    assert "requires a command" in pipeline.stderr.lower()
    assert "traceback" not in pipeline.stderr.lower()


def test_status_json_and_human_table_keep_stdout_machine_clean(fake_client: FakeClient) -> None:
    machine = runner.invoke(app, ["status", "--json"])
    human = runner.invoke(app, ["nodes", "list"])

    assert machine.exit_code == human.exit_code == 0
    payload = json.loads(machine.stdout)
    assert payload["schema_version"] == 1
    assert payload["request_id"] == "req-cli-1"
    assert payload["data"]["status"] == "ready"
    assert machine.stderr == ""
    assert "MBP" in human.stdout and "healthy" in human.stdout
    assert "\x1b[" not in human.stdout


def test_show_json_returns_only_the_selected_resource(fake_client: FakeClient) -> None:
    node = runner.invoke(app, ["nodes", "show", "mbp", "--json"])
    model = runner.invoke(app, ["models", "show", "local/model-a", "--json"])

    assert node.exit_code == model.exit_code == 0
    assert json.loads(node.stdout)["data"]["id"] == "mbp"
    assert json.loads(model.stdout)["data"]["id"] == "local/model-a"


def test_show_follows_stable_pagination_beyond_first_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = PagedClient()
    monkeypatch.setattr(cli_module, "_client_factory", lambda _path: client)

    node = runner.invoke(app, ["nodes", "show", "node-100", "--json"])
    model = runner.invoke(app, ["models", "show", "model-100", "--json"])

    assert node.exit_code == model.exit_code == 0
    assert json.loads(node.stdout)["data"]["id"] == "node-100"
    assert json.loads(model.stdout)["data"]["id"] == "model-100"
    assert ("nodes", "node-099", 100) in client.calls
    assert ("models", "model-099", 100) in client.calls


def test_show_cursor_cycle_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    client = PagedClient(cycle=True)
    monkeypatch.setattr(cli_module, "_client_factory", lambda _path: client)

    result = runner.invoke(app, ["nodes", "show", "missing", "--json"])

    assert result.exit_code == 10
    assert result.stdout == ""
    assert json.loads(result.stderr)["error"]["code"] == "E900"
    assert len([call for call in client.calls if call[0] == "nodes"]) == 2


def test_daemon_errors_use_stderr_and_public_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    failure = DaemonClientError(
        RemoteError(code="E200", message="daemon is unavailable", retryable=True),
        request_id="req-down",
    )
    client = FakeClient(health_error=failure)
    monkeypatch.setattr(cli_module, "_client_factory", lambda _path: client, raising=False)

    result = runner.invoke(app, ["status", "--json"])

    assert result.exit_code == 3
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["schema_version"] == 1
    assert payload["request_id"] == "req-down"
    assert payload["error"]["code"] == "E200"


def test_r1_noninteractive_requires_yes_before_mutation(fake_client: FakeClient) -> None:
    refused = runner.invoke(app, ["models", "load", "local/model-a"])
    accepted = runner.invoke(app, ["models", "load", "local/model-a", "--yes", "--json"])

    assert refused.exit_code == 7
    assert "E700" in refused.stderr
    assert accepted.exit_code == 0
    assert [call[0] for call in fake_client.calls] == ["load"]
    assert json.loads(accepted.stdout)["data"]["id"] == "job-load"


def test_r1_interactive_refusal_is_typed_safety_error(
    fake_client: FakeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli_module, "_stdio_is_tty", lambda: True)

    refused = runner.invoke(app, ["models", "unload", "local/model-a"], input="n\n")

    assert refused.exit_code == 7
    assert "E700" in refused.stderr
    assert fake_client.calls == []


def test_r2_shows_plan_and_requires_two_confirmations_without_daemon_write(
    fake_client: FakeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli_module, "_stdio_is_tty", lambda: True, raising=False)

    refused = runner.invoke(app, ["daemon", "restart"], input="y\nn\n")

    assert refused.exit_code == 7
    assert "impact" in refused.stdout.lower()
    assert "rollback" in refused.stdout.lower()
    assert "E700" in refused.stderr
    assert fake_client.entered == 0

    monkeypatch.setattr(cli_module, "_stdio_is_tty", lambda: False, raising=False)
    incomplete = runner.invoke(app, ["daemon", "restart", "--yes", "--json"])
    assert incomplete.exit_code == 7
    assert json.loads(incomplete.stdout)["data"]["risk"] == "R2"
    assert json.loads(incomplete.stderr)["error"]["code"] == "E700"
    assert fake_client.entered == 0

    class FakeLaunchd:
        async def restart(self) -> object:
            return object()

    monkeypatch.setattr(cli_module, "_launchd_controller", lambda: FakeLaunchd())

    bypassed = runner.invoke(
        app,
        ["daemon", "restart", "--yes", "--confirm-impact", "--json"],
    )
    assert bypassed.exit_code == 0
    records = [json.loads(line) for line in bypassed.stdout.splitlines()]
    assert records[0]["data"]["rollback"]
    assert records[-1]["data"]["status"] == "restart"
    assert bypassed.stderr == ""
    assert fake_client.entered == 0


def test_jobs_watch_emits_versioned_ndjson(fake_client: FakeClient) -> None:
    result = runner.invoke(app, ["jobs", "watch", "--output", "ndjson"])

    assert result.exit_code == 0
    records = [json.loads(line) for line in result.stdout.splitlines()]
    assert records == [
        {
            "schema_version": 1,
            "request_id": "req-events",
            "cursor": 2,
            "event_id": "job-2",
            "timestamp": "2026-08-11T00:00:00Z",
            "priority": "high",
            "kind": "job.running",
            "payload": {"state": "running"},
            "job_id": "job-1",
            "resource_id": None,
        }
    ]
    assert fake_client.calls == [("events", 0)]
