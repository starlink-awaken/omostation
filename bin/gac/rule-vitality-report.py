#!/usr/bin/env python3
"""rule-vitality-report.py — 规则活力报告 + 动态降级建议 (BET-Y1Q2-T6-01).

用法:
  python3 bin/gac/rule-vitality-report.py --zero-violations --window 30
  python3 bin/gac/rule-vitality-report.py --suggest-downgrade --window 60
  python3 bin/gac/rule-vitality-report.py --json
  python3 bin/gac/rule-vitality-report.py --apply-downgrade --file proposals.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKSPACE / "bin" / "gac"))

import importlib.util

_tracker_path = WORKSPACE / "bin" / "gac" / "rule-vitality-tracker.py"
_spec = importlib.util.spec_from_file_location("rule_vitality_tracker", str(_tracker_path))
_tracker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_tracker)

record_vitality = _tracker.record_vitality
read_vitality = _tracker.read_vitality
query_vitality = _tracker.query_vitality
compute_all_summaries = _tracker.compute_all_summaries

REGISTRY = WORKSPACE / ".omo" / "_truth" / "registry" / "governance-checks.yaml"
MAPPING_PATH = WORKSPACE / ".omo" / "_truth" / "registry" / "rule-gate-mapping.yaml"
DOWNGRADE_LOG = WORKSPACE / ".omo" / "state" / "rule-downgrade-history.jsonl"

PROTECTED_EXECUTORS = {"hook_pre_edit"}
MIN_OBSERVATION_DAYS = 30
MIN_EVALUATIONS = 20
MAX_DOWNGRADES_PER_WEEK = 3


def _load_rules() -> list[dict[str, Any]]:
    import yaml

    docs = [d for d in yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")) if d]
    if not docs:
        return []
    return docs[-1].get("gac", {}).get("rules", [])


def _load_mapping() -> dict[str, Any]:
    import yaml

    if not MAPPING_PATH.exists():
        return {}
    return yaml.safe_load(MAPPING_PATH.read_text(encoding="utf-8")) or {}


def _is_protected(rule: dict[str, Any]) -> bool:
    executors = rule.get("executor", [])
    if isinstance(executors, str):
        executors = [executors]
    return bool(set(executors) & PROTECTED_EXECUTORS)


def _count_recent_downgrades(days: int = 7) -> int:
    if not DOWNGRADE_LOG.exists():
        return 0
    cutoff = time.time() - (days * 86400)
    count = 0
    with DOWNGRADE_LOG.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                ts = entry.get("timestamp", "")
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if dt.timestamp() >= cutoff:
                    count += 1
            except (ValueError, OSError):
                count += 1
    return count


def _zero_violations_report(
    window_days: int,
) -> list[dict[str, Any]]:
    entries = read_vitality()
    if not entries:
        return []

    rule_ids = sorted({e.get("rule_id", "") for e in entries if e.get("rule_id")})
    cutoff = time.time() - (window_days * 86400)
    results = []

    for rid in rule_ids:
        relevant = []
        for e in entries:
            if e.get("rule_id") != rid:
                continue
            ts = e.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if dt.timestamp() >= cutoff:
                    relevant.append(e)
            except (ValueError, OSError):
                relevant.append(e)

        if not relevant:
            continue
        violations = [e for e in relevant if e.get("violated")]
        if violations:
            continue

        results.append({
            "rule_id": rid,
            "evaluations": len(relevant),
            "window_days": window_days,
            "last_eval": relevant[-1].get("timestamp", ""),
            "enforcement": relevant[-1].get("enforcement", ""),
        })

    return results


def _suggest_downgrade(window_days: int) -> list[dict[str, Any]]:
    rules = _load_rules()
    rule_map = {r["id"]: r for r in rules}
    entries = read_vitality()
    if not entries:
        return []

    rule_ids = sorted({e.get("rule_id", "") for e in entries if e.get("rule_id")})
    cutoff = time.time() - (window_days * 86400)
    suggestions = []

    recent_downgrades = _count_recent_downgrades(7)

    for rid in rule_ids:
        rule = rule_map.get(rid, {})
        if not rule:
            continue

        if _is_protected(rule):
            continue

        enforcement = rule.get("enforcement", "required")
        if enforcement == "error":
            continue

        lifecycle = rule.get("lifecycle", "active")
        if lifecycle != "active":
            continue

        relevant = []
        for e in entries:
            if e.get("rule_id") != rid:
                continue
            ts = e.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if dt.timestamp() >= cutoff:
                    relevant.append(e)
            except (ValueError, OSError):
                relevant.append(e)

        if len(relevant) < MIN_EVALUATIONS:
            continue

        first_ts = relevant[0].get("timestamp", "")
        try:
            first_dt = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
            span_days = (datetime.now(UTC) - first_dt).days
        except (ValueError, OSError):
            span_days = 0

        if span_days < MIN_OBSERVATION_DAYS:
            continue

        violations = [e for e in relevant if e.get("violated")]
        if violations:
            continue

        if enforcement == "required":
            new_enforcement = "advisory"
        else:
            new_enforcement = "inactive"

        suggestions.append({
            "rule_id": rid,
            "current_enforcement": enforcement,
            "suggested_enforcement": new_enforcement,
            "evaluations": len(relevant),
            "span_days": span_days,
            "violations": len(violations),
            "gate_checks": sorted({e.get("gate_check", "") for e in relevant}),
        })

    suggestions.sort(key=lambda s: s["evaluations"], reverse=True)
    return suggestions


def _apply_downgrade(proposals_path: Path) -> list[dict[str, Any]]:
    import yaml

    if not proposals_path.exists():
        print(f"Error: proposals file not found: {proposals_path}", file=sys.stderr)
        return []

    proposals = yaml.safe_load(proposals_path.read_text(encoding="utf-8")) or {}
    items = proposals.get("downgrades", [])
    if not items:
        print("No downgrades to apply.")
        return []

    recent = _count_recent_downgrades(7)
    if recent >= MAX_DOWNGRADES_PER_WEEK:
        print(
            f"Rate limit: {recent}/{MAX_DOWNGRADES_PER_WEEK} downgrades this week. "
            f"Refusing to apply more.",
            file=sys.stderr,
        )
        return []

    docs = list(yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")))
    data_doc = None
    for doc in docs:
        if doc and "gac" in doc:
            data_doc = doc
            break

    if data_doc is None:
        print("Error: cannot find gac rules document", file=sys.stderr)
        return []

    rules = data_doc.get("gac", {}).get("rules", [])
    rule_map = {r["id"]: r for r in rules}
    applied = []

    for item in items:
        rid = item.get("rule_id", "")
        new_enc = item.get("suggested_enforcement", "")
        rule = rule_map.get(rid)
        if not rule:
            print(f"  SKIP: {rid} not found in registry", file=sys.stderr)
            continue

        if _is_protected(rule):
            print(f"  SKIP: {rid} has protected executor", file=sys.stderr)
            continue

        if rule.get("enforcement") == "error":
            print(f"  SKIP: {rid} is error enforcement", file=sys.stderr)
            continue

        old_enc = rule.get("enforcement", "")
        rule["enforcement"] = new_enc
        rule["lifecycle"] = "downgraded"
        if "downgraded_from" not in rule:
            rule["downgraded_from"] = old_enc
        rule["downgraded_at"] = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        applied.append({
            "rule_id": rid,
            "old_enforcement": old_enc,
            "new_enforcement": new_enc,
        })

    if applied:
        import yaml as _yaml

        output = _yaml.safe_dump_all(docs, allow_unicode=True, sort_keys=False, default_flow_style=False)
        REGISTRY.write_text(output, encoding="utf-8")

        DOWNGRADE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with DOWNGRADE_LOG.open("a", encoding="utf-8") as f:
            for a in applied:
                f.write(json.dumps({
                    **a,
                    "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                }, sort_keys=True) + "\n")

    return applied


def main() -> int:
    parser = argparse.ArgumentParser(description="Rule vitality report + downgrade engine")
    parser.add_argument("--zero-violations", action="store_true", help="Show rules with zero violations")
    parser.add_argument("--suggest-downgrade", action="store_true", help="Suggest rules for downgrade")
    parser.add_argument("--apply-downgrade", action="store_true", help="Apply downgrade proposals")
    parser.add_argument("--file", type=str, default="", help="Proposals YAML file (for --apply-downgrade)")
    parser.add_argument("--window", type=int, default=30, help="Observation window in days")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    args = parser.parse_args()

    if args.apply_downgrade:
        if not args.file:
            print("Error: --apply-downgrade requires --file", file=sys.stderr)
            return 1
        applied = _apply_downgrade(Path(args.file))
        if args.json:
            print(json.dumps({"applied": len(applied), "details": applied}, indent=2))
        else:
            for a in applied:
                print(f"  {a['rule_id']}: {a['old_enforcement']} → {a['new_enforcement']}")
            print(f"\nApplied {len(applied)} downgrade(s).")
        return 0

    if args.zero_violations:
        results = _zero_violations_report(args.window)
        if args.json:
            print(json.dumps({"zero_violation_rules": len(results), "rules": results}, indent=2))
        else:
            print(f"=== Zero-Violation Rules (window={args.window}d) ===")
            print(f"Found {len(results)} rules with zero violations:\n")
            for r in results:
                print(f"  {r['rule_id']}: {r['evaluations']} evals, enforcement={r['enforcement']}")
        return 0

    if args.suggest_downgrade:
        suggestions = _suggest_downgrade(args.window)
        if args.json:
            print(json.dumps({"suggestions": len(suggestions), "downgrades": suggestions}, indent=2))
        else:
            recent = _count_recent_downgrades(7)
            print(f"=== Downgrade Suggestions (window={args.window}d, recent={recent}/{MAX_DOWNGRADES_PER_WEEK}) ===")
            if not suggestions:
                print("No rules qualify for downgrade.")
            else:
                for s in suggestions:
                    print(
                        f"  {s['rule_id']}: {s['current_enforcement']} → {s['suggested_enforcement']} "
                        f"({s['evaluations']} evals, {s['span_days']}d span, 0 violations)"
                    )
                print(f"\n{suggestions} rule(s) suggested for downgrade.")
                print("To apply: export proposals, review, then --apply-downgrade --file proposals.yaml")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
