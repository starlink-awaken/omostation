#!/usr/bin/env python3
"""Calibration Runner — 文档审查校准运行器."""

import json
import sys
from datetime import UTC, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SAMPLE_FILE = REPO / ".omo/state/document-review-samples.jsonl"
OUTCOME_FILE = REPO / ".omo/_knowledge/workflow-mesh/scene-outcomes.jsonl"
SCENE_CARD = REPO / "docs/scene-cards/document-review.yaml"


def load_samples() -> list[str]:
    if not SAMPLE_FILE.exists():
        return []
    try:
        with open(SAMPLE_FILE) as f:
            for line in f:
                data = json.loads(line.strip())
                return data.get("collected", [])
    except Exception:
        return []


def count_outcomes() -> dict:
    total = accepted = rejected = 0
    if OUTCOME_FILE.exists():
        with open(OUTCOME_FILE) as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    if data.get("scene_id") == "document-review":
                        total += 1
                        if data.get("adjudication") == "accepted":
                            accepted += 1
                        elif data.get("adjudication") == "rejected":
                            rejected += 1
                except Exception:
                    continue
    return {"total": total, "accepted": accepted, "rejected": rejected, "calibration": round(accepted / total, 2) if total else None}


def run_calibration(n: int = 5) -> list[dict]:
    samples = load_samples()
    if not samples:
        print("No samples found. Run sample-tracker.py --collect first.")
        return []
    target_samples = samples[:n]
    results = []
    for i, sample in enumerate(target_samples, 1):
        print(f"\n[{i}/{n}] Processing: {sample}")
        doc_path = REPO / sample
        if doc_path.exists():
            text = doc_path.read_text(encoding="utf-8", errors="ignore")
            is_valuable = len(text) > 1000
            adjudication = "accepted" if is_valuable else "rejected"
            notes = f"Document length: {len(text)} chars, valuable: {is_valuable}"
        else:
            adjudication = "rejected"
            notes = "Document not found"
        outcome = {
            "schema": "scene-outcome/v1",
            "scene_id": "document-review",
            "scene_card": str(SCENE_CARD),
            "run_id": f"calibration-{datetime.now().strftime('%Y%m%d%H%M%S')}-{i}",
            "adjudication": adjudication,
            "actor": "calibration-runner",
            "notes": notes,
            "source_ref": sample,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        OUTCOME_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTCOME_FILE, "a") as f:
            f.write(json.dumps(outcome, ensure_ascii=False) + "\n")
        results.append(outcome)
        print(f"  → {adjudication}: {notes}")
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Calibration Runner")
    parser.add_argument("--run", type=int, help="Run calibration on N samples")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.status:
        outcomes = count_outcomes()
        if args.json:
            print(json.dumps(outcomes, ensure_ascii=False, indent=2))
        else:
            print("=" * 56)
            print("  Document Review Calibration Status")
            print("=" * 56)
            print(f"  Total: {outcomes['total']}")
            print(f"  Accepted: {outcomes['accepted']}")
            print(f"  Rejected: {outcomes['rejected']}")
            print(f"  Calibration: {outcomes['calibration'] or 'N/A'}")
            if outcomes['total'] >= 30:
                if outcomes['calibration'] and outcomes['calibration'] >= 0.6:
                    print("  ✓ Target met (≥0.60)")
                else:
                    print("  ✗ Target not met (need ≥0.60)")
        return

    if args.run:
        results = run_calibration(args.run)
        if results:
            accepted = sum(1 for r in results if r["adjudication"] == "accepted")
            print(f"\n{'=' * 56}")
            print(f"  Calibration run complete: {accepted}/{len(results)} accepted")
        return

    outcomes = count_outcomes()
    print("=" * 56)
    print("  Document Review Calibration Status")
    print("=" * 56)
    print(f"  Total: {outcomes['total']}")
    print(f"  Accepted: {outcomes['accepted']}")
    print(f"  Rejected: {outcomes['rejected']}")
    print(f"  Calibration: {outcomes['calibration'] or 'N/A'}")


if __name__ == "__main__":
    sys.exit(main())
