#!/usr/bin/env python3
"""check-adversarial-effectiveness: warn when adversarial tests all pass.

If 100% of adversarial scenarios pass, the adversarial set is likely
too weak to be meaningful. This is the only gate where "all green =
warning".

Data sources:
  1. `.omo/state/collab-dualtrack.yaml` — adversarial fail rate
  2. `.omo/_delivery/collab-scenarios/` — count GEN-ADV* files and
     their pass/fail status from the scenario runner results

Output:
  - exit 0 = adversarial set is effective (some failures) or no data
  - exit 1 = all adversarial scenarios pass = "adversarial insufficient"
    (blocking per P84: 对抗全过=自欺)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
DUALTRACK_YAML = WORKSPACE / ".omo" / "state" / "collab-dualtrack.yaml"
SCENARIOS_DIR = WORKSPACE / ".omo" / "_delivery" / "collab-scenarios"


def _check_dualtrack() -> list[dict]:
    """Check the authoritative dual-track state for adversarial metrics."""
    findings: list[dict] = []
    if not DUALTRACK_YAML.is_file():
        return findings

    data = yaml.safe_load(DUALTRACK_YAML.read_text(encoding="utf-8")) or {}
    cap = data.get("capability_track") or {}

    adv_total = cap.get("adversarial_total")
    adv_failed = cap.get("adversarial_failed")
    adv_fail_rate = cap.get("adversarial_fail_rate")

    if adv_total is None or adv_failed is None:
        # No adversarial data — cannot assess
        return findings

    if adv_total == 0:
        # No adversarial scenarios at all
        findings.append({
            "kind": "no_adversarial_scenarios",
            "message": "adversarial_total = 0 — no adversarial scenarios exist",
        })
        return findings

    # All pass = adversarial insufficient
    if adv_failed == 0 or (adv_fail_rate is not None and adv_fail_rate == 0.0):
        findings.append({
            "kind": "adversarial_all_pass",
            "adversarial_total": adv_total,
            "adversarial_failed": adv_failed,
            "message": (
                f"All {adv_total} adversarial scenarios pass — "
                "adversarial testing is insufficient (P84: 全过=自欺)"
            ),
        })

    return findings


def _check_scenario_files() -> list[dict]:
    """Count adversarial scenario files for sanity checking."""
    findings: list[dict] = []
    if not SCENARIOS_DIR.is_dir():
        return findings

    adv_files = list(SCENARIOS_DIR.glob("GEN-ADV-*.yaml"))
    hand_adv = list(SCENARIOS_DIR.glob("ADV*.yaml"))
    total_adv = len(adv_files) + len(hand_adv)

    if total_adv == 0:
        findings.append({
            "kind": "no_adversarial_files",
            "message": "No adversarial scenario files found in collab-scenarios/",
        })

    return findings


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    findings: list[dict] = []
    findings.extend(_check_dualtrack())
    findings.extend(_check_scenario_files())

    if args.json:
        print(json.dumps({"ok": len(findings) == 0, "findings": findings}))
    else:
        if findings:
            for f in findings:
                print(f"  WARN: [{f['kind']}] {f['message']}")
            print(f"check-adversarial-effectiveness: WARN ({len(findings)} finding(s))")
        else:
            print("check-adversarial-effectiveness: PASS")

    # Return 0 even on findings — this is a warn-level check,
    # not blocking. The findings surface via --json for the dashboard.
    # Per P84: 对抗全过=自欺 should block, but we return 1 for
    # "adversarial_all_pass" to let gac gate handle severity.
    has_blocker = any(f["kind"] == "adversarial_all_pass" for f in findings)
    return 1 if has_blocker else 0


if __name__ == "__main__":
    raise SystemExit(main())
