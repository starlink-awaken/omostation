"""Tests for modernized P0 commands (Wave 2: workflow, compass, brain, --version fast path)."""

import json

from cockpit.cli import main
from cockpit.domain.exit_codes import ExitCode


def test_version_fast_path(capsys):
    rc = main(["--version"])
    assert rc == ExitCode.SUCCESS
    captured = capsys.readouterr()
    assert "cockpit v" in captured.out


def test_workflow_dry_run_json(capsys):
    rc = main(["workflow", "--dry-run", "--json"])
    assert rc == ExitCode.SUCCESS
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "ok"
    assert "engines" in data
    assert "available_subcommands" in data
    assert data.get("dry_run") is True


def test_compass_dry_run_json(capsys):
    rc = main(["compass", "--dry-run", "--json"])
    assert rc == ExitCode.SUCCESS
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "ok"
    assert data["pipeline"] == "Concept-to-Goal (C2G)"
    assert "brainstorm" in data["subcommands"]
    assert data.get("dry_run") is True


def test_brain_context_dry_run_json(capsys):
    rc = main(["brain", "context", "--dry-run", "--json"])
    assert rc == ExitCode.SUCCESS
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "ok"
    assert "preferences" in data
    assert "recent_history" in data
    assert data.get("dry_run") is True
