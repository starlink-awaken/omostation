#!/usr/bin/env python3
"""Read-only Claims Authority status observer.

This command calls only ``authority_status``; it never begins, settles,
activates, resolves, or retries a Claims Authority mutation.  The output is
whitelisted so receipts and dashboards cannot leak authority internals.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "claims-authority-observation/v1"
ALLOWED_FIELDS = {
    "activation_state",
    "authority_epoch",
    "authority_id",
    "code",
    "descriptor_digest",
    "effective_claim_authority",
    "fresh",
    "instruction_capable",
    "last_receipt_digest",
    "observed_at",
    "security_level",
    "sequence",
}


def observe() -> dict[str, Any]:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    omo_src = ROOT / "projects/omo/src"
    if omo_src.is_dir() and str(omo_src) not in sys.path:
        sys.path.insert(0, str(omo_src))
    try:
        from omo.workflow.claims_authority import authority_status
    except ImportError as exc:
        return {
            "schema": SCHEMA,
            "ok": False,
            "verdict": "UNAVAILABLE",
            "available": False,
            "error": f"OMO source unavailable: {type(exc).__name__}",
        }
    try:
        status = authority_status()
    except Exception as exc:  # noqa: BLE001 - observation failure is visible, never green
        return {
            "schema": SCHEMA,
            "ok": False,
            "verdict": "UNAVAILABLE",
            "available": False,
            "error": type(exc).__name__,
        }
    if not isinstance(status, dict):
        return {
            "schema": SCHEMA,
            "ok": False,
            "verdict": "INVALID",
            "available": False,
            "mutation_performed": False,
            "authorization_granted": False,
            "error": "authority status is not an object",
        }
    safe_status = {key: status.get(key) for key in sorted(ALLOWED_FIELDS)}
    # The status is an observation, not an authorization grant.  Keep its
    # verdict distinct from gate PASS so an unactivated authority cannot be
    # mistaken for admission.
    return {
        "schema": SCHEMA,
        "ok": True,
        "verdict": "READ_ONLY",
        "available": True,
        "mutation_performed": False,
        "authorization_granted": False,
        "status": safe_status,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = observe()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        status = report.get("status") if isinstance(report.get("status"), dict) else {}
        print(
            f"claims-authority-status: ok={report['ok']} verdict={report['verdict']} "
            f"state={status.get('activation_state', 'unknown')}"
        )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
