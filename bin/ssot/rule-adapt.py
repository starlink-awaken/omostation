#!/usr/bin/env python3
"""Rule Adapt — 治理规则自适应审计 (GOV-02).

审计 governance-checks.yaml 中 enforcement=required 规则的违规历史,
长期无违规的 required 规则 → 建议降级为 warn (减少误伤成本).
守 KISS: 只产出建议, 不自动改 SSOT (降级需人批准).

Usage:
  python3 bin/ssot/rule-adapt.py              # 审计 required 规则
  python3 bin/ssot/rule-adapt.py --json
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from _shared import ROOT, load_yaml, read_jsonl, utc_now

GOVERNANCE_CHECKS = ROOT / ".omo" / "_truth" / "registry" / "governance-checks.yaml"
HISTORY = ROOT / ".omo" / "_knowledge" / "governance-history.jsonl"
OUT_DIR = ROOT / ".omo" / "_knowledge" / "rule-adapt-suggestions"


def _load_required_rules() -> list[dict[str, Any]]:
    data = load_yaml(GOVERNANCE_CHECKS)
    gac = data.get("gac", {})
    if not isinstance(gac, dict):
        return []
    checks = gac.get("rules", [])
    if not isinstance(checks, list):
        return []
    return [c for c in checks if isinstance(c, dict) and c.get("enforcement") == "required"]


def _count_violations(rule_id: str) -> int:
    """Count violations for a rule in governance history (if exists)."""
    entries = read_jsonl(HISTORY)
    if not entries and not HISTORY.exists():
        return -1  # unknown (no history file)
    count = 0
    for entry in entries:
        blob = json.dumps(entry, ensure_ascii=False)
        if rule_id in blob and ("violat" in blob.lower() or "fail" in blob.lower()):
            count += 1
    return count


def audit_rules(root: Path | None = None) -> dict[str, Any]:
    root = root or ROOT
    rules = _load_required_rules()
    suggestions: list[dict[str, Any]] = []

    for r in rules:
        rid = str(r.get("id", r.get("check", "?")))
        violations = _count_violations(rid)
        if violations == 0:
            suggestions.append({
                "rule_id": rid,
                "enforcement": "required",
                "violations": 0,
                "suggestion": "downgrade_to_warn",
                "reason": "required 但违规历史为空 — 误伤成本 > 拦截价值 (Bet-Y1Q2-T6-01)",
                "summary": str(r.get("summary", r.get("description", "")))[:100],
            })
        elif violations < 0:
            suggestions.append({
                "rule_id": rid,
                "enforcement": "required",
                "violations": -1,
                "suggestion": "needs_history",
                "reason": "无违规历史数据, 需先建立审计日志",
            })

    result = {
        "schema": "rule-adapt/v1",
        "generated_at": utc_now(),
        "required_rules": len(rules),
        "downgrade_suggestions": len([s for s in suggestions if s["suggestion"] == "downgrade_to_warn"]),
        "suggestions": suggestions,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    (OUT_DIR / f"suggestion-{ts}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return result


def _apply_suggestions(suggestions: list[dict], root: Path, *, dry_run: bool) -> dict:
    """Apply downgrade suggestions to governance-checks.yaml (T4).

    守安全: 备份→修改→验证. dry_run 只预览不写.
    """
    import shutil

    checks_path = root / ".omo" / "_truth" / "registry" / "governance-checks.yaml"
    if not checks_path.exists():
        return {"status": "error", "reason": "governance-checks.yaml not found"}

    downgrade_ids = {s["rule_id"] for s in suggestions if s["suggestion"] == "downgrade_to_warn"}
    if not downgrade_ids:
        return {"status": "noop", "reason": "no downgrade suggestions to apply"}

    original = checks_path.read_text(encoding="utf-8")
    modified = original
    applied: list[str] = []

    # Per-rule enforcement downgrade (required → advisory)
    for rid in sorted(downgrade_ids):
        # Match patterns like: enforcement: required (within a rule block containing this id)
        # Simple approach: find id line, then find nearest enforcement: required after it
        lines = modified.split("\n")
        for i, line in enumerate(lines):
            if f'id: {rid}' in line or f'id: "{rid}"' in line:
                # Search forward for enforcement: required within next 10 lines
                for j in range(i + 1, min(i + 15, len(lines))):
                    if "enforcement: required" in lines[j]:
                        lines[j] = lines[j].replace("enforcement: required", "enforcement: advisory")
                        applied.append(rid)
                        break
                break
        modified = "\n".join(lines)

    if dry_run:
        return {
            "status": "dry_run",
            "would_downgrade": applied,
            "count": len(applied),
            "note": "use --confirm to actually apply",
        }

    # Backup + apply
    backup = checks_path.with_suffix(".yaml.bak")
    shutil.copy2(checks_path, backup)
    checks_path.write_text(modified, encoding="utf-8")

    return {
        "status": "applied",
        "downgraded": applied,
        "count": len(applied),
        "backup": str(backup.relative_to(root)),
        "note": "run 'python3 bin/ssot/verify.py --mode task' to verify",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--apply", action="store_true", help="apply downgrade suggestions (T4)")
    parser.add_argument("--confirm", action="store_true", help="confirm apply (required with --apply for write)")
    args = parser.parse_args(argv)

    result = audit_rules(args.root)

    if args.apply:
        apply_result = _apply_suggestions(
            result["suggestions"], args.root, dry_run=not args.confirm,
        )
        if args.json:
            print(json.dumps(apply_result, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"Rule Apply ({'CONFIRM' if args.confirm else 'DRY-RUN'}):")
            print(f"  status: {apply_result['status']}")
            if "would_downgrade" in apply_result:
                print(f"  would downgrade: {apply_result.get('would_downgrade', [])}")
            elif "downgraded" in apply_result:
                print(f"  downgraded: {apply_result.get('downgraded', [])}")
                print(f"  backup: {apply_result.get('backup', '')}")
            print(f"  count: {apply_result.get('count', 0)}")
        return 0

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Rule Adapt: {result['required_rules']} required rules, "
              f"{result['downgrade_suggestions']} downgrade suggestions")
        for s in result["suggestions"]:
            marker = "🔻" if s["suggestion"] == "downgrade_to_warn" else "❔"
            print(f"  {marker} {s['rule_id']}: {s['suggestion']} ({s['reason'][:50]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
