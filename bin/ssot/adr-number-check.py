#!/usr/bin/env python3
"""Check ADR numbering for duplicates and enforce ADR-0443 decision tiers.

Scans .omo/_knowledge/decisions/ for ADR files and reports:
1. number collisions (exit 1)
2. tier violations (ADR-0443): draft/placeholder content occupying a full
   decision number (exit 1) — RSS/signal-grade drafts belong in
   .omo/_knowledge/signals/, not decisions/.
Exit code 0 = clean.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

ADR_PATTERN = re.compile(r"^(\d{4})-")
# ADR-0443 分级：占位实体的特征——无 Decision 语义、等人审标记。
DRAFT_MARKERS = (
    "pending human review",
    "## decision\n\ntbd",
)


def _looks_like_draft(path: Path) -> str | None:
    """Return the violation reason if a decisions/ file is signal-grade draft."""

    try:
        text = path.read_text(encoding="utf-8", errors="replace").lower()
    except OSError:
        return None
    for marker in DRAFT_MARKERS:
        if marker in text and "## decision" in text:
            decision_section = text.split("## decision", 1)[1].split("##", 1)[0]
            if len(decision_section.strip()) < 80 or "pending" in decision_section or "tbd" in decision_section:
                return f"draft-grade content in decisions/ (marker: {marker!r}) — move to .omo/_knowledge/signals/"
    return None


def check_adr_numbers(decisions_dir: Path) -> int:
    if not decisions_dir.is_dir():
        print(f"adr-number-check: directory not found: {decisions_dir}")
        return 0

    numbers: list[str] = []
    tier_violations: list[tuple[str, str]] = []
    for path in sorted(decisions_dir.glob("*.md")):
        match = ADR_PATTERN.match(path.name)
        if match:
            numbers.append(match.group(1))
            reason = _looks_like_draft(path)
            if reason:
                tier_violations.append((path.name, reason))

    exit_code = 0
    counts = Counter(numbers)
    duplicates = {num: count for num, count in counts.items() if count > 1}
    if duplicates:
        print("adr-number-check: DUPLICATE ADR numbers detected!")
        for num, count in sorted(duplicates.items()):
            files = [p.name for p in decisions_dir.glob(f"{num}-*.md")]
            print(f"  ADR-{num}: {count} files → {files}")
        exit_code = 1

    if tier_violations:
        print("adr-number-check: TIER violations (ADR-0443) — drafts must not occupy decision numbers:")
        for name, reason in tier_violations:
            print(f"  {name}: {reason}")
        exit_code = 1

    max_num = max(numbers) if numbers else "0000"
    if exit_code == 0:
        print(f"adr-number-check: OK ({len(numbers)} ADRs, latest={max_num}, next available={int(max_num) + 1:04d})")
    return exit_code


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    decisions_dir = root / ".omo" / "_knowledge" / "decisions"
    return check_adr_numbers(decisions_dir)


if __name__ == "__main__":
    raise SystemExit(main())
