import pytest
from pathlib import Path
from c2g.domain import PitchSchema
from c2g.adapters_local import LocalGovernanceProvider, LocalStorageProvider
import subprocess

def test_domain_schema():
    pitch = PitchSchema(pitch_id="1", title="Test", content="Data", created_at="2026-06-15")
    assert pitch.title == "Test"

def test_local_governance():
    gov = LocalGovernanceProvider()
    pitch = PitchSchema(pitch_id="1", title="Test", content="Data", created_at="2026-06-15")
    assert gov.validate_pitch(pitch) == True
    pitch_short = PitchSchema(pitch_id="1", title="Te", content="Data", created_at="2026-06-15")
    assert gov.validate_pitch(pitch_short) == False

def test_cli_help():
    result = subprocess.run(["uv", "run", "--project", ".", "c2g", "--help"], cwd="projects/c2g", capture_output=True, text=True)
    assert result.returncode == 0
    assert "brainstorm" in result.stdout

def test_cli_local_radar():
    result = subprocess.run(["uv", "run", "--project", ".", "c2g", "--adapter", "local", "radar"], cwd="projects/c2g", capture_output=True, text=True)
    assert result.returncode == 0
    assert "No active Bets" in result.stdout or "Active Bets retrieved" in result.stdout

def test_cli_local_gc():
    result = subprocess.run(["uv", "run", "--project", ".", "c2g", "--adapter", "local", "gc"], cwd="projects/c2g", capture_output=True, text=True)
    assert result.returncode == 0
    assert "GC 完成" in result.stdout
