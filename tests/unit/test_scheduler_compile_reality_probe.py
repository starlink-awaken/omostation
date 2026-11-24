"""Hermetic tests for scheduler-compile.py --probe-reality / --sync-reality."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "scheduler_compile_probe", WORKSPACE / "bin" / "scheduler-compile.py"
)
assert _SPEC and _SPEC.loader
sc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sc)


def test_probe_reality_detects_crontab_launchd_and_cli_alias() -> None:
    home = str(Path.home())
    jobs = [
        {
            "name": "cron-ok",
            "schedule": "0 3 * * *",
            "command": 'cd "$HOME/Workspace" && python3 bin/ssot/log-rotate.py --daily',
            "planes": ["crontab"],
            "reality": "crontab_installed",
            "status": "active",
        },
        {
            "name": "launchd-explicit",
            "label": "com.l4.resident.decision",
            "schedule": "every 120s",
            "command": '/bin/bash "$HOME/Workspace/lib/resident-role-tick.sh" decision',
            "planes": ["launchd"],
            "reality": "installed",
            "status": "active",
        },
        {
            "name": "debt-refresh-alias",
            "schedule": "30 10 * * 1",
            "command": 'cd "$HOME/Workspace" && uv run --project projects/omo omo debt refresh',
            "planes": ["crontab"],
            "reality": "declared_only",
            "status": "proposed",
        },
        {
            "name": "stale-claimed",
            "schedule": "0 4 * * *",
            "command": 'cd "$HOME/Workspace" && python3 bin/ssot/never-installed.py',
            "planes": ["crontab"],
            "reality": "installed",
            "status": "active",
        },
    ]
    crontab_lines = [
        f"0 3 * * * cd {home}/Workspace && /opt/homebrew/bin/python3 bin/ssot/log-rotate.py --daily"
    ]
    plists = {
        "com.l4.resident.decision": {
            "Label": "com.l4.resident.decision",
            "ProgramArguments": ["/bin/bash", f"{home}/Workspace/lib/resident-role-tick.sh", "decision"],
        },
        "com.omostation.omo-debt-refresh": {
            "Label": "com.omostation.omo-debt-refresh",
            "ProgramArguments": ["/bin/bash", "-c", "python -m omo.omo_debt_cli refresh"],
        },
    }

    report = sc.probe_reality(jobs=jobs, installed_crontab=crontab_lines, launchd_plists=plists)
    by_name = {e["name"]: e for e in report["entries"]}

    assert by_name["cron-ok"]["drift"] is False
    assert by_name["cron-ok"]["observed_planes"] == ["crontab"]
    assert by_name["launchd-explicit"]["drift"] is False
    assert by_name["launchd-explicit"]["matched_label"] == "com.l4.resident.decision"
    assert by_name["debt-refresh-alias"]["drift"] is True
    assert by_name["debt-refresh-alias"]["observed_reality"] == "installed"
    assert by_name["debt-refresh-alias"]["matched_label"] == "com.omostation.omo-debt-refresh"
    assert by_name["stale-claimed"]["drift"] is True
    assert by_name["stale-claimed"]["observed_reality"] == "declared_only"
    assert report["ok"] is False
    assert report["mismatch_count"] == 2


def test_sync_reality_dry_run_and_atomic_update_preserve_invariants(tmp_path: Path) -> None:
    reg = tmp_path / "registry.yaml"
    original = (
        "# header comment\n"
        "version: 2\n"
        "jobs:\n"
        "  - name: drifted-to-installed\n"
        "    schedule: '5,35 * * * *'\n"
        "    command: 'cd \"$HOME/Workspace\" && uv run --project projects/omo omo debt refresh'\n"
        "    planes: [launchd]\n"
        "    reality: declared_only\n"
        "    status: proposed\n"
        "  - name: drifted-to-declared\n"
        "    schedule: '0 4 * * *'\n"
        "    command: 'cd \"$HOME/Workspace\" && python3 bin/ssot/removed.py'\n"
        "    planes: [crontab]\n"
        "    reality: installed\n"
        "    status: active\n"
    )
    reg.write_text(original, encoding="utf-8")
    plists = {
        "com.omostation.omo-debt-refresh": {
            "Label": "com.omostation.omo-debt-refresh",
            "ProgramArguments": ["/bin/bash", "-c", "python -m omo.omo_debt_cli refresh"],
        }
    }

    dry = sc.sync_reality(reg, installed_crontab=[], launchd_plists=plists, dry_run=True)
    assert dry["ok"] is True and dry["applied"] is False and dry["updated_count"] == 2
    assert reg.read_text(encoding="utf-8") == original

    applied = sc.sync_reality(reg, installed_crontab=[], launchd_plists=plists, dry_run=False)
    assert applied["ok"] is True and applied["applied"] is True and applied["updated_count"] == 2

    updated_text = reg.read_text(encoding="utf-8")
    assert "# header comment" in updated_text
    parsed = yaml.safe_load(updated_text)
    by_name = {j["name"]: j for j in parsed["jobs"]}
    assert by_name["drifted-to-installed"]["reality"] == "installed"
    assert by_name["drifted-to-installed"]["status"] == "active"
    assert by_name["drifted-to-declared"]["reality"] == "declared_only"
    assert by_name["drifted-to-declared"]["status"] == "proposed"


def test_real_registry_debt_refresh_weekly_is_active_launchd_installed() -> None:
    docs = [d for d in yaml.safe_load_all((WORKSPACE / ".omo/cron/registry.yaml").read_text(encoding="utf-8")) if d]
    jobs = {j["name"]: j for j in docs[-1]["jobs"] if isinstance(j, dict) and j.get("name")}
    entry = jobs["debt-refresh-weekly"]
    assert entry["label"] == "com.omostation.omo-debt-refresh"
    assert entry["planes"] == ["launchd"]
    assert entry["reality"] == "installed"
    assert entry["status"] == "active"
