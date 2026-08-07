"""Tests for cockpit.commands.bus — cmd_bus data/control subcommands.

These complement test_cli_main_routing.py (which asserts `bus status`
routes to cmd_bus) by exercising the P4-added data/control surfaces:
- `bus data` emits via bus_foundation.facade.data.emit (fire-and-forget)
- `bus control` submits / acks / nacks via bus_foundation.facade.control
"""

from __future__ import annotations

import argparse
from typing import Any

import pytest

from cockpit.commands.bus import cmd_bus, main


def _ns(**kwargs: Any) -> argparse.Namespace:
    return argparse.Namespace(**kwargs)


# ── data subcommand ────────────────────────────────────────────────


def test_data_emit_dispatches(monkeypatch: pytest.MonkeyPatch) -> None:
    """cmd_bus data routes to facade.data.emit with parsed payload."""
    import bus_foundation.facade.data as data_facade

    calls: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(data_facade, "emit", lambda topic, payload, **kw: calls.append((topic, payload)))

    rc = cmd_bus(_ns(bus_command="data", topic="sensor.temp", payload='{"value": 36.5}'))

    assert rc == 0
    assert calls == [("sensor.temp", {"value": 36.5})]


def test_data_missing_topic_returns_1(monkeypatch: pytest.MonkeyPatch) -> None:
    import bus_foundation.facade.data as data_facade

    monkeypatch.setattr(data_facade, "emit", lambda *a, **k: None)

    rc = cmd_bus(_ns(bus_command="data", topic=None, payload="{}"))

    assert rc == 1


def test_data_invalid_json_returns_1(monkeypatch: pytest.MonkeyPatch) -> None:
    import bus_foundation.facade.data as data_facade

    monkeypatch.setattr(data_facade, "emit", lambda *a, **k: None)

    rc = cmd_bus(_ns(bus_command="data", topic="sensor.temp", payload="{bad"))

    assert rc == 1


# ── control subcommand ─────────────────────────────────────────────


def test_control_submit(monkeypatch: pytest.MonkeyPatch) -> None:
    """control submit routes to facade.control.submit_task and prints the task id."""
    import bus_foundation.facade.control as control_facade

    submitted: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(
        control_facade, "submit_task", lambda topic, payload, **kw: submitted.append((topic, payload)) or "task-1"
    )

    rc = cmd_bus(_ns(bus_command="control", control_command="submit", topic="job.run", payload='{"x": 1}'))

    assert rc == 0
    assert submitted == [("job.run", {"x": 1})]


def test_control_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    """control ack routes to facade.control.ack with the task id."""
    import bus_foundation.facade.control as control_facade

    acked: list[str] = []
    monkeypatch.setattr(control_facade, "ack", lambda task_id: acked.append(task_id))

    rc = cmd_bus(_ns(bus_command="control", control_command="ack", task_id="task-1"))

    assert rc == 0
    assert acked == ["task-1"]


def test_control_nack(monkeypatch: pytest.MonkeyPatch) -> None:
    """control nack routes to facade.control.nack with task id + error."""
    import bus_foundation.facade.control as control_facade

    nacked: list[tuple[str, str]] = []
    monkeypatch.setattr(control_facade, "nack", lambda task_id, error: nacked.append((task_id, error)))

    rc = cmd_bus(_ns(bus_command="control", control_command="nack", task_id="task-1", error="boom"))

    assert rc == 0
    assert nacked == [("task-1", "boom")]


def test_control_unknown_action_returns_1(monkeypatch: pytest.MonkeyPatch) -> None:
    import bus_foundation.facade.control as control_facade

    monkeypatch.setattr(control_facade, "submit_task", lambda *a, **k: "x")

    rc = cmd_bus(_ns(bus_command="control", control_command=None))

    assert rc == 1


# ── module entry point help ────────────────────────────────────────


def test_main_help_lists_data_and_control(capsys: pytest.CaptureFixture[str]) -> None:
    """`python -m cockpit.commands.bus --help` exposes data/control subcommands."""
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "data" in out
    assert "control" in out


def test_main_data_help_shows_topic_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["data", "--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "--topic" in out
    assert "--payload" in out


def test_main_control_help_shows_actions(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["control", "--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for action in ("submit", "ack", "nack"):
        assert action in out


# ── full CLI registration (cli.py) ────────────────────────────────


class TestFullCliRegistration:
    @pytest.mark.parametrize(
        "argv",
        [
            ["workspace", "bus", "data", "--topic", "sensor.temp", "--payload", "{}"],
            ["workspace", "bus", "control", "submit", "--topic", "job.run", "--payload", "{}"],
            ["workspace", "bus", "control", "ack", "--task-id", "task-1"],
            ["workspace", "bus", "control", "nack", "--task-id", "task-1", "--error", "boom"],
        ],
    )
    def test_bus_subcommands_dispatch(self, monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> None:
        """cli.main() parses the new subcommands and routes them to cmd_bus."""
        import sys
        from unittest.mock import MagicMock

        from cockpit import cli

        monkeypatch.setattr(sys, "argv", argv)
        mock_fn = MagicMock(return_value=0)
        monkeypatch.setattr(cli, "cmd_bus", mock_fn, raising=False)

        assert cli.main() == 0
        mock_fn.assert_called_once()

    def test_bus_data_help_via_full_cli(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`cockpit bus data --help` renders the data subcommand through the full CLI."""
        import sys

        from cockpit import cli

        monkeypatch.setattr(sys, "argv", ["workspace", "bus", "data", "--help"])
        with pytest.raises(SystemExit) as exc:
            cli.main()
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "--topic" in out
        assert "--payload" in out

    def test_bus_control_help_via_full_cli(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`cockpit bus control --help` renders submit/ack/nack through the full CLI."""
        import sys

        from cockpit import cli

        monkeypatch.setattr(sys, "argv", ["workspace", "bus", "control", "--help"])
        with pytest.raises(SystemExit) as exc:
            cli.main()
        assert exc.value.code == 0
        out = capsys.readouterr().out
        for action in ("submit", "ack", "nack"):
            assert action in out
