#!/usr/bin/env python3
"""Capability Router — selects best external AI tool provider (P4-T2).

Reads capability-providers.yaml, matches task requirements,
returns optimal provider based on capability + cost + availability.

Usage: python3 bin/ssot/capability-router.py route --capabilities document_draft email_compose
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PROVIDERS_FILE = ROOT / ".omo" / "_truth" / "registry" / "capability-providers.yaml"
COST_RANK = {"free": 0, "low": 1, "medium": 2, "high": 3}


def load_providers() -> list[dict[str, Any]]:
    import yaml

    if not PROVIDERS_FILE.exists():
        return []
    data = yaml.safe_load(PROVIDERS_FILE.read_text(encoding="utf-8"))
    return data.get("providers", []) if isinstance(data, dict) else []


def route(*, required_capabilities: list[str], max_cost: str = "high") -> dict[str, Any]:
    """Select best provider for required capabilities."""
    providers = load_providers()
    if not providers:
        return {"selected": None, "reason": "no providers registered"}

    max_cost_rank = COST_RANK.get(max_cost, 3)
    candidates = []

    for p in providers:
        # Capability filter: must have ALL required capabilities
        caps = set(p.get("capabilities", []))
        if not all(c in caps for c in required_capabilities):
            continue
        # Cost filter
        cost = p.get("cost", "high")
        if COST_RANK.get(cost, 3) > max_cost_rank:
            continue
        candidates.append(p)

    if not candidates:
        return {"selected": None, "reason": "no provider matches all requirements",
                "required": required_capabilities, "available": [p["id"] for p in providers]}

    # Rank: lowest cost wins (ties broken by more capabilities)
    candidates.sort(key=lambda p: (COST_RANK.get(p.get("cost", "high"), 3), -len(p.get("capabilities", []))))
    best = candidates[0]

    return {
        "selected": best["id"],
        "launch": best.get("launch", ""),
        "cost": best.get("cost", "unknown"),
        "strengths": best.get("strengths", []),
        "governance": best.get("governance", "unknown"),
        "matched_capabilities": [c for c in required_capabilities if c in best.get("capabilities", [])],
        "total_candidates": len(candidates),
        "all_candidates": [c["id"] for c in candidates],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")

    r = sub.add_parser("route", help="route a task to best provider")
    r.add_argument("--capabilities", nargs="+", required=True)
    r.add_argument("--max-cost", default="high", choices=list(COST_RANK.keys()))

    l = sub.add_parser("list", help="list all registered providers")

    args = parser.parse_args(argv)

    if args.command == "list":
        providers = load_providers()
        print(f"Registered providers ({len(providers)}):")
        for p in providers:
            print(f"  {p['id']:15s} cost={p.get('cost','?'):8s} caps={p.get('capabilities',[])}")
        return 0

    if args.command == "route":
        result = route(required_capabilities=args.capabilities, max_cost=args.max_cost)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result.get("selected") else 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
