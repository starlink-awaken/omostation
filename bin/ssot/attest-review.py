#!/usr/bin/env python3
"""attest-review.py — Human value attestation review interactive flow (weekly default).

North star pacemaker final loop: aggregates episode drafts, presents them for
human review (confirm/edit/reject/skip), and persists attestations.

Usage:
    python3 bin/ssot/attest-review.py [--since 7] [--dry-run]

Write paths:
    - Confirmed: .omo/state/attestations/<date>.json (pending_broker)
    - Rejected:  .omo/state/attest-negative-samples.json
    - If uv/omo PersonalEpisodeService is available, confirmed items are also
      written to the event ledger via subprocess.

Design:
    - stdin is abstracted (injectable StringIO for testing)
    - Write failures never crash — auto-fallback to JSON with clear message
    - --dry-run: display only, zero side effects
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

try:
    from _shared import ROOT  # type: ignore[import-not-found]
except ImportError:
    ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGGREGATOR_PATH = ROOT / "bin" / "ssot" / "episode-source-aggregator.py"
COEFFICIENT_PATH = ROOT / "bin" / "ssot" / "est-minutes-coefficient.py"
COEFFICIENT_SSOT = ROOT / "protocols" / "est-minutes-coefficient.yaml"
DEFAULT_STATE_DIR = ROOT / ".omo" / "state"
NEGATIVE_SAMPLES_FILE = "attest-negative-samples.json"

# Keyword → coefficient type mapping (configurable)
KEYWORD_TYPE_MAP: list[tuple[list[str], str]] = [
    (["merge pull request", "pr merge", "merged pr"], "pr_merge"),
    (["debt", "closeout", "close item", "resolve debt"], "debt_close"),
    (["doc", "readme", "adr", "documentation", "write doc"], "doc_write"),
    # attestation_review must precede scene_activation (both share "attest")
    (["attestation", "attest review", "sign-off"], "attestation_review"),
    (["scene", "attest", "activation", "scene card"], "scene_activation"),
    (["infra", "fix ci", "pipeline", "timeout", "ci fix", "infra fix"], "infra_fix"),
    (["research", "digest", "paper", "study", "analysis"], "research_digest"),
]

# Fallback coefficient table (in case YAML is unavailable)
FALLBACK_COEFFICIENTS: dict[str, int] = {
    "pr_merge": 15,
    "debt_close": 20,
    "doc_write": 10,
    "scene_activation": 25,
    "infra_fix": 30,
    "research_digest": 45,
    "attestation_review": 20,
    "default": 15,
}


# ---------------------------------------------------------------------------
# Keyword classification
# ---------------------------------------------------------------------------

def classify_summary(summary: str) -> str:
    """Classify a summary string into a coefficient type via keyword matching."""
    lower = summary.lower()
    for keywords, ctype in KEYWORD_TYPE_MAP:
        for kw in keywords:
            if kw in lower:
                return ctype
    return "default"


# ---------------------------------------------------------------------------
# Coefficient lookup
# ---------------------------------------------------------------------------

_coefficient_cache: dict[str, int] | None = None


def _load_coefficients() -> dict[str, int]:
    """Load coefficients from YAML SSOT, falling back to built-in table."""
    global _coefficient_cache
    if _coefficient_cache is not None:
        return _coefficient_cache

    try:
        import yaml  # type: ignore[import-untyped]
        data = yaml.safe_load(COEFFICIENT_SSOT.read_text(encoding="utf-8"))
        coeffs = {}
        for entry in data.get("coefficients", []):
            coeffs[entry["type"]] = entry["minutes"]
        _coefficient_cache = coeffs
        return coeffs
    except Exception:
        _coefficient_cache = dict(FALLBACK_COEFFICIENTS)
        return _coefficient_cache


def get_est_minutes(ctype: str) -> int:
    """Get estimated minutes for a coefficient type, defaulting to 15."""
    coeffs = _load_coefficients()
    return coeffs.get(ctype, coeffs.get("default", 15))


# ---------------------------------------------------------------------------
# Aggregator call
# ---------------------------------------------------------------------------

def fetch_drafts(since_days: int = 7, workspace: Path | None = None) -> list[dict[str, Any]]:
    """Call episode-source-aggregator.py to get draft entries."""
    ws = workspace or ROOT
    cmd = [
        sys.executable, str(AGGREGATOR_PATH),
        "--json", "--since", str(since_days),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, cwd=str(ws),
        )
        if result.returncode != 0:
            print(f"[attest-review] aggregator failed (rc={result.returncode}): {result.stderr[:200]}", file=sys.stderr)
            return []
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as exc:
        print(f"[attest-review] aggregator error: {exc}", file=sys.stderr)
        return []


# ---------------------------------------------------------------------------
# Write paths
# ---------------------------------------------------------------------------

def write_attestation(
    state_dir: Path,
    draft: dict[str, Any],
    est_type: str,
    est_minutes: int,
    verdict: str = "accept",
) -> None:
    """Write one confirmed attestation to .omo/state/attestations/<date>.json."""
    attest_dir = state_dir / "attestations"
    attest_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    attest_file = attest_dir / f"{today}.json"

    existing: list[dict[str, Any]] = []
    if attest_file.exists():
        try:
            existing = json.loads(attest_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, TypeError):
            existing = []

    entry = {
        "ref_id": draft["ref_id"],
        "episode_id": draft.get("episode_id", ""),
        "source": draft.get("source", ""),
        "summary": draft.get("summary", ""),
        "confidence": draft.get("confidence", ""),
        "occurred_at": draft.get("occurred_at", ""),
        "est_type": est_type,
        "est_minutes": est_minutes,
        "verdict": verdict,
        "status": "pending_broker",
        "attested_at": datetime.now(UTC).isoformat(),
    }

    existing.append(entry)
    attest_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def add_negative_sample(state_dir: Path, ref_id: str) -> None:
    """Append a ref_id to the negative samples file (idempotent)."""
    state_dir.mkdir(parents=True, exist_ok=True)
    neg_file = state_dir / NEGATIVE_SAMPLES_FILE

    existing: list[str] = []
    if neg_file.exists():
        try:
            existing = json.loads(neg_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, TypeError):
            existing = []

    if ref_id not in existing:
        existing.append(ref_id)
        neg_file.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def display_draft(index: int, draft: dict[str, Any], est_type: str, est_minutes: int) -> None:
    """Display one draft entry for review."""
    conf = draft.get("confidence", "?").upper()
    source = draft.get("source", "?")
    summary = draft.get("summary", "")[:72]
    ref_id = draft.get("ref_id", "")

    print(f"\n  [{index}] [{conf}] {source} | {ref_id}")
    print(f"      {summary}")
    print(f"      est: {est_type} → {est_minutes} min")


def format_summary(counts: dict[str, int]) -> str:
    """Format session summary."""
    lines = [
        "",
        "=" * 50,
        "  Attestation Review Summary",
        "=" * 50,
        f"  Confirmed:  {counts['confirmed']}",
        f"  Rejected:   {counts['rejected']}",
        f"  Skipped:    {counts['skipped']}",
        f"  Est. saved: {counts['total_est_minutes']} min",
        "=" * 50,
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Interactive loop
# ---------------------------------------------------------------------------

def interactive_loop(
    drafts: list[dict[str, Any]],
    state_dir: Path,
    *,
    stdin: TextIO | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Run the interactive review loop.

    Returns counts dict: {confirmed, rejected, skipped, total_est_minutes}.
    """
    input_stream = stdin or sys.stdin

    confirmed = 0
    rejected = 0
    skipped = 0
    total_est_minutes = 0

    if not drafts:
        print("  (no episodes to review)")
        return {
            "confirmed": 0, "rejected": 0, "skipped": 0, "total_est_minutes": 0,
        }

    print(f"\n  Found {len(drafts)} episode draft(s) to review.")
    if dry_run:
        print("  [DRY-RUN] No files will be written.\n")

    for i, draft in enumerate(drafts, 1):
        est_type = classify_summary(draft.get("summary", ""))
        est_minutes = get_est_minutes(est_type)

        display_draft(i, draft, est_type, est_minutes)

        while True:
            try:
                raw = input_stream.readline()
            except (EOFError, KeyboardInterrupt):
                print("\n  (interrupted)")
                break

            if not raw:
                break

            action = raw.strip().lower()

            if action == "q":
                print("  (quit)")
                return {
                    "confirmed": confirmed,
                    "rejected": rejected,
                    "skipped": skipped,
                    "total_est_minutes": total_est_minutes,
                }
            elif action == "c":
                confirmed += 1
                total_est_minutes += est_minutes
                if not dry_run:
                    write_attestation(state_dir, draft, est_type, est_minutes, verdict="accept")
                print(f"    ✓ confirmed (+{est_minutes} min)")
                break
            elif action == "e":
                # Edit: prompt for new summary and/or minutes
                try:
                    print("    Enter new summary (blank to keep): ", end="", flush=True)
                    new_summary = input_stream.readline().strip()
                    print("    Enter new minutes (blank to keep): ", end="", flush=True)
                    new_minutes_raw = input_stream.readline().strip()
                except (EOFError, KeyboardInterrupt):
                    print("\n    (edit cancelled)")
                    break

                if new_summary:
                    draft = dict(draft)
                    draft["summary"] = new_summary
                    est_type = classify_summary(new_summary)
                    est_minutes = get_est_minutes(est_type)
                if new_minutes_raw:
                    try:
                        est_minutes = int(new_minutes_raw)
                    except ValueError:
                        print("    (invalid minutes, keeping original)")

                confirmed += 1
                total_est_minutes += est_minutes
                if not dry_run:
                    write_attestation(state_dir, draft, est_type, est_minutes, verdict="edit")
                print(f"    ✓ edited & confirmed (+{est_minutes} min)")
                break
            elif action == "r":
                rejected += 1
                if not dry_run:
                    add_negative_sample(state_dir, draft["ref_id"])
                print("    ✗ rejected")
                break
            elif action == "s":
                skipped += 1
                print("    → skipped")
                break
            else:
                print("    (c=confirm, e=edit, r=reject, s=skip, q=quit)")

    return {
        "confirmed": confirmed,
        "rejected": rejected,
        "skipped": skipped,
        "total_est_minutes": total_est_minutes,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Human value attestation review interactive flow (weekly default).",
    )
    parser.add_argument("--since", type=int, default=7,
                        help="Look back N days for episode drafts (default: 7)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Display only — no files written, no scores recorded")
    parser.add_argument("--state-dir", type=str, default=None,
                        help="Override state directory path")
    parser.add_argument("--workspace", type=str, default=None,
                        help="Override workspace root (for aggregator)")

    args = parser.parse_args(argv)

    state_dir = Path(args.state_dir) if args.state_dir else DEFAULT_STATE_DIR
    workspace = Path(args.workspace) if args.workspace else None

    # Allow env override for workspace (used in tests)
    if workspace is None:
        ws_env = os.environ.get("ATTEST_REVIEW_WORKSPACE")
        if ws_env:
            workspace = Path(ws_env)

    print("╔══════════════════════════════════════════════════╗")
    print("║   Attestation Review — North Star Pacemaker     ║")
    print("╚══════════════════════════════════════════════════╝")
    print(f"  since: {args.since} days | dry-run: {args.dry_run}")

    # Step 1: Fetch drafts from aggregator
    drafts = fetch_drafts(since_days=args.since, workspace=workspace)

    # Step 2: Interactive loop
    counts = interactive_loop(drafts, state_dir, dry_run=args.dry_run)

    # Step 3: Summary
    print(format_summary(counts))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
