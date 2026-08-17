"""Unit tests for V2 Cognitive & Governance subcommands in Cockpit."""

from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

from cockpit.commands.cartridge import cmd_cartridge
from cockpit.commands.challenge import cmd_challenge
from cockpit.commands.fabric import cmd_fabric
from cockpit.commands.intent import cmd_intent


@patch("subprocess.run")
def test_cmd_intent_delegation(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="IntentSpec: OK\n", stderr="")
    args = argparse.Namespace(prompt=["卫健委立项规划"], domain="work-weijian", json=False)
    rc = cmd_intent(args)
    assert rc == 0
    mock_run.assert_called_once()
    cmd_args = mock_run.call_args[0][0]
    assert "ecos-constraint" in cmd_args
    assert "intent" in cmd_args
    assert "compile" in cmd_args


@patch("subprocess.run")
def test_cmd_challenge_delegation(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="ShadowReport: PASS\n", stderr="")
    args = argparse.Namespace(target="proposal.md", domain="work-weijian", auto_patch=True, strict=False, json=False)
    rc = cmd_challenge(args)
    assert rc == 0
    mock_run.assert_called_once()
    cmd_args = mock_run.call_args[0][0]
    assert "ecos-constraint" in cmd_args
    assert "challenge" in cmd_args
    assert "--auto-patch" in cmd_args


@patch("subprocess.run")
def test_cmd_cartridge_delegation(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="cartridge-weijian-v1\n", stderr="")
    args = argparse.Namespace(action="list", cartridge_id=None, output=None, file_path=None)
    rc = cmd_cartridge(args)
    assert rc == 0
    mock_run.assert_called_once()
    cmd_args = mock_run.call_args[0][0]
    assert "ecos-constraint" in cmd_args
    assert "cartridge" in cmd_args
    assert "list" in cmd_args


@patch("subprocess.run")
def test_cmd_fabric_delegation(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="Snapshot: WARMED\n", stderr="")
    args = argparse.Namespace(action="snapshot", snapshot_action="warm", name="mof-governance-v3", model=None)
    rc = cmd_fabric(args)
    assert rc == 0
    mock_run.assert_called_once()
    cmd_args = mock_run.call_args[0][0]
    assert "omlxc" in cmd_args
    assert "fabric" in cmd_args
    assert "snapshot" in cmd_args
