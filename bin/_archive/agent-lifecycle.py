#!/usr/bin/env python3
"""Agent Lifecycle Manager — spawn/retire/version agents (P4-T7).

Manages the full lifecycle of digital organism agents:
- spawn: register new agent (from Governor proposal or manual)
- retire: mark agent retired (when superseded or no longer needed)
- version: bump version after skill evolution
- status: show lifecycle status of all agents

Usage:
  python3 bin/ssot/agent-lifecycle.py spawn --id advisor --tier resident --role "决策评估"
  python3 bin/ssot/agent-lifecycle.py retire --id old-agent --reason "superseded by v2"
  python3 bin/ssot/agent-lifecycle.py version --id journey-runner --changelog "added retry logic"
  python3 bin/ssot/agent-lifecycle.py status
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = ROOT / ".omo" / "_truth" / "registry" / "agents"
VALID_TIERS = {"resident", "on_demand", "emergent"}
VALID_STATUSES = {"active", "idle", "deprecated", "retired"}


def _load(agent_id: str) -> dict[str, Any] | None:
    import yaml
    path = AGENTS_DIR / f"{agent_id}.yaml"
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _save(agent_id: str, data: dict[str, Any]) -> None:
    import yaml
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    (AGENTS_DIR / f"{agent_id}.yaml").write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def spawn(agent_id: str, tier: str, role: str, **kwargs) -> dict[str, Any]:
    """Spawn a new agent."""
    if tier not in VALID_TIERS:
        return {"error": f"invalid tier: {tier}"}
    existing = _load(agent_id)
    if existing and existing.get("status") == "active":
        return {"error": f"agent {agent_id} already active"}
    spec = {
        "agent_id": agent_id, "schema": "digital-agent/v1", "tier": tier,
        "status": "active", "version": "1.0.0",
        "created_at": datetime.now(UTC).isoformat(),
        "identity": {"role": role, "description": kwargs.get("description", "")},
        "capabilities": kwargs.get("capabilities", []),
        "performance": {"total_executions": 0, "acceptance_rate": 0.0, "trust_score": 0.5},
        "born_from": kwargs.get("born_from", "manual"),
        "lifecycle": {"versions": [{"version": "1.0.0", "ts": datetime.now(UTC).isoformat(), "change": "initial"}]},
    }
    _save(agent_id, spec)
    spec["action"] = "spawned"
    return spec


def retire(agent_id: str, reason: str = "") -> dict[str, Any]:
    """Retire an agent."""
    spec = _load(agent_id)
    if not spec:
        return {"error": f"agent {agent_id} not found"}
    spec["status"] = "retired"
    spec["retired_at"] = datetime.now(UTC).isoformat()
    spec["retire_reason"] = reason
    _save(agent_id, spec)
    return {"action": "retired", "agent_id": agent_id, "reason": reason}


def bump_version(agent_id: str, changelog: str = "") -> dict[str, Any]:
    """Bump agent version after evolution."""
    spec = _load(agent_id)
    if not spec:
        return {"error": f"agent {agent_id} not found"}
    parts = spec.get("version", "1.0.0").split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    new_version = ".".join(parts)
    spec["version"] = new_version
    if "lifecycle" not in spec:
        spec["lifecycle"] = {"versions": []}
    spec["lifecycle"].setdefault("versions", []).append(
        {"version": new_version, "ts": datetime.now(UTC).isoformat(), "change": changelog[:200]}
    )
    _save(agent_id, spec)
    return {"action": "version_bumped", "agent_id": agent_id, "new_version": new_version}


def status() -> list[dict[str, Any]]:
    """Show lifecycle status of all agents."""
    import yaml
    if not AGENTS_DIR.is_dir():
        return []
    result = []
    for path in sorted(AGENTS_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                result.append({
                    "id": data.get("agent_id", path.stem),
                    "status": data.get("status", "?"),
                    "tier": data.get("tier", "?"),
                    "version": data.get("version", "?"),
                    "role": data.get("identity", {}).get("role", "?"),
                    "executions": data.get("performance", {}).get("total_executions", 0),
                })
        except Exception:
            continue
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")

    s = sub.add_parser("spawn")
    s.add_argument("--id", required=True)
    s.add_argument("--tier", required=True, choices=sorted(VALID_TIERS))
    s.add_argument("--role", required=True)
    s.add_argument("--description", default="")
    s.add_argument("--capabilities", nargs="*", default=[])
    s.add_argument("--born-from", default="manual")

    r = sub.add_parser("retire")
    r.add_argument("--id", required=True)
    r.add_argument("--reason", default="")

    v = sub.add_parser("version")
    v.add_argument("--id", required=True)
    v.add_argument("--changelog", default="")

    sub.add_parser("status")

    args = parser.parse_args(argv)

    if args.command == "spawn":
        result = spawn(args.id, args.tier, args.role, description=args.description,
                       capabilities=args.capabilities, born_from=args.born_from)
    elif args.command == "retire":
        result = retire(args.id, args.reason)
    elif args.command == "version":
        result = bump_version(args.id, args.changelog)
    elif args.command == "status":
        agents = status()
        print(f"Agent Lifecycle Status ({len(agents)} agents):")
        for a in agents:
            print(f"  {a['id']:30s} status={a['status']:10s} v{a['version']:8s} exec={a['executions']:5d} {a['role']}")
        return 0
    else:
        parser.print_help()
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str, sort_keys=True))
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
