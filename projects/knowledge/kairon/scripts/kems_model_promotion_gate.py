#!/usr/bin/env python3
"""Build a repeated shadow-evaluation gate without authorizing promotion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kos.kems import PromotionGateInputError, build_model_promotion_gate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="JSON list of redacted model-acceptance reports")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--candidate-model-id", required=True)
    parser.add_argument("--min-runs", type=int, default=2)
    parser.add_argument("--min-observations", type=int, default=1)
    parser.add_argument("--min-relative-improvement", type=float, default=0.0)
    args = parser.parse_args(argv)
    try:
        reports = json.loads(args.input.expanduser().resolve().read_text(encoding="utf-8"))
        gate = build_model_promotion_gate(
            reports,
            candidate_model_id=args.candidate_model_id,
            min_runs=args.min_runs,
            min_observations=args.min_observations,
            min_relative_improvement=args.min_relative_improvement,
        )
        output = args.output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(gate, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, PromotionGateInputError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "succeeded", **gate}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
