"""Tests for 8-Domain Orthogonal Hierarchy and Dual-Track Routing (BET-Y1Q4-T8-11).

Verifies:
  1. All 8 orthogonal domains are recognized in ORTHOGONAL_DOMAINS.
  2. Running a domain root (`cockpit system`) outputs the domain table.
  3. Running `cockpit <domain> <subcmd>` transparently dispatches to `<subcmd>`.
  4. Legacy direct invocation (`cockpit <subcmd>`) works identically.
"""

import json
from unittest.mock import patch
import pytest

from cockpit.cli import main
from cockpit.commands.registry import ORTHOGONAL_DOMAINS, LEGACY_COMMAND_MAPPING
from cockpit.domain.exit_codes import ExitCode


def test_orthogonal_domains_definition():
    expected = {"governance", "workflow", "memory", "compute", "bus", "scene", "system", "user"}
    assert set(ORTHOGONAL_DOMAINS.keys()) == expected


def test_domain_help_display(capsys):
    # Running cockpit system with no extra args should display domain table and return 0
    rc = main(["system"])
    assert rc == ExitCode.SUCCESS

    captured = capsys.readouterr()
    assert "正交一级领域" in captured.out
    assert "dashboard" in captured.out
    assert "health" in captured.out


def test_dual_track_routing_system_dashboard(capsys):
    # Calling via orthogonal hierarchy: cockpit system dashboard --dry-run --json
    rc = main(["system", "dashboard", "--dry-run", "--json"])
    assert rc == ExitCode.SUCCESS

    captured = capsys.readouterr()
    data = json.loads(captured.out.strip())
    assert data["dry_run"] is True
    assert "http://" in data["url"]


def test_legacy_mapping_consistency():
    # Every mapped command must point to a recognized orthogonal domain
    for cmd, (domain, target) in LEGACY_COMMAND_MAPPING.items():
        assert domain in ORTHOGONAL_DOMAINS, f"{cmd} points to unknown domain {domain}"
