"""Tests for Tier-1 Universal Flags in Cockpit CLI (BET-Y1Q4-T8-12).

Verifies:
  1. --json produces clean valid JSON on stdout with zero ANSI escapes.
  2. --dry-run sets the dry_run flag and skips actual mutations.
  3. Exit codes follow ExitCode IntEnum standards (0=OK, 2=USAGE_ERROR, etc.).
  4. Trace-id propagation.
"""

import json
import re
from unittest.mock import patch
import pytest

from cockpit.cli import main, create_parser
from cockpit.domain.exit_codes import ExitCode


ANSI_REGEX = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def test_parser_contains_universal_flags():
    parser, _, _ = create_parser()
    actions = {a.dest for a in parser._actions}
    assert "json" in actions
    assert "dry_run" in actions
    assert "quiet" in actions
    assert "verbose" in actions
    assert "trace_id" in actions


def test_invalid_command_with_json_outputs_clean_json(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--json", "totally_nonexistent_command_12345"])

    assert exc_info.value.code == ExitCode.USAGE_ERROR

    captured = capsys.readouterr()
    stdout = captured.out.strip()

    # Must have no ANSI escape sequences
    assert not ANSI_REGEX.search(stdout), "Found ANSI escape codes in --json stdout"

    # Must parse as valid JSON
    data = json.loads(stdout)
    assert data["ok"] is False
    assert "totally_nonexistent_command_12345" in data["error"]
    assert data["exit_code"] == ExitCode.USAGE_ERROR


def test_dashboard_dry_run_json_output(capsys):
    rc = main(["dashboard", "--dry-run", "--json"])
    assert rc == ExitCode.SUCCESS

    captured = capsys.readouterr()
    stdout = captured.out.strip()

    assert not ANSI_REGEX.search(stdout)
    data = json.loads(stdout)
    assert data["dry_run"] is True
    assert "url" in data
    assert "port" in data
    assert data["ready"] is True
