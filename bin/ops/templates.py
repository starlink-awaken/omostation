#!/usr/bin/env python3
"""Service Template Library for Service Gateway.

Pre-defined templates for common service patterns:
- daemon: Long-running background process
- cron: Scheduled task
- mcp: MCP server
- cli: Command-line interface
- docker: Docker container
- web: Web service
- worker: Background worker
- api: REST API server

Usage:
    python3 bin/ops/templates.py list
    python3 bin/ops/templates.py show <template>
    python3 bin/ops/templates.py apply <template> --name <name>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml required", file=sys.stderr)
    sys.exit(1)

WORKSPACE = Path(__file__).resolve().parents[2]
SERVICES_YAML = WORKSPACE / ".omo" / "_truth" / "registry" / "services.yaml"

# Service templates
TEMPLATES: dict[str, dict[str, Any]] = {
    "daemon": {
        "description": "Long-running background process",
        "scheduler": "launchd",
        "trigger": "interval",
        "interval_sec": 300,
        "program": {"interpreter": "stable-python3", "entrypoint": "bin/examples/<name>.py"},
        "resilience": {"keepalive": "crashed", "throttle_interval": 60},
        "liveness": {"signal": ".omo/_delivery/<name>/", "max_stale_hours": 24},
    },
    "cron": {
        "description": "Scheduled task",
        "scheduler": "cron",
        "trigger": "schedule",
        "schedule": "0 9 * * *",
        "program": {"interpreter": "stable-python3", "entrypoint": "bin/examples/<name>.py"},
        "liveness": {"signal": ".omo/_delivery/<name>/", "max_stale_hours": 24},
    },
    "mcp": {
        "description": "MCP server",
        "scheduler": "manual",
        "trigger": "on_demand",
        "transport": "stdio",
        "program": {"interpreter": "uv", "entrypoint": "projects/agora"},
        "liveness": {"signal": "http", "endpoint": "http://localhost:<port>/health"},
    },
    "cli": {
        "description": "Command-line interface",
        "scheduler": "manual",
        "trigger": "on_demand",
        "program": {"interpreter": "uv", "entrypoint": "projects/cockpit"},
    },
    "docker": {
        "description": "Docker container",
        "scheduler": "docker",
        "trigger": "compose",
        "program": {"interpreter": "docker", "entrypoint": "projects/<name>"},
        "liveness": {"signal": "docker", "label": "<name>"},
    },
    "web": {
        "description": "Web service",
        "scheduler": "launchd",
        "trigger": "keepalive",
        "program": {"interpreter": "uv", "entrypoint": "projects/<name>"},
        "resilience": {"keepalive": "always"},
        "liveness": {"signal": "http", "endpoint": "http://localhost:<port>/health"},
    },
    "worker": {
        "description": "Background worker",
        "scheduler": "launchd",
        "trigger": "interval",
        "interval_sec": 30,
        "program": {"interpreter": "stable-python3", "entrypoint": "bin/examples/<name>.py"},
        "resilience": {"keepalive": "crashed", "throttle_interval": 30},
        "liveness": {"signal": ".omo/_delivery/<name>/", "max_stale_hours": 1},
    },
    "api": {
        "description": "REST API server",
        "scheduler": "launchd",
        "trigger": "keepalive",
        "program": {"interpreter": "uv", "entrypoint": "projects/<name>"},
        "resilience": {"keepalive": "always"},
        "liveness": {"signal": "http", "endpoint": "http://localhost:<port>/api/health"},
    },
}


def list_templates() -> str:
    """List available templates."""
    lines = ["Available service templates:\n"]
    for name, tmpl in TEMPLATES.items():
        lines.append(f"  {name:<12} {tmpl['description']}")
    return "\n".join(lines)


def show_template(name: str) -> str:
    """Show template details."""
    if name not in TEMPLATES:
        return f"ERROR: Template '{name}' not found"

    tmpl = TEMPLATES[name]
    return json.dumps(tmpl, indent=2, ensure_ascii=False)


def apply_template(name: str, service_name: str, port: int | None = None) -> dict[str, Any]:
    """Apply a template to create a new service."""
    if name not in TEMPLATES:
        return {"error": f"Template '{name}' not found"}

    tmpl = TEMPLATES[name].copy()

    # Replace placeholders
    def replace_placeholders(obj: Any) -> Any:
        if isinstance(obj, str):
            obj = obj.replace("<name>", service_name)
            if port:
                obj = obj.replace("<port>", str(port))
            return obj
        elif isinstance(obj, dict):
            return {k: replace_placeholders(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [replace_placeholders(v) for v in obj]
        return obj

    service = replace_placeholders(tmpl)
    service["id"] = service_name
    service["enabled"] = True

    # Load existing services
    if SERVICES_YAML.exists():
        content = SERVICES_YAML.read_text()
        docs = list(yaml.safe_load_all(content))
    else:
        docs = [{"services": []}]

    # Add new service
    for doc in docs:
        if isinstance(doc, dict) and "services" in doc:
            # Check if service already exists
            existing = [s for s in doc["services"] if s.get("id") == service_name]
            if existing:
                return {"error": f"Service '{service_name}' already exists"}
            doc["services"].append(service)
            break

    # Write back
    output = []
    for doc in docs:
        output.append(yaml.dump(doc, default_flow_style=False, allow_unicode=True, sort_keys=False))
    SERVICES_YAML.write_text("---\n".join(output))

    return {"created": True, "service": service}


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Service Template Library")
    parser.add_argument("action", choices=["list", "show", "apply"], help="Action")
    parser.add_argument("template", nargs="?", help="Template name")
    parser.add_argument("--name", help="Service name for apply")
    parser.add_argument("--port", type=int, help="Port number for apply")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    args = parser.parse_args()

    if args.action == "list":
        print(list_templates())

    elif args.action == "show":
        if not args.template:
            print("ERROR: template required", file=sys.stderr)
            return 1
        result = show_template(args.template)
        print(result)

    elif args.action == "apply":
        if not args.template or not args.name:
            print("ERROR: template and --name required", file=sys.stderr)
            return 1
        result = apply_template(args.template, args.name, args.port)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            if result.get("error"):
                print(f"ERROR: {result['error']}", file=sys.stderr)
                return 1
            print(f"Created service '{args.name}' from template '{args.template}'")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
