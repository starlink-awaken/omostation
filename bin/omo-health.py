#!/usr/bin/env python3
import sys
import yaml
import json
from pathlib import Path
import os
from pathlib import Path

WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", str(Path(__file__).resolve().parents[1])))
WORKSPACE = WORKSPACE_ROOT
HEALTH_YAML = WORKSPACE / ".omo/state/system_health.yaml"
DEBT_DIR = WORKSPACE / ".omo/debt/items"
SYSTEM_YAML = WORKSPACE / ".omo/state/system.yaml"

def print_header(title):
    print(f"\n{'='*50}\n{title}\n{'='*50}")

def render_dashboard():
    print_header("👁️  KEEPER DASHBOARD (eCOS v5.0)")
    
    # 1. System Phase & Freeze Status
    try:
        with open(SYSTEM_YAML, "r") as f:
            sys_data = yaml.safe_load(f)
            freeze = sys_data.get("governance", {}).get("code_freeze", False)
            print(f"System State: {'❄️  L0-L3 CODE FREEZE ACTIVE' if freeze else '🔥 DEVELOPMENT ACTIVE'}")
    except Exception:
        print("System State: Unknown")

    # 2. Health Pulse
    print_header("🩺 L1: Runtime Health Matrix")
    try:
        if HEALTH_YAML.exists():
            with open(HEALTH_YAML, "r") as f:
                health = yaml.safe_load(f)
                score = health.get("score", 0)
                status = health.get("status", "unknown")
                print(f"Global Score: {score}/100 [{status.upper()}]")
                print(f"Last Updated: {health.get('last_updated', 'never')}")
        else:
            print("❌ .omo/state/system_health.yaml missing. Is scheduler.py running?")
    except Exception as e:
        print(f"Error reading health: {e}")

    # 3. X2/X3 Debt Status (Active vs Resolved)
    print_header("📊 Debt Ledger (X2 Anti-Entropy)")
    active = 0
    resolved = 0
    try:
        if DEBT_DIR.exists():
            for debt_file in DEBT_DIR.glob("*.yaml"):
                with open(debt_file, "r") as f:
                    debt = yaml.safe_load(f)
                    if debt.get("resolved", False):
                        resolved += 1
                    else:
                        active += 1
        print(f"Active Debts:   {active}")
        print(f"Resolved Debts: {resolved} (Swept by X2 Pan-Entropy GC)")
    except Exception as e:
        print(f"Error reading debt ledger: {e}")

    print("\nUse this dashboard to monitor physical reality rather than theoretical design.\n")

if __name__ == "__main__":
    render_dashboard()
