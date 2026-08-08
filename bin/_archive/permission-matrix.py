#!/usr/bin/env python3
"""Permission Matrix — 7-layer access control filter (P3-T4).

Evaluates cross-twin data access requests through 7 independent filter layers.
Each layer can permit, degrade (partial), or deny. Final = most restrictive.

Usage: python3 bin/ssot/permission-matrix.py check --requester spouse --resource calendar/work --action read --purpose coordination
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from typing import Any

RELATIONSHIP_BASELINE = {
    "self": {"sensitivity": "full", "action": "full", "delegation": "full"},
    "spouse": {"sensitivity": "family+degraded", "action": "read+write_shared", "delegation": "depth_1"},
    "child": {"sensitivity": "family_readonly", "action": "read_only", "delegation": "none"},
    "colleague": {"sensitivity": "project_scoped", "action": "project_read", "delegation": "none"},
    "stranger": {"sensitivity": "public_only", "action": "none", "delegation": "none"},
}

SENSITIVITY_LEVELS = {"public": 0, "family": 1, "personal": 2, "confidential": 3}
ACCESS_LEVELS = {"full": 3, "degraded": 2, "summary": 1, "blocked": 0}


def check_permission(*, requester: str, resource: str, action: str,
                     purpose: str, context: str = "normal") -> dict[str, Any]:
    """Evaluate access request through 7 layers."""
    layers: list[dict[str, Any]] = []

    # L1: Identity
    identity_ok = requester in RELATIONSHIP_BASELINE or requester == "self"
    layers.append({"layer": "L1_identity", "result": "pass" if identity_ok else "deny",
                   "detail": f"requester={requester}"})
    if not identity_ok:
        return _final_decision(layers, "deny")

    # L2: Relationship
    baseline = RELATIONSHIP_BASELINE.get(requester, RELATIONSHIP_BASELINE["stranger"])
    layers.append({"layer": "L2_relationship", "result": "pass",
                   "detail": f"baseline={baseline}"})

    # L3: Sensitivity
    resource_domain = resource.split("/")[0] if "/" in resource else resource
    sensitivity = "personal"  # default
    if resource_domain in ("calendar", "inbox"):
        sensitivity = "personal"
    elif resource_domain in ("family", "shopping"):
        sensitivity = "family"
    elif resource_domain in ("finance", "health"):
        sensitivity = "confidential"

    rel_sensitivity = baseline["sensitivity"]
    if "confidential" == sensitivity and "full" not in rel_sensitivity:
        layers.append({"layer": "L3_sensitivity", "result": "deny",
                       "detail": f"resource={sensitivity}, access={rel_sensitivity}"})
        return _final_decision(layers, "deny")
    elif "personal" == sensitivity and "degraded" in rel_sensitivity:
        layers.append({"layer": "L3_sensitivity", "result": "degrade",
                       "detail": f"personal → degraded view"})
    else:
        layers.append({"layer": "L3_sensitivity", "result": "pass"})

    # L4: Purpose
    valid_purposes = ["coordination", "emergency", "project_collab", "maintenance"]
    purpose_ok = purpose in valid_purposes
    layers.append({"layer": "L4_purpose", "result": "pass" if purpose_ok else "deny",
                   "detail": f"purpose={purpose}"})
    if not purpose_ok:
        return _final_decision(layers, "deny")

    # L5: Temporal
    if context == "emergency" and requester in ("self", "spouse"):
        layers.append({"layer": "L5_temporal", "result": "escalate",
                       "detail": "emergency context — elevated access"})
    else:
        layers.append({"layer": "L5_temporal", "result": "pass", "detail": f"context={context}"})

    # L6: Action
    rel_action = baseline["action"]
    if action == "write" and "write" not in rel_action:
        layers.append({"layer": "L6_action", "result": "deny",
                       "detail": f"write not allowed for {requester}"})
        return _final_decision(layers, "deny")
    elif action == "read" and "read" not in rel_action:
        layers.append({"layer": "L6_action", "result": "deny",
                       "detail": f"read not allowed for {requester}"})
        return _final_decision(layers, "deny")
    layers.append({"layer": "L6_action", "result": "pass", "detail": f"action={action} allowed"})

    # L7: Delegation
    layers.append({"layer": "L7_delegation", "result": "pass",
                   "detail": f"delegation={baseline['delegation']}"})

    # Final: most restrictive wins
    results = [l["result"] for l in layers]
    if "deny" in results:
        final = "deny"
    elif "degrade" in results or "escalate" in results:
        final = "degraded"
    else:
        final = "permit"

    return _final_decision(layers, final)


def _final_decision(layers: list[dict], final: str) -> dict[str, Any]:
    return {
        "decision": final,
        "layers": layers,
        "assessed_at": datetime.now(UTC).isoformat(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    c = sub.add_parser("check", help="check access permission")
    c.add_argument("--requester", required=True)
    c.add_argument("--resource", required=True)
    c.add_argument("--action", required=True, choices=["read", "write", "delete", "share"])
    c.add_argument("--purpose", required=True)
    c.add_argument("--context", default="normal")

    args = parser.parse_args(argv)
    if args.command != "check":
        parser.print_help()
        return 1

    result = check_permission(requester=args.requester, resource=args.resource,
                              action=args.action, purpose=args.purpose, context=args.context)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["decision"] == "permit" else 1


if __name__ == "__main__":
    raise SystemExit(main())
