#!/usr/bin/env python3
"""BET Digest Sync — detect/fix sha256 digest drift in bet-ledger.yaml.

Safety contract (Phase A / anti-#2989/#3010):
- --apply ONLY rewrites digest string literals (content_digest / sha256:...).
- NEVER modifies status / done_at / overall_state / deletes bets / reorders YAML
  via full dump (full yaml.dump is forbidden — it previously corrupted the ledger).
- Before/after apply: bet count stable; no status/done_at field diffs.

Usage:
    python3 bin/ssot/sync-bet-digests.py --check
    python3 bin/ssot/sync-bet-digests.py --apply
    python3 bin/ssot/sync-bet-digests.py --report
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
LEDGER = REPO / "docs/plans/3y-bet-ledger.yaml"

# Digests we are allowed to rewrite in-place (literal string replace).
_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")


def compute_digest(file_path: Path) -> str:
    return "sha256:" + hashlib.sha256(file_path.read_bytes()).hexdigest()


def resolve_ref(ref: str) -> Path | None:
    if ref.startswith("repo://"):
        return REPO / ref[7:]
    if ref.startswith("receipt://"):
        return REPO / ref[10:]
    if ref.startswith("git://"):
        return None
    return None


def scan_ledger(ledger_path: Path = LEDGER) -> list[dict]:
    if not ledger_path.exists():
        print(f"ERROR: Ledger not found: {ledger_path}", file=sys.stderr)
        sys.exit(1)

    data = yaml.safe_load(ledger_path.read_text(encoding="utf-8"))
    mismatches: list[dict] = []

    for bet in data.get("bets", []):
        bet_id = bet.get("id", "?")

        for spec in bet.get("accepted_specifications", []) or []:
            if not isinstance(spec, dict):
                continue
            ref = spec.get("spec_ref", "")
            digest = spec.get("content_digest", "")
            file_path = resolve_ref(ref) if isinstance(ref, str) else None
            if file_path and file_path.exists() and isinstance(digest, str) and digest:
                actual = compute_digest(file_path)
                if digest != actual:
                    mismatches.append(
                        {
                            "bet_id": bet_id,
                            "type": "spec",
                            "ref": ref,
                            "expected": digest,
                            "actual": actual,
                        }
                    )

        ce = bet.get("completion_evidence", {})
        if not isinstance(ce, dict):
            continue
        for axis_name, axis in (ce.get("axes") or {}).items():
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
                file_path = resolve_ref(ref) if isinstance(ref, str) else None
                if file_path and file_path.exists() and isinstance(digest, str) and digest:
                    actual = compute_digest(file_path)
                    if digest != actual:
                        mismatches.append(
                            {
                                "bet_id": bet_id,
                                "type": f"evidence.{axis_name}.{ev_name}",
                                "ref": ref,
                                "expected": digest,
                                "actual": actual,
                            }
                        )

    return mismatches


def _status_snapshot(data: dict) -> dict[str, tuple[str | None, str | None]]:
    out: dict[str, tuple[str | None, str | None]] = {}
    for bet in data.get("bets", []) or []:
        if not isinstance(bet, dict):
            continue
        bet_id = bet.get("id")
        if not isinstance(bet_id, str):
            continue
        out[bet_id] = (bet.get("status"), bet.get("done_at") if isinstance(bet.get("done_at"), str) else str(bet.get("done_at")) if bet.get("done_at") is not None else None)
    return out


def assert_structural_invariants(before_text: str, after_text: str) -> None:
    """Fail closed if apply mutated identity fields or bet cardinality."""
    before = yaml.safe_load(before_text)
    after = yaml.safe_load(after_text)
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise RuntimeError("LEDGER_INTEGRITY: ledger root must remain a mapping")

    b_bets = before.get("bets") or []
    a_bets = after.get("bets") or []
    if len(b_bets) != len(a_bets):
        raise RuntimeError(
            f"LEDGER_INTEGRITY: bet count changed {len(b_bets)} -> {len(a_bets)}"
        )

    snap_b = _status_snapshot(before)
    snap_a = _status_snapshot(after)
    if set(snap_b) != set(snap_a):
        missing = sorted(set(snap_b) - set(snap_a))
        extra = sorted(set(snap_a) - set(snap_b))
        raise RuntimeError(
            f"LEDGER_INTEGRITY: bet id set changed missing={missing[:5]} extra={extra[:5]}"
        )

    flipped = [
        bet_id
        for bet_id, (st_b, done_b) in snap_b.items()
        if snap_a[bet_id] != (st_b, done_b)
    ]
    if flipped:
        raise RuntimeError(
            "LEDGER_INTEGRITY: status/done_at mutated for "
            + ", ".join(flipped[:10])
            + ("..." if len(flipped) > 10 else "")
        )

    # Apply must only touch digest literals — forbid accidental non-digest drift
    # beyond whitespace-normalized digest replacements is enforced by replace set.


def apply_fixes(mismatches: list[dict], ledger_path: Path = LEDGER) -> int:
    """Apply digest fixes via literal string replace only (no yaml.dump)."""
    if not mismatches:
        return 0

    before = ledger_path.read_text(encoding="utf-8")
    text = before
    fixed = 0

    # Replace exact expected digest tokens with actual. Prefer unique expected→actual
    # pairs; if the same expected appears for multiple targets with same actual, once is enough.
    replacements: dict[str, str] = {}
    for m in mismatches:
        expected = m["expected"]
        actual = m["actual"]
        if not _DIGEST_RE.fullmatch(expected) or not _DIGEST_RE.fullmatch(actual):
            raise RuntimeError(f"LEDGER_INTEGRITY: refusing non-digest token {expected!r}")
        if expected == actual:
            continue
        if expected in replacements and replacements[expected] != actual:
            raise RuntimeError(
                f"LEDGER_INTEGRITY: conflicting replacements for {expected}"
            )
        replacements[expected] = actual

    for expected, actual in replacements.items():
        count = text.count(expected)
        if count == 0:
            continue
        text = text.replace(expected, actual)
        fixed += count

    assert_structural_invariants(before, text)
    ledger_path.write_text(text, encoding="utf-8")
    return fixed


def main() -> int:
    parser = argparse.ArgumentParser(description="BET Digest Sync")
    parser.add_argument("--check", action="store_true", help="仅检测")
    parser.add_argument("--apply", action="store_true", help="自动修复 digests（禁改 status）")
    parser.add_argument("--report", action="store_true", help="生成报告")
    parser.add_argument(
        "--ledger",
        type=Path,
        default=None,
        help="Override ledger path (tests)",
    )
    args = parser.parse_args()

    ledger_path = args.ledger if args.ledger is not None else LEDGER
    mismatches = scan_ledger(ledger_path)

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
        try:
            fixed = apply_fixes(mismatches, ledger_path)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        print(f"\nFixed {fixed} digest occurrences (status/done_at immutable)")
        return 0

    if args.check:
        print(f"\nUse --apply to fix {len(mismatches)} mismatches")
        return 1

    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
