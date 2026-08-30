#!/usr/bin/env python3
"""ADR protection check — detect duplicates, verify INDEX, report violations.

CLI tool for governance-as-code gate integration. Checks:
1. Duplicate ADR numbers on disk
2. Title similarity detection
3. INDEX.md consistency with disk
4. Active claim conflicts

Usage:
    python3 bin/gac/adr-protection-check.py
    python3 bin/gac/adr-protection-check.py --json
    python3 bin/gac/adr-protection-check.py --check-title "My New ADR"
    python3 bin/gac/adr-protection-check.py --check-title "My New ADR" --number 440
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

from adr_protection import ADRProtection


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument(
        "--check-title",
        default=None,
        help="Check if a title would be a duplicate before creation",
    )
    parser.add_argument(
        "--number",
        type=int,
        default=None,
        help="Specific ADR number to check (with --check-title)",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show overall ADR protection status",
    )
    args = parser.parse_args()

    prot = ADRProtection(ROOT)

    # Status mode
    if args.status:
        status = prot.get_protection_status()
        if args.json:
            print(json.dumps(status, ensure_ascii=False, indent=2))
        else:
            print("═══ ADR Protection Status ═══")
            print(f"Total ADRs: {status['total_adrs']}")
            print(f"Active claims: {status['active_claims']}")
            print(f"Protection active: {status['protection_active']}")
            print(f"INDEX consistent: {status['index_consistent']}")
            if status["duplicate_numbers"]:
                print(f"⚠️  Duplicate numbers: {status['duplicate_numbers']}")
            if status["index_missing"]:
                print(
                    f"⚠️  Missing from INDEX ({len(status['index_missing'])}): " + ", ".join(status["index_missing"][:5])
                )
            if status["index_stale"]:
                print(f"⚠️  Stale in INDEX ({len(status['index_stale'])}): " + ", ".join(status["index_stale"][:5]))
        return 0

    # Pre-creation check mode
    if args.check_title:
        result = prot.validate_before_creation(args.check_title, number=args.number)
        if args.json:
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        else:
            if result.ok:
                print(f"✓ No duplicates found for: {args.check_title}")
            else:
                print(f"✗ Violations found for: {args.check_title}")
                for v in result.violations:
                    print(f"  VIOLATION: {v}")
            for w in result.warnings:
                print(f"  WARNING: {w}")
            if result.duplicates:
                print(f"  Duplicates: {len(result.duplicates)}")
                for d in result.duplicates:
                    print(f"    ADR-{d.number:04d} ({d.match_type}, sim={d.similarity:.1%}): {d.title}")
            if not result.ok:
                print(
                    "  HINT: adr-protection FAIL → bin/gac/adr-protection-check.py --json 查看重复/相似; 用 bin/adr/next-adr-id.py 原子取号"
                )
                print("  强约束: 同号/相似标题直接 FAIL, INDEX 漂移告警 (CR-ADR-PROTECTION)")
        return 0 if result.ok else 1

    # Default: full protection check
    violations: list[str] = []
    warnings: list[str] = []

    # 1. Check for duplicate numbers on disk
    from collections import Counter

    from adr_protection import list_adr_files

    adrs = list_adr_files(prot.decisions_dir)
    numbers = [n for n, _, _ in adrs]
    dup_numbers = {n: c for n, c in Counter(numbers).items() if c > 1}

    if dup_numbers:
        for num, count in sorted(dup_numbers.items()):
            files = [f.name for n, f, _ in adrs if n == num]
            violations.append(f"Duplicate ADR-{num:04d} ({count} files): {', '.join(files)}")

    # 2. Check INDEX consistency
    missing, stale = prot.check_index_consistency()
    if missing:
        warnings.append(
            f"{len(missing)} ADR(s) missing from INDEX.md: "
            + ", ".join(missing[:10])
            + ("..." if len(missing) > 10 else "")
        )
    if stale:
        warnings.append(
            f"{len(stale)} stale reference(s) in INDEX.md: "
            + ", ".join(stale[:10])
            + ("..." if len(stale) > 10 else "")
        )

    # 3. Check for high-similarity title pairs
    from adr_protection import compute_title_similarity

    similar_pairs: list[tuple[int, int, float]] = []
    for i, (n1, _, t1) in enumerate(adrs):
        for n2, _, t2 in adrs[i + 1 :]:
            if n1 == n2:
                continue  # already caught as duplicate number
            sim = compute_title_similarity(t1, t2)
            if sim >= ADRProtection.SIMILARITY_ERROR:
                similar_pairs.append((n1, n2, sim))

    for n1, n2, sim in similar_pairs:
        warnings.append(f"High title similarity between ADR-{n1:04d} and ADR-{n2:04d} ({sim:.1%})")

    # Output
    ok = len(violations) == 0

    if args.json:
        result = {
            "ok": ok,
            "violations": violations,
            "warnings": warnings,
            "total_adrs": len(adrs),
            "duplicate_numbers": sorted(dup_numbers.keys()),
            "index_missing_count": len(missing),
            "index_stale_count": len(stale),
            "similar_title_pairs": len(similar_pairs),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("═══ ADR Protection Check ═══")
        print(f"Total ADRs: {len(adrs)}")
        if ok:
            print("✓ No duplicate ADR numbers found")
        else:
            print(f"✗ {len(violations)} violation(s) found")
        for v in violations:
            print(f"  VIOLATION: {v}")
        for w in warnings:
            print(f"  WARNING: {w}")
        if not missing and not stale:
            print("✓ INDEX.md is consistent with disk")
        if not ok:
            print(
                "  HINT: adr-protection FAIL → bin/gac/adr-protection-check.py --json 查看重复/相似; 用 bin/adr/next-adr-id.py 原子取号"
            )
            print("  强约束: 同号/相似标题直接 FAIL, INDEX 漂移告警 (CR-ADR-PROTECTION)")
        status = "PASS" if ok else "FAIL"
        print(f"ADR protection check: {status}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
