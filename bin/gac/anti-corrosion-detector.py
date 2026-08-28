#!/usr/bin/env python3
"""Anti-Corrosion Detector — 治理规则陈旧检测.

Detects governance rule staleness and suggests fixes:
- Stale rules in governance-checks.yaml (deprecated/superseded/removed lifecycle)
- Legacy CR IDs that should be cleaned up
- ADRs with stale status (PROPOSED for too long)

Usage:
  python3 bin/gac/anti-corrosion-detector.py [--json]
"""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
GOV_CHECKS_YAML = WORKSPACE / ".omo/_truth/registry/governance-checks.yaml"
DECISIONS_DIR = WORKSPACE / ".omo/_knowledge/decisions"

# Stale lifecycle values in governance-checks.yaml
STALE_LIFECYCLE_VALUES = {"deprecated", "superseded", "removed"}

# ADR status values that indicate staleness
STALE_ADR_STATUSES = {"PROPOSED", "proposed", "DRAFT"}

# Maximum age for PROPOSED ADRs before flagging (days)
MAX_PROPOSED_ADR_AGE_DAYS = 90


def _extract_rules_from_yaml() -> list[dict]:
    """Extract rules from governance-checks.yaml."""
    rules = []
    try:
        text = GOV_CHECKS_YAML.read_text(encoding="utf-8")
        # Simple regex extraction - find rule blocks
        rule_pattern = re.compile(
            r"^\s+-\s+id:\s+(.+?)$.*?"
            r"lifecycle:\s+(\S+)",
            re.MULTILINE | re.DOTALL,
        )
        for match in rule_pattern.finditer(text):
            rule_id = match.group(1).strip()
            lifecycle = match.group(2).strip()
            rules.append({"id": rule_id, "lifecycle": lifecycle})
    except Exception:
        pass
    return rules


def _extract_legacy_cr_ids() -> set[str]:
    """Extract LEGACY_CR_IDS from governance-convergence-lint.py."""
    legacy_ids = set()
    lint_script = WORKSPACE / "bin/gac/governance-convergence-lint.py"
    if not lint_script.exists():
        return legacy_ids
    try:
        text = lint_script.read_text(encoding="utf-8")
        # Find LEGACY_CR_IDS set
        match = re.search(r"LEGACY_CR_IDS\s*=\s*\{([^}]+)\}", text, re.DOTALL)
        if match:
            ids_text = match.group(1)
            for line in ids_text.split("\n"):
                # Strip whitespace, trailing comma, then quotes
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                line = line.rstrip(",").strip().strip('"').strip("'")
                if line:
                    legacy_ids.add(line)
    except Exception:
        pass
    return legacy_ids


def _extract_adr_metadata() -> list[dict]:
    """Extract ADR metadata from decision files."""
    adrs = []
    if not DECISIONS_DIR.exists():
        return adrs
    for adr_file in DECISIONS_DIR.glob("*.md"):
        try:
            text = adr_file.read_text(encoding="utf-8")
            # Extract frontmatter
            fm_match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
            if not fm_match:
                continue
            frontmatter = fm_match.group(1)
            # Extract fields
            status_match = re.search(r"status:\s*(\S+)", frontmatter)
            date_match = re.search(r"date:\s*(\S+)", frontmatter)
            adr_id_match = re.search(r"id:\s*(\S+)", frontmatter)
            title_match = re.search(r"title:\s*(.+)$", frontmatter, re.MULTILINE)
            adrs.append(
                {
                    "file": adr_file.name,
                    "id": adr_id_match.group(1) if adr_id_match else adr_file.stem,
                    "status": status_match.group(1) if status_match else "unknown",
                    "date": date_match.group(1) if date_match else None,
                    "title": title_match.group(1).strip() if title_match else adr_file.stem,
                }
            )
        except Exception:
            continue
    return adrs


