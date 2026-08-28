#!/usr/bin/env python3
"""Environment Configuration Manager for Service Gateway.

Manages environment-specific configurations:
- dev: Development (local, debug enabled, minimal services)
- staging: Testing (pre-production, full services)
- prod: Production (full services, strict SLOs)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml required", file=sys.stderr)
    sys.exit(1)

WORKSPACE = Path(__file__).resolve().parents[2]
ENV_DIR = WORKSPACE / "config" / "ops-environments"

# Environment profiles
ENV_PROFILES: dict[str, dict[str, Any]] = {
    "dev": {
        "description": "Development environment",
        "profile": "minimal",
        "debug": True,
        "log_level": "DEBUG",
        "services": {
            "enabled": [
                "omo.sync_daemon",
                "resident.orchestrator",
                "resident.heartbeat",
                "gac.daemon_watchdog",
                "cockpit.dashboard",
                "mcp.agora",
                "cli.cockpit",
                "cli.omo",
            ],
            "disabled": [
                "cron.capability_ownership",
                "cron.agent_workflow_status",
                "cron.meta_doctor",
                "cron.governance_evolution",
                "cron.m4_health",
                "cron.debt_refresh",
                "cron.drift_sweep",
                "cron.mof_drift",
                "cron.weekly_review",
            ],
        },
        "slos": {
            "availability": 0.95,
            "error_rate": 0.05,
        },
        "cost_tracking": False,
        "auto_recovery": False,
    },
    "staging": {
        "description": "Staging environment (pre-production)",
        "profile": "standard",
        "debug": False,
        "log_level": "INFO",
        "services": {
            "enabled": [
                "omo.sync_daemon",
                "resident.orchestrator",
                "resident.heartbeat",
                "resident.sediment",
                "resident.monitor",
                "gac.daemon_watchdog",
                "cockpit.dashboard",
                "mcp.agora",
                "mcp.kos",
                "mcp.minerva",
                "cli.cockpit",
                "cli.omo",
                "cli.kos",
                "cron.capability_ownership",
                "cron.agent_workflow_status",
                "cron.meta_doctor",
            ],
            "disabled": [
                "cron.m4_health",
                "cron.debt_refresh",
                "cron.drift_sweep",
                "cron.mof_drift",
                "cron.weekly_review",
            ],
        },
        "slos": {
            "availability": 0.98,
            "error_rate": 0.02,
        },
        "cost_tracking": True,
        "auto_recovery": True,
    },
    "prod": {
        "description": "Production environment",
        "profile": "full",
        "debug": False,
        "log_level": "WARNING",
        "services": {
            "enabled": "all",  # All enabled services
            "disabled": [],
        },
        "slos": {
            "availability": 0.99,
            "error_rate": 0.01,
        },
        "cost_tracking": True,
        "auto_recovery": True,
    },
}


def get_current_env() -> str:
    """Get current environment from OPS_ENV env var."""
    return os.environ.get("OPS_ENV", "dev")


def load_profile(env: str) -> dict[str, Any]:
    """Load environment profile."""
    return ENV_PROFILES.get(env, ENV_PROFILES["dev"])


def apply_profile(env: str, dry_run: bool = False) -> dict[str, Any]:
    """Apply environment profile to services.yaml."""
    profile = load_profile(env)
    services_yaml = WORKSPACE / ".omo" / "_truth" / "registry" / "services.yaml"

    if not services_yaml.exists():
        return {"error": f"{services_yaml} not found"}

    content = services_yaml.read_text()
    docs = list(yaml.safe_load_all(content))

    changes = []
    for doc in docs:
        if isinstance(doc, dict) and "services" in doc:
            enabled_list = profile["services"].get("enabled", [])
            disabled_list = profile["services"].get("disabled", [])

            for svc in doc["services"]:
                sid = svc.get("id", "")
                was_enabled = svc.get("enabled", False)

                if enabled_list == "all":
                    svc["enabled"] = True
                elif sid in enabled_list:
                    svc["enabled"] = True
                elif sid in disabled_list:
                    svc["enabled"] = False

                if svc.get("enabled") != was_enabled:
                    changes.append({
                        "id": sid,
                        "from": was_enabled,
                        "to": svc.get("enabled"),
                    })

    if not dry_run and changes:
        # Write back
        output = []
        for doc in docs:
            output.append(yaml.dump(doc, default_flow_style=False, allow_unicode=True, sort_keys=False))
        services_yaml.write_text("---\n".join(output))

    return {
        "environment": env,
        "profile": profile["profile"],
        "changes": changes,
        "dry_run": dry_run,
    }


def generate_env_report(env: str) -> str:
    """Generate environment configuration report."""
    profile = load_profile(env)

    lines = []
    lines.append("=" * 60)
    lines.append(f"Environment Configuration: {env.upper()}")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Description: {profile['description']}")
    lines.append(f"Profile: {profile['profile']}")
    lines.append(f"Debug: {profile['debug']}")
    lines.append(f"Log Level: {profile['log_level']}")
    lines.append(f"Cost Tracking: {profile['cost_tracking']}")
    lines.append(f"Auto Recovery: {profile['auto_recovery']}")
    lines.append("")

    # SLOs
    slos = profile.get("slos", {})
    lines.append("SLOs:")
    lines.append(f"  Availability: {slos.get('availability', 'N/A')}")
    lines.append(f"  Error Rate: {slos.get('error_rate', 'N/A')}")
    lines.append("")

    # Services
    services = profile.get("services", {})
    enabled = services.get("enabled", [])
    disabled = services.get("disabled", [])

    if enabled == "all":
        lines.append("Services: ALL enabled")
    else:
        lines.append(f"Services Enabled ({len(enabled)}):")
        for sid in sorted(enabled):
            lines.append(f"  ✅ {sid}")
        if disabled:
            lines.append(f"Services Disabled ({len(disabled)}):")
            for sid in sorted(disabled):
                lines.append(f"  ❌ {sid}")

    return "\n".join(lines)


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Environment Configuration Manager")
    parser.add_argument("action", choices=["show", "apply", "list"], help="Action")
    parser.add_argument("--env", choices=["dev", "staging", "prod"], default=None,
                        help="Environment (default: OPS_ENV or dev)")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without applying")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    args = parser.parse_args()

    env = args.env or get_current_env()

    if args.action == "list":
        if args.json:
            print(json.dumps(ENV_PROFILES, indent=2, ensure_ascii=False))
        else:
            for name, profile in ENV_PROFILES.items():
                print(f"  {name}: {profile['description']}")
        return 0

    if args.action == "show":
        if args.json:
            print(json.dumps(load_profile(env), indent=2, ensure_ascii=False))
        else:
            print(generate_env_report(env))
        return 0

    if args.action == "apply":
        result = apply_profile(env, dry_run=args.dry_run)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            if result.get("error"):
                print(f"ERROR: {result['error']}", file=sys.stderr)
                return 1
            print(f"Environment: {result['environment']}")
            print(f"Profile: {result['profile']}")
            print(f"Changes: {len(result['changes'])}")
            for change in result["changes"]:
                icon = "✅" if change["to"] else "❌"
                print(f"  {icon} {change['id']}: {change['from']} → {change['to']}")
            if result["dry_run"]:
                print("\n(Dry run - no changes applied)")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
