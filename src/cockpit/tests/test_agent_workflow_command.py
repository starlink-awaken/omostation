from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

from cockpit import cli
from cockpit.commands import governance as governance_cmd
from cockpit.commands.agent_workflow import WORKSPACE, cmd_agent_workflow


def test_agent_workflow_defaults_to_list(monkeypatch) -> None:
    mock_call = MagicMock(return_value=0)
    monkeypatch.setattr(subprocess, "call", mock_call)

    code = cmd_agent_workflow(argparse.Namespace(agent_workflow_args=[]))

    assert code == 0
    command = mock_call.call_args.args[0]
    assert command[:5] == ["uv", "run", "--with", "pyyaml", "python"]
    assert command[5] == str(WORKSPACE / "bin" / "agent-workflow.py")
    assert command[6:] == ["list"]
    assert mock_call.call_args.kwargs["cwd"] == str(WORKSPACE)


def test_agent_workflow_forwards_arguments(monkeypatch) -> None:
    mock_call = MagicMock(return_value=0)
    monkeypatch.setattr(subprocess, "call", mock_call)

    code = cmd_agent_workflow(
        argparse.Namespace(agent_workflow_args=["show", "project-code-change", "--project", "omo"])
    )

    assert code == 0
    command = mock_call.call_args.args[0]
    assert command[6:] == ["show", "project-code-change", "--project", "omo"]


def test_cli_routes_agent_workflow(monkeypatch) -> None:
    mock_call = MagicMock(return_value=0)
    monkeypatch.setattr(subprocess, "call", mock_call)
    monkeypatch.setattr(sys, "argv", ["cockpit", "agent-workflow", "doctor"])

    code = cli.main()

    assert code == 0
    command = mock_call.call_args.args[0]
    assert Path(command[5]).name == "agent-workflow.py"
    assert command[6:] == ["doctor"]


def test_agent_alias_defaults_to_bootstrap(monkeypatch) -> None:
    mock_call = MagicMock(return_value=0)
    monkeypatch.setattr(subprocess, "call", mock_call)

    code = cmd_agent_workflow(argparse.Namespace(command="agent", agent_args=[]))

    assert code == 0
    command = mock_call.call_args.args[0]
    assert command[6:] == ["bootstrap"]


def test_cli_routes_agent_alias(monkeypatch) -> None:
    mock_call = MagicMock(return_value=0)
    monkeypatch.setattr(subprocess, "call", mock_call)
    monkeypatch.setattr(sys, "argv", ["cockpit", "agent", "verify", "run-1", "--from-diff"])

    code = cli.main()

    assert code == 0
    command = mock_call.call_args.args[0]
    assert Path(command[5]).name == "agent-workflow.py"
    assert command[6:] == ["verify", "run-1", "--from-diff"]


def test_cli_routes_agent_status(monkeypatch) -> None:
    mock_call = MagicMock(return_value=0)
    monkeypatch.setattr(subprocess, "call", mock_call)
    monkeypatch.setattr(sys, "argv", ["cockpit", "agent", "status", "--json"])

    code = cli.main()

    assert code == 0
    command = mock_call.call_args.args[0]
    assert Path(command[5]).name == "agent-workflow.py"
    assert command[6:] == ["status", "--json"]


def test_cli_routes_governance_evolution(monkeypatch) -> None:
    completed = subprocess.CompletedProcess(args=[], returncode=0)
    mock_run = MagicMock(return_value=completed)
    monkeypatch.setattr(subprocess, "run", mock_run)
    monkeypatch.setattr(governance_cmd, "resolve_workspace_root", lambda: WORKSPACE)
    monkeypatch.setattr(sys, "argv", ["cockpit", "governance", "evolution", "validate", "--json"])

    code = cli.main()

    assert code == 0
    command = mock_run.call_args.args[0]
    assert command[:5] == ["uv", "run", "--with", "pyyaml", "python"]
    assert Path(command[5]).name == "governance-evolution.py"
    assert command[6:] == ["validate", "--json"]
