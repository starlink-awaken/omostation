"""Tests for CLI reference documentation generator (BET-Y1Q4-T8-16)."""

import json
from pathlib import Path

from cockpit.cli import main
from cockpit.domain.exit_codes import ExitCode
from cockpit.commands.docs import generate_cli_reference_markdown


def test_generate_cli_reference_content():
    content = generate_cli_reference_markdown()
    assert "# Cockpit CLI Reference Manual" in content
    assert "Global Flags & Universal Contract" in content
    assert "Standard Exit Codes" in content
    assert "The 8 Orthogonal Domains" in content
    assert "Command Catalog" in content
    assert "Observability & Prometheus Telemetry" in content
    assert "Shell Auto-completion" in content


def test_cli_docs_dry_run_json(capsys):
    rc = main(["docs", "--dry-run", "--json"])
    assert rc == ExitCode.SUCCESS
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["dry_run"] is True
    assert "target_file" in data
    assert data["bytes_to_write"] > 1000


def test_cli_docs_export_custom_path(tmp_path: Path, capsys):
    target = tmp_path / "CUSTOM_REF.md"
    rc = main(["docs", "export", "-o", str(target), "--json"])
    assert rc == ExitCode.SUCCESS
    assert target.is_file()
    text = target.read_text(encoding="utf-8")
    assert "Cockpit CLI Reference Manual" in text
