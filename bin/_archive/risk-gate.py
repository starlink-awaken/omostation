#!/usr/bin/env python3
"""Risk Gate — C5动作风控门禁 (P3-T3).

Evaluates proposed C5 actions (transactions, submissions, commitments)
against risk policies. Returns permit/2FA/human/block decisions.

Usage: python3 bin/ssot/risk-gate.py assess --action-type transfer --amount 5000 --recipient known
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from typing import Any

DEFAULT_TIERS = [
    {"max": 100, "decision": "permit", "notify": "push"},
    {"max": 1000, "decision": "require_push_confirm"},
    {"max": 10000, "decision": "require_2fa", "cooling_off": "1h"},
    {"max": None, "decision": "require_human", "cooling_off": "24h"},
]
DAILY_LIMIT = 5000
FREQUENCY_LIMIT = {"per_recipient_per_day": 3}


def assess_risk(*, action_type: str, amount: float = 0, recipient: str = "unknown",
                reversible: bool = False, novel: bool = False,
                daily_total: float = 0, frequency_today: int = 0) -> dict[str, Any]:
    """Assess risk for a proposed C5 action."""
    reasons: list[str] = []

    # 1. Amount tier check
    decision = "block"
    for tier in DEFAULT_TIERS:
        if tier["max"] is None or amount <= tier["max"]:
            decision = tier["decision"]
            break

    # 2. Daily limit check
    if daily_total + amount > DAILY_LIMIT:
        decision = "require_human"
        reasons.append(f"Daily limit exceeded: {daily_total + amount} > {DAILY_LIMIT}")

    # 3. Frequency check
    if frequency_today >= FREQUENCY_LIMIT["per_recipient_per_day"]:
        decision = "require_human"
        reasons.append(f"Frequency limit: {frequency_today} transactions to {recipient} today")

    # 4. Novelty escalation
    if novel and decision == "permit":
        decision = "require_push_confirm"
        reasons.append("Novel action — first time, escalated to push confirm")

    # 5. Irreversibility escalation
    if not reversible and decision == "permit":
        decision = "require_push_confirm"
        reasons.append("Irreversible action — escalated to push confirm")

    # 6. Unknown recipient escalation
    if recipient == "unknown" and decision == "permit":
        decision = "require_push_confirm"
        reasons.append("Unknown recipient — escalated to push confirm")

    return {
        "action_type": action_type,
        "amount": amount,
        "recipient": recipient,
        "decision": decision,
        "reasons": reasons or ["passed all checks"],
        "assessed_at": datetime.now(UTC).isoformat(),
        "reversible": reversible,
        "novel": novel,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")

    assess_parser = sub.add_parser("assess", help="assess a proposed action")
    assess_parser.add_argument("--action-type", required=True)
    assess_parser.add_argument("--amount", type=float, default=0)
    assess_parser.add_argument("--recipient", default="unknown", choices=["known", "unknown", "blacklisted"])
    assess_parser.add_argument("--reversible", action="store_true")
    assess_parser.add_argument("--novel", action="store_true")
    assess_parser.add_argument("--daily-total", type=float, default=0)
    assess_parser.add_argument("--frequency-today", type=int, default=0)

    args = parser.parse_args(argv)
    if args.command != "assess":
        parser.print_help()
        return 1

    if args.recipient == "blacklisted":
        result = {"decision": "block", "reasons": ["recipient is blacklisted"],
                  "assessed_at": datetime.now(UTC).isoformat()}
    else:
        result = assess_risk(
            action_type=args.action_type, amount=args.amount, recipient=args.recipient,
            reversible=args.reversible, novel=args.novel,
            daily_total=args.daily_total, frequency_today=args.frequency_today,
        )

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["decision"] in ("permit",) else 1


if __name__ == "__main__":
    raise SystemExit(main())
