#!/usr/bin/env python3
"""Check ADR numbering for duplicates.

Scans .omo/_knowledge/decisions/ for ADR files and reports any
number collisions. Exit code 0 = clean, 1 = duplicates found.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

ADR_PATTERN = re.compile(r"^(\d{4})-")


def check_adr_numbers(decisions_dir: Path) -> int:
    if not decisions_dir.is_dir():
        print(f"adr-number-check: directory not found: {decisions_dir}")
        return 0

    numbers: list[str] = []
    for path in sorted(decisions_dir.glob("*.md")):
        match = ADR_PATTERN.match(path.name)
        if match:
            numbers.append(match.group(1))

    counts = Counter(numbers)
    duplicates = {num: count for num, count in counts.items() if count > 1}

    if duplicates:
        print("adr-number-check: DUPLICATE ADR numbers detected!")
        for num, count in sorted(duplicates.items()):
            files = [p.name for p in decisions_dir.glob(f"{num}-*.md")]
            print(f"  ADR-{num}: {count} files → {files}")
        return 1

    max_num = max(numbers) if numbers else "0000"
    print(f"adr-number-check: OK ({len(numbers)} ADRs, latest={max_num}, next available={int(max_num)+1:04d})")
    return 0


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    decisions_dir = root / ".omo" / "_knowledge" / "decisions"
    return check_adr_numbers(decisions_dir)


if __name__ == "__main__":
    raise SystemExit(main())
