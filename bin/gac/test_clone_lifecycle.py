#!/usr/bin/env python3
"""clone-lifecycle.py 集成测试 — 自动化 clone 生命周期管道."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

_BIN_GAC = Path(__file__).resolve().parent
sys.path.insert(0, str(_BIN_GAC))
sys.path.insert(0, str(_BIN_GAC.parents[1]))

lc = importlib.import_module("clone-lifecycle")


def test_snapshot_creates_valid_manifest(tmp_path, monkeypatch):
    """snapshot 生成有效 manifest."""
    import subprocess
    # Use existing pilot clone as input
    pilot = Path.home() / "agents" / "pilot" / "ws"
    if not pilot.exists():
        return  # skip if no pilot
    output = tmp_path / "baseline.json"
    rc = lc.cmd_snapshot(argparse.Namespace(clone=str(pilot), output=str(output)))
    assert rc == 0
    d = json.loads(output.read_text())
    assert "root_head_sha" in d
    assert "repositories" in d


def test_changeset_no_change(tmp_path):
    """无变更时 changeset 正确检测."""
    pilot = Path.home() / "agents" / "pilot" / "ws"
    if not pilot.exists():
        return
    baseline = tmp_path / "base.json"
    # Generate baseline first
    lc.cmd_snapshot(argparse.Namespace(clone=str(pilot), output=str(baseline)))
    output = tmp_path / "cs.json"
    rc = lc.cmd_changeset(argparse.Namespace(
        clone=str(pilot), baseline=str(baseline), output=str(output), verify_claims=True,
    ))
    assert rc == 0
    cs = json.loads(output.read_text())
    assert cs["no_change"] is True
    assert cs["claim_verification"]["all_covered"] is True


def test_changeset_with_verify_claims(tmp_path):
    """claim 校验开启时输出包含 claim_verification."""
    pilot = Path.home() / "agents" / "pilot" / "ws"
    if not pilot.exists():
        return
    baseline = tmp_path / "base.json"
    lc.cmd_snapshot(argparse.Namespace(clone=str(pilot), output=str(baseline)))
    output = tmp_path / "cs.json"
    rc = lc.cmd_changeset(argparse.Namespace(
        clone=str(pilot), baseline=str(baseline), output=str(output), verify_claims=True,
    ))
    assert rc == 0
    cs = json.loads(output.read_text())
    assert "claim_verification" in cs
    assert cs["claim_verification"]["enabled"] is True


def test_integrate_dry_run(tmp_path, capsys):
    """integrate dry-run 不实际推送."""
    pilot = Path.home() / "agents" / "pilot" / "ws"
    if not pilot.exists():
        return
    rc = lc.cmd_integrate(argparse.Namespace(
        clone=str(pilot), agent_id="pilot", dry_run=True,
    ))
    assert rc == 0
    out = capsys.readouterr()
    assert "dry_run" in out.out


def test_retire_removes_clone(tmp_path, monkeypatch):
    """retire 清理 clone 目录."""
    # Create a temp dir to "retire"
    fake_clone = tmp_path / "fake_agent" / "ws"
    fake_clone.mkdir(parents=True)
    (fake_clone / "test.txt").write_text("data")
    rc = lc.cmd_retire(argparse.Namespace(destination=str(fake_clone)))
    assert rc == 0
    assert not fake_clone.exists()


def test_audit_logging(capsys, tmp_path):
    """审计日志输出到 stderr."""
    pilot = Path.home() / "agents" / "pilot" / "ws"
    if not pilot.exists():
        return
    output = tmp_path / "base.json"
    lc.cmd_snapshot(argparse.Namespace(clone=str(pilot), output=str(output)))
    err = capsys.readouterr().err
    assert "LIFECYCLE=snapshot_ok" in err


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
