"""Tests for Modernized P0 Command Group in Phase 2 (BET-Y1Q4-T8-13).

Verifies:
  1. quickstart --dry-run --json returns structured checks.
  2. journey --dry-run --json returns spec count.
  3. capabilities --source bos --limit 2 --json filters correctly.
  4. data --json returns top-level summary.
  5. iterate --fast-track --dry-run --json generates valid non-blocking task structure.
"""

import json
import pytest

from cockpit.cli import main
from cockpit.domain.exit_codes import ExitCode


def test_quickstart_dry_run_json(capsys):
    rc = main(["quickstart", "--dry-run", "--json"])
    assert rc == ExitCode.SUCCESS

    captured = capsys.readouterr()
    data = json.loads(captured.out.strip())
    assert isinstance(data, list)
    items = {d["item"] for d in data}
    assert "Python 版本" in items
    assert "Workspace 数据库" in items


def test_journey_dry_run_json(capsys):
    rc = main(["journey", "--dry-run", "--json"])
    assert rc == ExitCode.SUCCESS

    captured = capsys.readouterr()
    data = json.loads(captured.out.strip())
    assert data["dry_run"] is True
    assert data["runner_exists"] is True
    assert data["journey_specs_count"] > 0


def test_capabilities_source_filter_json(capsys):
    rc = main(["capabilities", "--source", "bos", "--limit", "2", "--json"])
    assert rc == ExitCode.SUCCESS

    captured = capsys.readouterr()
    data = json.loads(captured.out.strip())
    assert data["total"] == 2
    assert data["source_filter"] == "bos"
    for cap in data["capabilities"]:
        assert cap["source"] == "bos"


def test_data_summary_json(capsys):
    rc = main(["data", "--json"])
    assert rc == ExitCode.SUCCESS

    captured = capsys.readouterr()
    data = json.loads(captured.out.strip())
    assert data["status"] == "ok"
    assert "registered_types_count" in data
    assert "available_commands" in data


def test_iterate_fast_track_dry_run_json(capsys):
    rc = main(["iterate", "自动化测试任务", "--fast-track", "--dry-run", "--json"])
    assert rc == ExitCode.SUCCESS

    captured = capsys.readouterr()
    data = json.loads(captured.out.strip())
    assert data["ok"] is True
    assert data["mode"] == "fast_track"
    assert data["dry_run"] is True
    assert "FAST-" in data["task_id"]
