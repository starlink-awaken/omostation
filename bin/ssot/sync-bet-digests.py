#!/usr/bin/env python3
"""BET Digest Sync — 自动检测并修复 bet-ledger.yaml 中的 sha256 digest 失配.

遍历所有 BET 的 accepted_specifications 和 completion_evidence，
检测 repo:// 和 receipt:// 引用的文件 digest 是否匹配当前文件内容。

Usage:
    python3 bin/ssot/sync-bet-digests.py --check     # 仅检测，不修改
    python3 bin/ssot/sync-big-digests.py --apply     # 自动修复失配
    python3 bin/ssot/sync-bet-digests.py --report    # 生成报告
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
LEDGER = REPO / "docs/plans/3y-bet-ledger.yaml"


def compute_digest(file_path: Path) -> str:
    """Compute sha256 digest of a file."""
    content = file_path.read_bytes()
    return "sha256:" + hashlib.sha256(content).hexdigest()


def resolve_ref(ref: str) -> Path | None:
    """Resolve a repo:// or receipt:// reference to a file path."""
    if ref.startswith("repo://"):
        return REPO / ref[7:]
    if ref.startswith("receipt://"):
        return REPO / ref[10:]
    if ref.startswith("git://"):
        return None  # git references can't be checked locally
    return None


def scan_ledger() -> list[dict]:
    """Scan ledger for digest mismatches."""
    if not LEDGER.exists():
        print(f"ERROR: Ledger not found: {LEDGER}", file=sys.stderr)
        sys.exit(1)

    content = LEDGER.read_text()
    data = yaml.safe_load(content)

    mismatches = []

    for bet in data.get("bets", []):
        bet_id = bet.get("id", "?")

        # Check accepted_specifications
        for i, spec in enumerate(bet.get("accepted_specifications", [])):
            ref = spec.get("spec_ref", "")
            digest = spec.get("content_digest", "")
            file_path = resolve_ref(ref)
            if file_path and file_path.exists() and digest:
                actual = compute_digest(file_path)
                if digest != actual:
                    mismatches.append({
                        "bet_id": bet_id,
                        "type": "spec",
                        "ref": ref,
                        "expected": digest,
                        "actual": actual,
                    })

        # Check completion_evidence
        ce = bet.get("completion_evidence", {})
        if not isinstance(ce, dict):
            continue
        for axis_name, axis in ce.get("axes", {}).items():
            if not isinstance(axis, dict):
                continue
            evidence = axis.get("evidence", {})
            if not isinstance(evidence, dict):
                continue
            for ev_name, ev_item in evidence.items():
                if not isinstance(ev_item, dict):
                    continue
                ref = ev_item.get("ref", "")
                digest = ev_item.get("sha256", "")
                file_path = resolve_ref(ref)
                if file_path and file_path.exists() and digest:
                    actual = compute_digest(file_path)
                    if digest != actual:
                        mismatches.append({
                            "bet_id": bet_id,
                            "type": f"evidence.{axis_name}.{ev_name}",
                            "ref": ref,
                            "expected": digest,
                            "actual": actual,
                        })

    return mismatches


def apply_fixes(mismatches: list[dict]) -> int:
    """Apply digest fixes to ledger. Returns number of fixes applied."""
    if not mismatches:
        return 0

    content = LEDGER.read_text()
    data = yaml.safe_load(content)
    fixed = 0

    # Build lookup: (bet_id, ref) -> actual_digest
    fix_lookup = {}
    for m in mismatches:
        fix_lookup[(m["bet_id"], m["ref"])] = m["actual"]

    for bet in data.get("bets", []):
        bet_id = bet.get("id", "?")

        for spec in bet.get("accepted_specifications", []):
            ref = spec.get("spec_ref", "")
            key = (bet_id, ref)
            if key in fix_lookup:
                spec["content_digest"] = fix_lookup[key]
                fixed += 1

        ce = bet.get("completion_evidence", {})
        if not isinstance(ce, dict):
            continue
        for axis_name, axis in ce.get("axes", {}).items():
            if not isinstance(axis, dict):
                continue
            evidence = axis.get("evidence", {})
            if not isinstance(evidence, dict):
                continue
            for ev_name, ev_item in evidence.items():
                if not isinstance(ev_item, dict):
                    continue
                ref = ev_item.get("ref", "")
                key = (bet_id, ref)
                if key in fix_lookup:
                    ev_item["sha256"] = fix_lookup[key]
                    fixed += 1

    with open(LEDGER, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return fixed


def main():
    parser = argparse.ArgumentParser(description="BET Digest Sync")
    parser.add_argument("--check", action="store_true", help="仅检测")
    parser.add_argument("--apply", action="store_true", help="自动修复")
    parser.add_argument("--report", action="store_true", help="生成报告")
    args = parser.parse_args()

    mismatches = scan_ledger()

    if args.report:
        print(json.dumps(mismatches, ensure_ascii=False, indent=2))
        return 0

    if not mismatches:
        print("OK — 0 mismatches")
        return 0

    print(f"Found {len(mismatches)} digest mismatches:")
    for m in mismatches[:10]:
        print(f"  [{m['bet_id']}] {m['type']}: {m['ref'][:60]}...")
    if len(mismatches) > 10:
        print(f"  ... and {len(mismatches) - 10} more")

    if args.apply:
        fixed = apply_fixes(mismatches)
        print(f"\nFixed {fixed} digests")
        return 0

    if args.check:
        print(f"\nUse --apply to fix {len(mismatches)} mismatches")
        return 1

    # default: check
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