def detect_stale_rules() -> list[dict]:
    """Detect stale governance rules.

    Returns list of dicts with id, reason, fix.
    """
    findings = []

    # Check governance-checks.yaml for stale lifecycle
    rules = _extract_rules_from_yaml()
    for rule in rules:
        if rule["lifecycle"].lower() in STALE_LIFECYCLE_VALUES:
            findings.append(
                {
                    "id": rule["id"],
                    "reason": f"Rule has stale lifecycle: {rule['lifecycle']}",
                    "fix": f"Remove or update rule '{rule['id']}' in governance-checks.yaml",
                }
            )

    # Check for legacy CR IDs
    legacy_ids = _extract_legacy_cr_ids()
    for cr_id in sorted(legacy_ids):
        findings.append(
            {
                "id": cr_id,
                "reason": "Legacy CR ID in LEGACY_CR_IDS set — should be registered or removed",
                "fix": f"Register '{cr_id}' in governance-checks.yaml or remove from ADR references",
            }
        )

    # Check ADRs for staleness
    adrs = _extract_adr_metadata()
    now = datetime.now(UTC)
    for adr in adrs:
        if adr["status"] in STALE_ADR_STATUSES:
            # Check age if date is available
            if adr["date"]:
                try:
                    adr_date = datetime.fromisoformat(adr["date"])
                    if adr_date.tzinfo is None:
                        adr_date = adr_date.replace(tzinfo=UTC)
                    age_days = (now - adr_date).days
                    if age_days > MAX_PROPOSED_ADR_AGE_DAYS:
                        findings.append(
                            {
                                "id": adr["id"],
                                "reason": f"ADR has been {adr['status']} for {age_days} days (> {MAX_PROPOSED_ADR_AGE_DAYS})",
                                "fix": f"Accept, supersede, or archive ADR '{adr['id']}' in .omo/_knowledge/decisions/",
                            }
                        )
                except (ValueError, TypeError):
                    pass

    return findings


def suggest_fixes() -> list[dict]:
    """Suggest fixes for detected issues.

    Returns list of dicts with area and fix details.
    """
    fixes = []
    findings = detect_stale_rules()

    # Group by area
    areas: dict[str, list[dict]] = {}
    for finding in findings:
        area = "governance-checks.yaml" if "governance-checks" in finding.get("fix", "") else "ADR"
        if area not in areas:
            areas[area] = []
        areas[area].append(finding)

    # Generate fix suggestions
    for area, items in areas.items():
        if area == "governance-checks.yaml":
            stale_rules = [i for i in items if "stale lifecycle" in i["reason"]]
            legacy_ids = [i for i in items if "Legacy CR ID" in i["reason"]]
            if stale_rules:
                fixes.append(
                    {
                        "area": "governance-checks.yaml",
                        "fix": f"Remove or update {len(stale_rules)} rules with stale lifecycle",
                        "details": [i["id"] for i in stale_rules],
                    }
                )
            if legacy_ids:
                fixes.append(
                    {
                        "area": "governance-checks.yaml",
                        "fix": f"Register or remove {len(legacy_ids)} legacy CR IDs",
                        "details": [i["id"] for i in legacy_ids],
                    }
                )
        elif area == "ADR":
            fixes.append(
                {
                    "area": ".omo/_knowledge/decisions/",
                    "fix": f"Review {len(items)} stale ADRs — accept, supersede, or archive",
                    "details": [i["id"] for i in items],
                }
            )

    return fixes


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Anti-corrosion detector for governance rules")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    findings = detect_stale_rules()
    fixes = suggest_fixes()

    if args.json:
        print(
            json.dumps(
                {
                    "findings": findings,
                    "fixes": fixes,
                    "ok": len(findings) == 0,
                },
                indent=2,
            )
        )
    else:
        if findings:
            print(f"Found {len(findings)} stale items:")
            for f in findings:
                print(f"  - {f['id']}: {f['reason']}")
            print()
            print("Suggested fixes:")
            for fix in fixes:
                print(f"  [{fix['area']}] {fix['fix']}")
                for detail in fix.get("details", []):
                    print(f"    - {detail}")
        else:
            print("No stale governance rules detected.")

    return 0 if len(findings) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
