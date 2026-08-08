#!/usr/bin/env python3
"""
gen-mof-artifacts.py — Generate or verify BOS and Cockpit configurations from MOF registry.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
import yaml

REPO = Path(__file__).resolve().parents[2]
MOF_REGISTRY = REPO / ".omo/_truth/registry/mof-capabilities.yaml"
BOS_SERVICES = REPO / "projects/agora/etc/bos-services.yaml"

def load_mof_tools() -> dict:
    if not MOF_REGISTRY.exists():
        return {}
    with MOF_REGISTRY.open(encoding="utf-8") as f:
        docs = list(yaml.safe_load_all(f))
        for doc in docs:
            if doc and "tools" in doc:
                return doc["tools"]
    return {}

def check_drift() -> list[dict]:
    tools = load_mof_tools()
    findings = []
    
    # Check BOS services
    if BOS_SERVICES.exists():
        with BOS_SERVICES.open(encoding="utf-8") as f:
            bos_data = yaml.safe_load(f) or {}
            services = bos_data.get("services", [])
            
            existing_actions = set()
            for s in services:
                if s.get("domain") == "mof" and s.get("package") == "mof":
                    existing_actions.add(s.get("action"))
                    
            for tool_key, tool_info in tools.items():
                if tool_key.startswith("mof-"):
                    action = tool_key[4:]
                    if action not in existing_actions:
                        findings.append({
                            "check": "bos_service_missing",
                            "tool": tool_key,
                            "expected_uri": f"bos://mof/mof/{action}",
                            "actual": "MISSING"
                        })
    return findings

def sync_artifacts() -> bool:
    tools = load_mof_tools()
    changed = False
    
    if BOS_SERVICES.exists():
        with BOS_SERVICES.open(encoding="utf-8") as f:
            bos_data = yaml.safe_load(f) or {}
            
        services = bos_data.setdefault("services", [])
        existing_actions = set()
        for s in services:
            if s.get("domain") == "mof" and s.get("package") == "mof":
                existing_actions.add(s.get("action"))
                
        for tool_key, tool_info in tools.items():
            if tool_key.startswith("mof-"):
                action = tool_key[4:]
                if action not in existing_actions:
                    new_service = {
                        "domain": "mof",
                        "package": "mof",
                        "action": action,
                        "transport": "stdio",
                        "status": "active",
                        "command": [
                            "sh", "-c",
                            f"PYTHONPATH=projects/cockpit/src python3 -m cockpit.cli mof {action} \"$@\"",
                            "--"
                        ],
                        "description": tool_info.get("description", f"MOF Tool: {tool_key}")
                    }
                    services.append(new_service)
                    changed = True
                
        if changed:
            with BOS_SERVICES.open("w", encoding="utf-8") as f:
                yaml.safe_dump(bos_data, f, allow_unicode=True, sort_keys=False)
                
    return changed

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    
    if args.sync:
        changed = sync_artifacts()
        if args.json:
            print('{"changed": ' + str(changed).lower() + '}')
        else:
            print("Sync complete. Changed:" if changed else "No changes needed.")
        return 0
        
    findings = check_drift()
    if args.json:
        import json
        print(json.dumps({"drifts": len(findings), "findings": findings}))
    else:
        for f in findings:
            print(f"🔴 Drift: {f}")
        print(f"Total drifts: {len(findings)}")
        
    return 1 if findings else 0

if __name__ == "__main__":
    sys.exit(main())
