#!/usr/bin/env python3
"""Agent Registry — register/query/validate digital organism agents (P1-T6).

Agents are registered as YAML specs in .omo/_truth/registry/agents/.
Each spec follows the DigitalAgent M2 model (mof-m2-extensions/digital_agent.yaml).

Usage:
  python3 bin/ssot/agent-registry.py register --id health-monitor --tier resident --role "系统健康监控"
  python3 bin/ssot/agent-registry.py list
  python3 bin/ssot/agent-registry.py query health-monitor
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


def _load_agent(agent_id: str) -> dict[str, Any] | None:
    import yaml

    path = AGENTS_DIR / f"{agent_id}.yaml"
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def list_agents() -> list[dict[str, Any]]:
    import yaml

    if not AGENTS_DIR.is_dir():
        return []
    agents = []
    for path in sorted(AGENTS_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                agents.append({
                    "id": data.get("agent_id", path.stem),
                    "tier": data.get("tier", "?"),
                    "role": data.get("role", data.get("identity", {}).get("role", "?")),
                    "status": data.get("status", "active"),
                    "version": data.get("version", "1.0.0"),
                })
        except Exception:
            continue
    return agents


def register_agent(agent_id: str, tier: str, role: str, *,
                   description: str = "", capabilities: list[str] | None = None) -> dict[str, Any]:
    """Register a new agent spec."""
    if tier not in VALID_TIERS:
        raise ValueError(f"tier must be one of {VALID_TIERS}")

    AGENTS_DIR.mkdir(parents=True, exist_ok=True)

    spec = {
        "agent_id": agent_id,
        "schema": "digital-agent/v1",
        "tier": tier,
        "status": "active",
        "version": "1.0.0",
        "created_at": datetime.now(UTC).isoformat(),
        "identity": {"role": role, "description": description},
        "capabilities": capabilities or [],
        "performance": {"total_executions": 0, "acceptance_rate": 0.0, "trust_score": 0.5},
        "governance": {"self_modification_level": "S2", "can_auto_implement": "S1_only"},
    }

    path = AGENTS_DIR / f"{agent_id}.yaml"
    import yaml

    path.write_text(yaml.dump(spec, default_flow_style=False, allow_unicode=True, sort_keys=False), encoding="utf-8")

    spec["status"] = "registered"
    return spec


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="list all registered agents")

    q_parser = sub.add_parser("query", help="query specific agent")
    q_parser.add_argument("agent_id")

    reg_parser = sub.add_parser("register", help="register a new agent")
    reg_parser.add_argument("--id", required=True)
    reg_parser.add_argument("--tier", required=True, choices=sorted(VALID_TIERS))
    reg_parser.add_argument("--role", required=True)
    reg_parser.add_argument("--description", default="")
    reg_parser.add_argument("--capabilities", nargs="*", default=[])

    args = parser.parse_args(argv)
    command = args.command or "list"

    if command == "list":
        agents = list_agents()
        if not agents:
            print("No agents registered yet.")
            print("Register with: python3 bin/ssot/agent-registry.py register --id <id> --tier <tier> --role <role>")
            return 0
        print(f"Registered agents ({len(agents)}):")
        for a in agents:
            print(f"  {a['id']:30s} tier={a['tier']:12s} role={a['role']:30s} status={a['status']}")
        return 0

    if command == "query":
        agent = _load_agent(args.agent_id)
        if not agent:
            print(f"Agent '{args.agent_id}' not found.")
            return 1
        print(json.dumps(agent, ensure_ascii=False, indent=2, default=str))
        return 0

    if command == "register":
        result = register_agent(args.id, args.tier, args.role,
                                description=args.description, capabilities=args.capabilities)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
