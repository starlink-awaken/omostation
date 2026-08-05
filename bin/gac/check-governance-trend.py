#!/usr/bin/env python3
"""check-governance-trend: check governance metrics are within reasonable ranges.

Reads `.omo/_truth/registry/governance-checks.yaml` and enforces:

  - Active rule count must not exceed freeze.max_rules.
  - ADR coverage must be 100% (no active rule without an `adr` field).
  - Dimension balance: X2 rule count / X4 rule count > 0.4.
  - No draft rules older than 90 days (based on `created_at`).

Output:
  - exit 0 = all metrics within range
  - exit 1 = one or more metrics violated
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
GOVERNANCE_CHECKS = WORKSPACE / ".omo" / "_truth" / "registry" / "governance-checks.yaml"


def _parse_date(date_str: str) -> datetime | None:
    """Parse an ISO-format date string (YYYY-MM-DD) into a datetime."""
    if not date_str or not isinstance(date_str, str):
        return None
    try:
        return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _load_data() -> dict | None:
    """Load governance-checks.yaml, returning the main document (second YAML doc)."""
    if not GOVERNANCE_CHECKS.is_file():
        return None
    docs = list(yaml.safe_load_all(GOVERNANCE_CHECKS.read_text(encoding="utf-8")))
    # The first doc is frontmatter; the second is the main body.
    if len(docs) < 2:
        return docs[-1] if docs else None
    return docs[1]


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    data = _load_data()
    if data is None:
        if args.json:
            print(json.dumps({"ok": False, "reason": "governance-checks.yaml not found or empty"}))
        else:
            print("check-governance-trend: FAIL (governance-checks.yaml missing or empty)")
        return 1

    # Extract rules from gac.rules
    gac = data.get("gac") or {}
    rules: list[dict] = gac.get("rules") or []

    # Extract freeze config
    freeze: dict = gac.get("freeze") or {}
    max_rules: int = int(freeze.get("max_rules", 0)) if freeze.get("active") else 0

    now = datetime.now(timezone.utc)
    draft_max_age = timedelta(days=90)

    # ── Counters ──
    total_rules = len(rules)
    active_rules: list[dict] = []
    no_adr_rules: list[dict] = []
    x2_count = 0
    x4_count = 0
    stale_draft_rules: list[dict] = []

    for rule in rules:
        lifecycle = (rule.get("lifecycle") or "").strip().lower()

        # Active rules
        if lifecycle == "active":
            active_rules.append(rule)
            dim = (rule.get("dimension") or "").strip().upper()
            if dim == "X2":
                x2_count += 1
            elif dim == "X4":
                x4_count += 1

            # ADR coverage
            adr = rule.get("adr")
            if not adr or (isinstance(adr, str) and not adr.strip()):
                no_adr_rules.append(rule)

        # Draft stale check
        if lifecycle == "draft":
            created_at = rule.get("created_at")
            if created_at:
                dt = _parse_date(created_at)
                if dt and (now - dt) > draft_max_age:
                    stale_draft_rules.append(rule)

    # ── Computed metrics ──
    violations: list[dict] = []

    # 1. Active rule count vs freeze
    active_count = len(active_rules)
    freeze_ok = True
    if max_rules > 0 and active_count > max_rules:
        freeze_ok = False
        violations.append({
            "kind": "freeze_exceeded",
            "metric": "active_rule_count",
            "value": active_count,
            "limit": max_rules,
            "message": f"active rule count {active_count} exceeds freeze limit {max_rules}",
        })

    # 2. ADR coverage
    adr_ok = len(no_adr_rules) == 0
    if not adr_ok:
        violations.append({
            "kind": "missing_adr",
            "metric": "adr_coverage",
            "value": len(no_adr_rules),
            "total_active": active_count,
            "message": f"{len(no_adr_rules)} active rule(s) have no ADR reference",
            "rule_ids": [r.get("id", "?") for r in no_adr_rules],
        })

    # 3. Dimension balance: X2/X4 ratio > 0.4
    x2x4_ratio = x2_count / x4_count if x4_count > 0 else 0.0
    balance_ok = x2x4_ratio > 0.4
    if not balance_ok:
        violations.append({
            "kind": "dimension_imbalance",
            "metric": "x2_x4_ratio",
            "value": round(x2x4_ratio, 3),
            "threshold": 0.4,
            "x2_count": x2_count,
            "x4_count": x4_count,
            "message": f"X2/X4 ratio {x2x4_ratio:.3f} is below 0.4 (X2={x2_count}, X4={x4_count})",
        })

    # 4. Stale draft rules (> 90 days)
    stale_ok = len(stale_draft_rules) == 0
    if not stale_ok:
        violations.append({
            "kind": "stale_draft",
            "metric": "stale_draft_count",
            "value": len(stale_draft_rules),
            "message": f"{len(stale_draft_rules)} draft rule(s) older than 90 days",
            "rule_ids": [r.get("id", "?") for r in stale_draft_rules],
        })

    # ── Summary ──
    ok = len(violations) == 0
    summary = {
        "total_rules": total_rules,
        "active_rules": active_count,
        "freeze_max_rules": max_rules,
        "adr_covered_active": active_count - len(no_adr_rules),
        "adr_missing_active": len(no_adr_rules),
        "x2_count": x2_count,
        "x4_count": x4_count,
        "x2_x4_ratio": round(x2x4_ratio, 3),
        "draft_count": len([r for r in rules if (r.get("lifecycle") or "").strip().lower() == "draft"]),
        "stale_draft_count": len(stale_draft_rules),
    }

    report = {"ok": ok, "summary": summary, "violations": violations}

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"check-governance-trend: {'PASS' if ok else 'FAIL'}")
        print(f"  total rules:        {total_rules}")
        print(f"  active rules:       {active_count}  (freeze max: {max_rules})")
        print(f"  ADR coverage:       {active_count - len(no_adr_rules)}/{active_count}  ({len(no_adr_rules)} missing)")
        print(f"  X2 count:           {x2_count}")
        print(f"  X4 count:           {x4_count}")
        print(f"  X2/X4 ratio:        {x2x4_ratio:.3f}  (threshold: > 0.4)")
        print(f"  stale drafts (>90d): {len(stale_draft_rules)}")
        for v in violations:
            print(f"  - {v.get('kind', '?')}: {v.get('message', '')}")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
