from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

from cockpit import cli
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
