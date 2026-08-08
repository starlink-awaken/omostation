#!/usr/bin/env python3
"""check-gateway-status-doc: verify LLM gateway unreachable states are documented.

Scans gateway configuration files and checks that unreachable/down
gateways have corresponding documentation.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    # Scan for gateway config files
    candidates = [
        WORKSPACE / "protocols" / "gateway-registry.yaml",
        WORKSPACE / ".omo" / "_truth" / "registry" / "gateway-registry.yaml",
    ]
    state_dir = WORKSPACE / ".omo" / "state"
    if state_dir.exists():
        candidates.extend(sorted(state_dir.glob("*.yaml")))

    gateways = []
    for c in candidates:
        if not c.exists():
            continue
        try:
            data = yaml.safe_load(c.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        # Try multiple formats
        for key in ("gateways", "services"):
            entries = data.get(key, {}) or {}
            if isinstance(entries, list):
                for e in entries:
                    if isinstance(e, dict) and any(k in str(e.get("uri", "")) or k in str(e.get("name", "")) for k in ("gateway", "llm")):
                        gateways.append(e)
            elif isinstance(entries, dict):
                for name, info in entries.items():
                    if isinstance(info, dict) and "gateway" in name.lower():
                        gateways.append(info)
        # Top-level dict with gateway keys
        for k, v in data.items():
            if "gateway" in k.lower() and isinstance(v, dict):
                gateways.append(v)

    if not gateways:
        if args.json:
            print(json.dumps({"ok": True, "gateways_checked": 0, "unreachable": 0, "violations": []}))
        else:
            print("check-gateway-status-doc: PASS (no gateways configured)")
        return 0

    violations = []
    unreachable_count = 0
    for gw in gateways:
        status = gw.get("runtime", {}).get("status") or gw.get("status") or gw.get("health_check", "")
        if status in ("unreachable", "down"):
            unreachable_count += 1
            gw_name = gw.get("name") or gw.get("uri") or "unknown"
            # Check for documentation
            doc_found = False
            for doc_dir in [WORKSPACE / "docs" / "operations", WORKSPACE / "docs" / "gateway", WORKSPACE / ".omo" / "_knowledge"]:
                if doc_dir.exists():
                    for doc_file in doc_dir.rglob("*.md"):
                        content = doc_file.read_text(encoding="utf-8", errors="ignore")
                        if gw_name in content and "unreachable" in content:
                            doc_found = True
                            break
            if not doc_found:
                violations.append({"gateway": gw_name, "status": status})

    ok = len(violations) == 0
    if args.json:
        print(json.dumps({"ok": ok, "gateways_checked": len(gateways), "unreachable": unreachable_count, "violations": violations}, indent=2))
    else:
        print(f"check-gateway-status-doc: {'PASS' if ok else 'FAIL'} ({len(gateways)} gateways, {unreachable_count} unreachable, {len(violations)} undocumented)")
        for v in violations:
            print(f"  VIOLATION: {v['gateway']} is {v['status']} but undocumented")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
