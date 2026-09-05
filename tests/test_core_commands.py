"""BET-Y1Q4-T8-13: P0 core command dry-run / JSON contract.

Covers all 9 P0 commands with --dry-run --json (or --json for pure-read
paths). Assertions use json.loads(stdout) so ANSI pollution fails loudly.

Consolidates coverage previously split across:
  - test_dashboard_modernized.py
  - test_modernized_p0_commands.py
  - test_modernized_p0_wave2.py
"""

from __future__ import annotations

import json
import re

from cockpit.cli import main
from cockpit.domain.exit_codes import ExitCode

ANSI_REGEX = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

P0_COMMANDS = (
    "dashboard",
    "quickstart",
    "journey",
    "capabilities",
    "data",
    "iterate",
    "workflow",
    "compass",
    "brain",
)


def _parse_json_stdout(capsys) -> dict | list:
    captured = capsys.readouterr()
    stdout = captured.out.strip()
    assert stdout, "expected non-empty stdout for --json"
    assert not ANSI_REGEX.search(stdout), f"ANSI found in --json stdout: {stdout[:200]!r}"
    return json.loads(stdout)


def test_p0_commands_listed_in_json_capable():
    from cockpit.commands.output_mode import JSON_CAPABLE

    missing = [c for c in P0_COMMANDS if c not in JSON_CAPABLE]
    assert missing == [], f"P0 commands missing from JSON_CAPABLE: {missing}"


def test_dashboard_dry_run_json(capsys):
    rc = main(["dashboard", "--dry-run", "--json"])
    assert rc == ExitCode.SUCCESS
    data = _parse_json_stdout(capsys)
    assert data["dry_run"] is True
    assert "url" in data
    assert "port" in data
    assert "ready" in data


def test_quickstart_dry_run_json(capsys):
    rc = main(["quickstart", "--dry-run", "--json"])
    assert rc == ExitCode.SUCCESS
    data = _parse_json_stdout(capsys)
    assert isinstance(data, list)
    items = {d["item"] for d in data}
    assert "Python 版本" in items
    assert "Workspace 数据库" in items


def test_journey_dry_run_json(capsys):
    rc = main(["journey", "--dry-run", "--json"])
    assert rc == ExitCode.SUCCESS
    data = _parse_json_stdout(capsys)
    assert data["dry_run"] is True
    assert data["runner_exists"] is True
    assert data["journey_specs_count"] > 0


def test_capabilities_dry_run_json(capsys):
    rc = main(["capabilities", "--dry-run", "--json"])
    assert rc == ExitCode.SUCCESS
    data = _parse_json_stdout(capsys)
    assert data["dry_run"] is True


def test_capabilities_source_filter_json(capsys):
    rc = main(["capabilities", "--source", "bos", "--limit", "2", "--json"])
    assert rc == ExitCode.SUCCESS
    data = _parse_json_stdout(capsys)
    assert data["total"] == 2
    assert data["source_filter"] == "bos"
    for cap in data["capabilities"]:
        assert cap["source"] == "bos"


def test_data_summary_json(capsys):
    """Top-level data is pure-read; --json is the contract path."""
    rc = main(["data", "--json"])
    assert rc == ExitCode.SUCCESS
    data = _parse_json_stdout(capsys)
    assert data["status"] == "ok"
    assert "registered_types_count" in data
    assert "available_commands" in data


def test_data_gc_dry_run_json(capsys):
    rc = main(["data", "gc", "--dry-run", "--json"])
    assert rc == ExitCode.SUCCESS
    data = _parse_json_stdout(capsys)
    assert data["dry_run"] is True
    assert data.get("ready") is True or "deleted_paths" in data


def test_iterate_fast_track_dry_run_json(capsys):
    rc = main(["iterate", "自动化测试任务", "--fast-track", "--dry-run", "--json"])
    assert rc == ExitCode.SUCCESS
    data = _parse_json_stdout(capsys)
    assert data["ok"] is True
    assert data["mode"] == "fast_track"
    assert data["dry_run"] is True
    assert "FAST-" in data["task_id"]


def test_workflow_dry_run_json(capsys):
    rc = main(["workflow", "--dry-run", "--json"])
    assert rc == ExitCode.SUCCESS
    data = _parse_json_stdout(capsys)
    assert data["status"] == "ok"
    assert "engines" in data
    assert "available_subcommands" in data
    assert data.get("dry_run") is True


def test_compass_dry_run_json(capsys):
    rc = main(["compass", "--dry-run", "--json"])
    assert rc == ExitCode.SUCCESS
    data = _parse_json_stdout(capsys)
    assert data["status"] == "ok"
    assert data["pipeline"] == "Concept-to-Goal (C2G)"
    assert "brainstorm" in data["subcommands"]
    assert data.get("dry_run") is True


def test_brain_context_dry_run_json(capsys):
    rc = main(["brain", "context", "--dry-run", "--json"])
    assert rc == ExitCode.SUCCESS
    data = _parse_json_stdout(capsys)
    assert data["status"] == "ok"
    assert "preferences" in data
    assert "recent_history" in data
    assert data.get("dry_run") is True


def test_output_json_alias_for_dashboard(capsys):
    """-o json / --output json must inject --json for JSON_CAPABLE commands."""
    rc = main(["-o", "json", "dashboard", "--dry-run"])
    assert rc == ExitCode.SUCCESS
    data = _parse_json_stdout(capsys)
    assert data["dry_run"] is True
