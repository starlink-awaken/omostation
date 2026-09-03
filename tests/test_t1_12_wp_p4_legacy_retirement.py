"""Regression test for BET-Y1Q3-T1-12 WP-P4: legacy empty-grant retirement.

Ensures the retired Phase8 bypass surfaces (bin/gac/daemon-watchdog.py and
bin/ssot/real-scenario-runner.py) stay retired as compatibility-only reject
paths, never re-activated as effectful dispatch.

Reference: docs/superpowers/specs/2026-08-24-exact-capability-binding-design.md
"BET-Y1Q3-T1-12 done_when: legacy 空 capability grant 与 KEMS 裸派工路径
被删除、接线或显式下线"
"被退役命令非零退出、零写入、provider/router/gateway 调用为 0"
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]  # worktree root


def _run_command(script_relpath: str) -> subprocess.CompletedProcess:
    """Run a bin/ script with PYTHONPATH so cockpit.env_resolver resolves."""
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{WORKSPACE}/lib:{WORKSPACE}/projects/cockpit/src:{env.get('PYTHONPATH', '')}"
    return subprocess.run(
        [sys.executable, script_relpath],
        cwd=WORKSPACE,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_daemon_watchdog_refuses_with_retired_status():
    """bin/gac/daemon-watchdog.py must return ok=False, status=retired, exit=2."""
    r = _run_command("bin/gac/daemon-watchdog.py")
    assert r.returncode == 2, f"expected exit 2, got {r.returncode}: {r.stdout!r}"
    payload = json.loads(r.stdout)
    assert payload["ok"] is False
    assert payload["status"] == "retired"
    assert payload["value_indicator_policy"] is False
    assert "Cockpit PR #78" in payload["retirement_evidence"]
    assert "Mesh" in payload["successor"]


def test_real_scenario_runner_refuses_with_retired_status():
    """bin/ssot/real-scenario-runner.py must return ok=False, status=retired, exit=2."""
    r = _run_command("bin/ssot/real-scenario-runner.py")
    assert r.returncode == 2, f"expected exit 2, got {r.returncode}: {r.stdout!r}"
    payload = json.loads(r.stdout)
    assert payload["ok"] is False
    assert payload["status"] == "retired"
    assert payload["value_indicator_policy"] is False
    assert "Cockpit PR #78" in payload["retirement_evidence"]


def test_bin_omostation_does_not_exist():
    """The bin/omostation root wrapper bypass was retired by PR #2215 / #2260."""
    assert not (WORKSPACE / "bin" / "omostation").exists(), (
        "bin/omostation must remain removed (PR #2215/#2260 retirement evidence)"
    )


def test_script_registry_marks_retired_surfaces_deprecated():
    """Script-registry entries must mark both retired surfaces as deprecated."""
    import yaml
    for script_id in ("bin/gac/daemon-watchdog.py", "bin/ssot/real-scenario-runner.py"):
        # Find registry yaml by id
        with open(WORKSPACE / "bin" / "_registry" / "scripts" / "governance" / f"{Path(script_id).stem}.yaml") as f:
            data = yaml.safe_load(f)
        assert data["id"] == script_id
        assert data["maturity"] == "deprecated", (
            f"{script_id} should be marked deprecated, got: {data.get('maturity')}"
        )
