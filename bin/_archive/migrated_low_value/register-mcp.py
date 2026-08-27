#!/usr/bin/env python3
"""Register cron-service MCP server in Hermes config.yaml.

Usage:
  python3 bin/gac/register-mcp.py                   # Dry run
  python3 bin/gac/register-mcp.py --apply           # Actually update config.yaml
"""
import os
import sys
import yaml
from pathlib import Path

CONFIG_PATH = Path.home() / ".hermes" / "config.yaml"

# 动态检测路径：从脚本位置推断 workspace 根目录
_SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = _SCRIPT_DIR.parent  # bin/ → workspace root
VENV_PYTHON = os.environ.get("HERMES_PYTHON") or str(
    (Path.home() / ".hermes" / "hermes-agent" / "venv" / "bin" / "python3").resolve()
)
WORKDIR = str(WORKSPACE_ROOT / "projects" / "kairon" / "packages" / "cron-service")

MCP_ENTRY = {
    "cron-service": {
        "command": VENV_PYTHON,
        "args": ["-m", "cron_service.server", "--mcp"],
        "workdir": WORKDIR,
    }
}


def main():
    dry_run = "--apply" not in sys.argv

    if not CONFIG_PATH.exists():
        print(f"❌ Config not found: {CONFIG_PATH}")
        return

    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f) or {}

    mcp_servers = config.get("mcp_servers", {})
    if "cron-service" in mcp_servers:
        print("ℹ️  cron-service already registered in MCP servers")
        return

    if dry_run:
        print("🔄 DRY RUN — would add to config.yaml:")
        print(yaml.dump({"mcp_servers": MCP_ENTRY}, default_flow_style=False))
        print("\nRun with --apply to actually update")
        return

    # Apply
    if "mcp_servers" not in config:
        config["mcp_servers"] = {}
    config["mcp_servers"]["cron-service"] = MCP_ENTRY["cron-service"]

    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    print("✅ cron-service registered as MCP server")
    print("   Run: hermes mcp test cron-service")
    print("   Then: /reset or restart Hermes to enable tools")


if __name__ == "__main__":
    main()
