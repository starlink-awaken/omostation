"""Contract tests for the six-hour Cockpit CLI availability probe."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_cli_probe_is_registered_on_the_six_hour_schedule() -> None:
    cron_registry = yaml.safe_load(
        (ROOT / ".omo/cron/registry.yaml").read_text(encoding="utf-8")
    )
    entries = {
        entry["name"]: entry
        for entry in cron_registry["jobs"]
        if isinstance(entry, dict) and entry.get("name")
    }
    assert "cli-availability-probe-daily" not in entries
    entry = entries["cli-availability-probe-6h"]
    assert entry["schedule"] == "15 */6 * * *"
    assert entry["status"] == "active"
    assert entry["reality"] == "installed"
    assert "crontab" in entry["planes"]
    assert "cli-availability-probe.sh" in entry["command"]


def test_cli_probe_script_registry_matches_the_six_hour_contract() -> None:
    script_registry = yaml.safe_load(
        (
            ROOT / "bin/_registry/scripts/governance/cli-availability-probe.yaml"
        ).read_text(encoding="utf-8")
    )
    assert script_registry["maturity"] == "active"
    triggers = [
        trigger
        for trigger in script_registry["triggers"]
        if trigger.get("type") == "cron"
    ]
    assert triggers
    assert all(trigger["schedule"] == "15 */6 * * *" for trigger in triggers)
