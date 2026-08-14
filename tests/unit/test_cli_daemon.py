"""Task 8 CLI command, output, and risk-gate contracts."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Never, cast

import pytest
import typer
from typer.testing import CliRunner

import omlxc.cli as cli_module
from omlxc.cli import app
from omlxc.cli_guide import (
    MAX_GUIDE_TRANSITIONS,
    GuideOperation,
    GuideRequest,
    GuideState,
    GuideTransition,
)
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

    async def probe_node(self, node_id: str) -> DaemonEnvelope:
        self.calls.append(("probe_node", node_id))
        return _envelope(
            {
                "id": node_id,
                "health": {"state": "healthy", "stale": False},
                "fresh": True,
                "available": True,
                "authorized": True,
                "ready": True,
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


class GuideTripwireClient(FakeClient):
    """Guide fixture that fails if a read-only workflow escapes its allowlist."""

    @staticmethod
    def _forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("guide called a forbidden daemon method")

    async def nodes(self, *, after: str | None = None, limit: int = 100) -> DaemonEnvelope:
        self._forbidden(after, limit)
        raise AssertionError("unreachable")

    async def jobs(self, *, after: str | None = None, limit: int = 100) -> DaemonEnvelope:
        self._forbidden(after, limit)
        raise AssertionError("unreachable")

    async def load_model(
        self, model_id: str, *, idempotency_key: str | None = None
    ) -> DaemonEnvelope:
        self._forbidden(model_id, idempotency_key)
        raise AssertionError("unreachable")

    async def unload_model(
        self, model_id: str, *, idempotency_key: str | None = None
    ) -> DaemonEnvelope:
        self._forbidden(model_id, idempotency_key)
        raise AssertionError("unreachable")

    async def cancel_job(self, job_id: str) -> DaemonEnvelope:
        self._forbidden(job_id)
        raise AssertionError("unreachable")

    async def metrics(self) -> DaemonEnvelope:
        self._forbidden()
        raise AssertionError("unreachable")

    def stream_events(self, *, after: int = 0) -> AsyncIterator[DaemonEvent]:
        self._forbidden(after)
        raise AssertionError("unreachable")


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


@pytest.mark.parametrize(
    ("user_input", "expected_call", "expected_text"),
    (
        ("1\n", ("health",), "OK · Daemon ready"),
        ("2\n", ("models", None, 20), "local/model-a"),
        (
            "3\nlocal/model-a\n",
            (
                "plan",
                {
                    "model_id": "local/model-a",
                    "profile": "interactive",
                    "context_tokens": 0,
                    "required_capabilities": [],
                    "thinking_requested": False,
                },
            ),
            "selected  mbp-omlx-a",
        ),
        ("4\njob-1\n", ("job", "job-1"), "job  job-1"),
        ("5\n", ("health",), "OK · Daemon ready"),
        ("6\nlocal/model-a\n", None, "omlxc models load local/model-a --yes"),
    ),
)
def test_guide_branches_are_bounded_and_read_only(
    monkeypatch: pytest.MonkeyPatch,
    user_input: str,
    expected_call: tuple[object, ...] | None,
    expected_text: str,
) -> None:
    client = GuideTripwireClient()
    monkeypatch.setattr(cli_module, "_client_factory", lambda _path: client)
    monkeypatch.setattr(cli_module, "_stdio_is_tty", lambda: True)

    result = runner.invoke(app, ["guide"], input=user_input)

    assert result.exit_code == 0
    assert expected_text in result.stdout
    assert result.stderr == ""
    assert client.calls == ([] if expected_call is None else [expected_call])


def test_guide_rejects_noninteractive_input_before_prompt_or_client_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = GuideTripwireClient()
    monkeypatch.setattr(cli_module, "_client_factory", lambda _path: client)
    monkeypatch.setattr(cli_module, "_stdio_is_tty", lambda: False)
    monkeypatch.setattr(
        typer,
        "prompt",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("prompted")),
    )

    result = runner.invoke(app, ["guide"])

    assert result.exit_code == 2
    assert result.stdout == ""
    assert "ERROR E100" in result.stderr
    assert "Next: omlxc guide --help" in result.stderr
    assert "traceback" not in result.stderr.lower()
    assert client.calls == []


@pytest.mark.parametrize("user_input", ("7\n", "3\n../../../private\n", "4\n\n"))
def test_guide_invalid_input_fails_closed_without_a_daemon_call(
    monkeypatch: pytest.MonkeyPatch, user_input: str
) -> None:
    client = GuideTripwireClient()
    monkeypatch.setattr(cli_module, "_client_factory", lambda _path: client)
    monkeypatch.setattr(cli_module, "_stdio_is_tty", lambda: True)

    result = runner.invoke(app, ["guide"], input=user_input)

    assert result.exit_code == 2
    assert result.stdout.startswith("What would you like to do?")
    assert "ERROR E100" in result.stderr
    assert "Next: omlxc guide --help" in result.stderr
    assert "../../../private" not in result.stderr
    assert "traceback" not in result.stderr.lower()
    assert client.calls == []


@pytest.mark.parametrize("cancel", (typer.Abort, EOFError, KeyboardInterrupt))
def test_guide_input_cancellation_fails_closed_without_a_daemon_call(
    monkeypatch: pytest.MonkeyPatch, cancel: type[BaseException]
) -> None:
    client = GuideTripwireClient()
    monkeypatch.setattr(cli_module, "_client_factory", lambda _path: client)
    monkeypatch.setattr(cli_module, "_stdio_is_tty", lambda: True)

    def abort_prompt(*_args: object, **_kwargs: object) -> Never:
        raise cancel()

    monkeypatch.setattr(typer, "prompt", abort_prompt)
    result = runner.invoke(app, ["guide"])

    assert result.exit_code == 2
    assert "ERROR E100" in result.stderr
    assert "Next: omlxc guide --help" in result.stderr
    assert "traceback" not in result.stderr.lower()
    assert client.calls == []


def test_guide_client_failure_retains_closed_error_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hostile = DaemonClientError(
        RemoteError(
            code="E200",
            message="Bearer credential at https://backend/private/path",
            technical_detail="hostile prompt body",
        ),
        request_id="req-guide",
    )
    client = GuideTripwireClient(health_error=hostile)
    monkeypatch.setattr(cli_module, "_client_factory", lambda _path: client)
    monkeypatch.setattr(cli_module, "_stdio_is_tty", lambda: True)

    result = runner.invoke(app, ["guide"], input="1\n")

    assert result.exit_code == 3
    assert result.stdout.startswith("What would you like to do?")
    assert "ERROR E200 · Daemon unavailable" in result.stderr
    assert "Next: omlxc daemon status" in result.stderr
    assert "Request: req-guide" in result.stderr
    for hostile_value in ("Bearer", "https://", "/private", "prompt body"):
        assert hostile_value not in result.stderr
    assert "traceback" not in result.stderr.lower()
    assert client.calls == [("health",)]


@pytest.mark.parametrize(
    ("user_input", "method", "data"),
    (
        ("1\n", "health", ["https://health/private"]),
        ("2\n", "models", {"not_items": "https://models/private"}),
        ("3\nlocal/model-a\n", "plan_route", ["https://route/private"]),
        ("4\njob-1\n", "job", ["https://job/private"]),
    ),
)
def test_guide_malformed_daemon_data_fails_closed_after_one_declared_call(
    monkeypatch: pytest.MonkeyPatch, user_input: str, method: str, data: object
) -> None:
    class MalformedGuideClient(GuideTripwireClient):
        async def health(self) -> DaemonEnvelope:
            self.calls.append(("health",))
            return _envelope(data)

        async def models(self, *, after: str | None = None, limit: int = 100) -> DaemonEnvelope:
            self.calls.append(("models", after, limit))
            return _envelope(data)

        async def plan_route(self, body: dict[str, object]) -> DaemonEnvelope:
            self.calls.append(("plan", body))
            return _envelope(data)

        async def job(self, job_id: str) -> DaemonEnvelope:
            self.calls.append(("job", job_id))
            return _envelope(data)

    client = MalformedGuideClient()
    monkeypatch.setattr(cli_module, "_client_factory", lambda _path: client)
    monkeypatch.setattr(cli_module, "_stdio_is_tty", lambda: True)

    result = runner.invoke(app, ["guide"], input=user_input)

    assert result.exit_code == 10
    assert "ERROR E900" in result.stderr
    assert "https://" not in result.stderr
    assert "traceback" not in result.stderr.lower()
    assert [call[0] for call in client.calls] == ["plan" if method == "plan_route" else method]


def test_guide_renderer_fault_fails_closed_without_echoing_error_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = GuideTripwireClient()
    monkeypatch.setattr(cli_module, "_client_factory", lambda _path: client)
    monkeypatch.setattr(cli_module, "_stdio_is_tty", lambda: True)

    def broken_renderer(_operation: GuideOperation, _data: object) -> str:
        raise RuntimeError("https://renderer/private/identity")

    monkeypatch.setattr(cli_module, "_render_guide_result", broken_renderer)
    result = runner.invoke(app, ["guide"], input="1\n")

    assert result.exit_code == 10
    assert "ERROR E900" in result.stderr
    assert "https://" not in result.stdout
    assert "https://" not in result.stderr
    assert "traceback" not in result.stderr.lower()
    assert client.calls == [("health",)]


def test_guide_renderer_abort_preserves_cancellation_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = GuideTripwireClient()
    monkeypatch.setattr(cli_module, "_client_factory", lambda _path: client)
    monkeypatch.setattr(cli_module, "_stdio_is_tty", lambda: True)

    def aborted_renderer(_operation: GuideOperation, _data: object) -> str:
        raise typer.Abort()

    monkeypatch.setattr(cli_module, "_render_guide_result", aborted_renderer)
    result = runner.invoke(app, ["guide"], input="1\n")

    assert result.exit_code == 2
    assert "ERROR E100" in result.stderr
    assert "guide cancelled" not in result.stderr
    assert "ERROR E900" not in result.stderr
    assert "Next: omlxc guide --help" in result.stderr
    assert "traceback" not in result.stderr.lower()
    assert client.calls == [("health",)]


def test_guide_rejects_hostile_route_fallback_before_rendering_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hostile_fallback = "https://route/private/identity"

    class HostileRouteGuideClient(GuideTripwireClient):
        async def plan_route(self, body: dict[str, object]) -> DaemonEnvelope:
            self.calls.append(("plan", body))
            return _envelope(
                {
                    "selected_placement_id": "mbp-omlx-a",
                    "fallback_chain": [hostile_fallback],
                }
            )

    client = HostileRouteGuideClient()
    monkeypatch.setattr(cli_module, "_client_factory", lambda _path: client)
    monkeypatch.setattr(cli_module, "_stdio_is_tty", lambda: True)

    result = runner.invoke(app, ["guide"], input="3\nlocal/model-a\n")

    assert result.exit_code == 10
    assert "ERROR E900" in result.stderr
    assert hostile_fallback not in result.stdout
    assert hostile_fallback not in result.stderr
    assert "traceback" not in result.stderr.lower()
    assert [call[0] for call in client.calls] == ["plan"]


def test_guide_operation_rejects_unknown_operations_before_a_daemon_call() -> None:
    client = GuideTripwireClient()
    request = GuideRequest(cast(GuideOperation, "future-operation"))

    with pytest.raises(ValueError, match="^guide operation is invalid$"):
        asyncio.run(cli_module._guide_operation(client, request))

    assert client.calls == []


def test_guide_transition_limit_fails_closed_without_daemon_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = GuideTripwireClient()
    prompts = 0
    monkeypatch.setattr(cli_module, "_client_factory", lambda _path: client)
    monkeypatch.setattr(cli_module, "_stdio_is_tty", lambda: True)

    def nonterminal_transition(_state: GuideState, _answer: object) -> GuideTransition:
        return GuideTransition(GuideState.GOAL)

    def counted_prompt(*_args: object, **_kwargs: object) -> str:
        nonlocal prompts
        prompts += 1
        return "1"

    monkeypatch.setattr(cli_module, "advance", nonterminal_transition)
    monkeypatch.setattr(typer, "prompt", counted_prompt)
    result = runner.invoke(app, ["guide"])

    assert result.exit_code == 10
    assert "ERROR E900" in result.stderr
    assert prompts == MAX_GUIDE_TRANSITIONS
    assert client.calls == []


def test_help_exposes_complete_public_command_tree() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert app.info.epilog == "Quick start: omlxc status\nGuided help: omlxc guide"
    assert "Quick start: omlxc status" in result.stdout
    assert "Guided help: omlxc guide" in result.stdout
    for command in (
        "status",
        "guide",
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


def test_guide_help_is_noninteractive_and_does_not_access_daemon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_client(*_args: object, **_kwargs: object) -> Never:
        raise AssertionError("guide --help accessed the daemon")

    monkeypatch.setattr(cli_module, "_client_factory", forbidden_client)
    monkeypatch.setattr(cli_module, "_stdio_is_tty", lambda: False)
    monkeypatch.setattr(
        typer,
        "prompt",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("guide --help prompted")),
    )

    result = runner.invoke(app, ["guide", "--help"])

    assert result.exit_code == 0
    assert "Choose a bounded, read-only workflow" in result.stdout
    assert result.stderr == ""


def test_readme_documents_guided_cli_quick_start_contract() -> None:
    readme = (Path(__file__).parents[2] / "README.md").read_text()

    section_start = readme.index("## Guided CLI quick start")
    section = readme[section_start:]
    section_flat = " ".join(section.split())
    assert "omlxc status        # cached daemon health plus safe next commands" in section
    assert "omlxc guide         # bounded, read-only TTY workflow" in section
    assert "omlxc status --json # unchanged machine contract" in section
    for statement in (
        "TTY-only and bounded",
        "exactly six goals",
        "never mutates models, jobs, services, or configuration",
        "prints commands but does not execute them",
        "no-argument TUI remains the interactive entry",
        "status --json is the automation/machine entry",
    ):
        assert statement in section_flat


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
    assert "ERROR E100 · Invalid command or configuration" in pipeline.stderr
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


def test_nodes_probe_calls_the_daemon_for_only_the_requested_node(
    fake_client: FakeClient,
) -> None:
    result = runner.invoke(app, ["nodes", "probe", "mbp", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["data"]["id"] == "mbp"
    assert fake_client.calls == [("probe_node", "mbp")]


def test_status_json_bytes_remain_unchanged(fake_client: FakeClient) -> None:
    result = runner.invoke(app, ["status", "--json"])

    assert result.exit_code == 0
    assert result.stdout == (
        '{"schema_version":1,"request_id":"req-cli-1",'
        '"data":{"status":"ready","degraded":false,"policy":"interactive"}}\n'
    )
    assert result.stderr == ""


def test_daemon_error_json_bytes_remain_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    failure = DaemonClientError(
        RemoteError(code="E200", message="daemon is unavailable", retryable=True),
        request_id="req-down",
    )
    monkeypatch.setattr(
        cli_module,
        "_client_factory",
        lambda _path: FakeClient(health_error=failure),
    )

    result = runner.invoke(app, ["status", "--json"])

    assert result.exit_code == 3
    assert result.stdout == ""
    assert result.stderr == (
        '{"schema_version":1,"request_id":"req-down",'
        '"error":{"code":"E200","message":"daemon is unavailable",'
        '"retryable":true,"affected_resources":[]}}\n'
    )


def test_status_human_output_is_guided_and_uses_one_health_call(
    fake_client: FakeClient,
) -> None:
    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert result.stdout == (
        "OK · Daemon ready\n"
        "  Status: ready\n"
        "  Degraded: no\n"
        "  Policy: interactive\n"
        "  Jobs: not checked by status\n\n"
        "Next\n"
        "  omlxc models list\n"
        "  omlxc jobs list\n"
    )
    assert result.stderr == ""
    assert fake_client.calls == [("health",)]


def test_status_human_error_is_closed_and_actionable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = DaemonClientError(
        RemoteError(
            code="E200",
            message="Bearer credential at https://backend/private/path",
            technical_detail="prompt body",
        ),
        request_id="req-down",
    )
    monkeypatch.setattr(
        cli_module,
        "_client_factory",
        lambda _path: FakeClient(health_error=failure),
    )

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 3
    assert result.stdout == ""
    assert result.stderr == (
        "ERROR E200 · Daemon unavailable\n"
        "What happened: the private control socket could not be reached.\n"
        "Next: omlxc daemon status\n"
        "Request: req-down\n"
    )


def test_status_human_degraded_output_is_guided_and_uses_one_health_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DegradedClient(FakeClient):
        async def health(self) -> DaemonEnvelope:
            self.calls.append(("health",))
            return _envelope({"status": "not-ready", "degraded": True, "policy": "strict"})

    client = DegradedClient()
    monkeypatch.setattr(cli_module, "_client_factory", lambda _path: client)

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert result.stdout == (
        "WARNING · Daemon is running in degraded mode\n"
        "  Status: degraded\n"
        "  Degraded: yes\n"
        "  Policy: strict\n"
        "  Jobs: not checked by status\n\n"
        "Next\n"
        "  omlxc doctor\n"
        "  omlxc nodes list\n"
        "  omlxc jobs list\n"
    )
    assert result.stderr == ""
    assert client.calls == [("health",)]


def test_status_human_malformed_health_fails_closed_without_echoing_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hostile_data = ["https://backend/private/path", "prompt body"]
    monkeypatch.setattr(cli_module, "_request_id", lambda: "req-malformed")

    class MalformedClient(FakeClient):
        async def health(self) -> DaemonEnvelope:
            self.calls.append(("health",))
            return _envelope(hostile_data)

    client = MalformedClient()
    monkeypatch.setattr(cli_module, "_client_factory", lambda _path: client)

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 10
    assert result.stdout == ""
    assert result.stderr == (
        "ERROR E900 · Internal client error\n"
        "What happened: the client could not safely process the response.\n"
        "Next: omlxc status\n"
        "Request: req-malformed\n"
    )
    assert "https://backend/private/path" not in result.stderr
    assert "prompt body" not in result.stderr
    assert "traceback" not in result.stderr.lower()
    assert client.calls == [("health",)]


def test_status_json_malformed_health_remains_original_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hostile_data = ["https://backend/private/path", "prompt body"]

    class MalformedClient(FakeClient):
        async def health(self) -> DaemonEnvelope:
            self.calls.append(("health",))
            return _envelope(hostile_data)

    client = MalformedClient()
    monkeypatch.setattr(cli_module, "_client_factory", lambda _path: client)

    result = runner.invoke(app, ["status", "--json"])

    assert result.exit_code == 0
    assert result.stdout == (
        '{"schema_version":1,"request_id":"req-cli-1",'
        '"data":["https://backend/private/path","prompt body"]}\n'
    )
    assert result.stderr == ""
    assert client.calls == [("health",)]


def test_local_human_safety_error_is_closed_without_hostile_message(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli_module, "_request_id", lambda: "req-local")

    with pytest.raises(typer.Exit) as exc_info:
        cli_module._fail_local(
            "E700",
            "hostile https://backend/private/path prompt body",
            json_output=False,
        )
    captured = capsys.readouterr()

    assert exc_info.value.exit_code == 7
    assert captured.out == ""
    assert captured.err == (
        "ERROR E700 · Safety confirmation required\n"
        "What happened: the requested operation is protected by an explicit safety gate.\n"
        "Request: req-local\n"
    )
    assert "https://backend/private/path" not in captured.err
    assert "prompt body" not in captured.err


def test_cached_doctor_human_health_failure_uses_closed_status_wording(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = DaemonClientError(
        RemoteError(code="E200", message="Bearer credential at https://backend/private/path"),
        request_id="req-doctor-down",
    )
    monkeypatch.setattr(
        cli_module,
        "_client_factory",
        lambda _path: FakeClient(health_error=failure),
    )

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 3
    assert result.stdout == ""
    assert result.stderr == (
        "ERROR E200 · Daemon unavailable\n"
        "What happened: the private control socket could not be reached.\n"
        "Next: omlxc daemon status\n"
        "Request: req-doctor-down\n"
    )


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
