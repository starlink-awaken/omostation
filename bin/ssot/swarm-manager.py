#!/usr/bin/env python3
"""Swarm Manager — 多twin临时编组管理 (P4-T1).

Form/active/dissolve swarms for multi-twin collaboration.
Follows .omo/standards/swarm-protocol.md (SP-001).

Usage:
  python3 bin/ssot/swarm-manager.py form --goal "卫健委数据上报" --members xiamingxing colleague_a
  python3 bin/ssot/swarm-manager.py status
  python3 bin/ssot/swarm-manager.py dissolve <swarm_id>
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SWARM_DIR = ROOT / ".omo" / "_knowledge" / "workflow-mesh" / "swarms"


def form_swarm(goal: str, members: list[str], *, deadline: str = "") -> dict[str, Any]:
    """Form a new swarm."""
    ts = datetime.now(UTC).isoformat()
    swarm_id = f"swarm-{hashlib.sha256(f'{goal}:{ts}'.encode()).hexdigest()[:8]}"
    spec = {
        "swarm_id": swarm_id, "schema": "swarm/v1", "status": "forming",
        "goal": goal, "members": members, "coordinator": members[0] if members else "",
        "formed_at": ts, "deadline": deadline,
        "shared_context": {}, "tasks": [], "decisions": [],
    }
    SWARM_DIR.mkdir(parents=True, exist_ok=True)
    import yaml
    (SWARM_DIR / f"{swarm_id}.yaml").write_text(
        yaml.dump(spec, default_flow_style=False, allow_unicode=True, sort_keys=False), encoding="utf-8")
    spec["action"] = "formed"
    return spec


def list_swarms() -> list[dict[str, Any]]:
    """List all swarms."""
    import yaml
    if not SWARM_DIR.is_dir():
        return []
    result = []
    for path in sorted(SWARM_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                result.append({"swarm_id": data.get("swarm_id", path.stem), "status": data.get("status", "?"),
                               "goal": data.get("goal", "?")[:50], "members": data.get("members", [])})
        except Exception:
            continue
    return result


def dissolve_swarm(swarm_id: str, reason: str = "") -> dict[str, Any]:
    """Dissolve a swarm."""
    import yaml
    path = SWARM_DIR / f"{swarm_id}.yaml"
    if not path.exists():
        return {"error": f"swarm {swarm_id} not found"}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["status"] = "dissolved"
    data["dissolved_at"] = datetime.now(UTC).isoformat()
    data["dissolve_reason"] = reason
    path.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return {"action": "dissolved", "swarm_id": swarm_id, "reason": reason}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")

    f = sub.add_parser("form")
    f.add_argument("--goal", required=True)
    f.add_argument("--members", nargs="+", required=True)
    f.add_argument("--deadline", default="")

    sub.add_parser("status")

    d = sub.add_parser("dissolve")
    d.add_argument("swarm_id")
    d.add_argument("--reason", default="")

    args = parser.parse_args(argv)

    if args.command == "form":
        result = form_swarm(args.goal, args.members, deadline=args.deadline)
    elif args.command == "status":
        swarms = list_swarms()
        print(f"Swarms ({len(swarms)}):")
        for s in swarms:
            print(f"  {s['swarm_id']:20s} status={s['status']:10s} members={s['members']} goal={s['goal']}")
        return 0
    elif args.command == "dissolve":
        result = dissolve_swarm(args.swarm_id, args.reason)
    else:
        parser.print_help()
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
