#!/usr/bin/env python3
"""Sync `.omo/_knowledge/bos-registry.json` from `projects/agora/etc/bos-services.yaml`.

Why:
  smoke/integration tests and omo bos list use the JSON mirror; live truth is
  bos-services.yaml. Drift makes smoke expect 34 resolved while agora filters
  unimplemented routes → false CI signal.

Default: 5 classic domains (memory/governance/analysis/persona/capability),
status ∈ {active, unimplemented} so smoke can classify resolved vs gap.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
BOS_YAML = WORKSPACE / "projects/agora/etc/bos-services.yaml"
REGISTRY = WORKSPACE / ".omo/_knowledge/bos-registry.json"
CLASSIC_DOMAINS = frozenset(
    {"memory", "governance", "analysis", "persona", "capability"}
)
KEEP_STATUS = frozenset({"active", "unimplemented"})

_TRANSPORT_TO_PROTOCOL = {
    "stdio": "stdio",
    "mcp_stdio": "stdio",
    "http": "http",
    "mcp_proxy": "http",
    "internal": "internal",
    "inline": "internal",
}


def _endpoint_for(svc: dict) -> str:
    transport = svc.get("transport", "stdio")
    if transport in ("stdio", "mcp_stdio") and svc.get("command"):
        return " ".join(str(x) for x in svc["command"][:6])
    if transport in ("http", "mcp_proxy") and svc.get("http_url"):
        return str(svc["http_url"])
    if transport == "internal" and svc.get("module_path"):
        fn = svc.get("func_name") or ""
        return f"{svc['module_path']}:{fn}".rstrip(":")
    if transport == "mcp_proxy" and svc.get("mcp_tool"):
        return f"mcp_proxy:{svc['mcp_tool']}"
    if transport == "mcp_proxy" and svc.get("tools"):
        return "mcp_proxy:tools"
    return transport


def build_registry(services: list[dict]) -> list[dict]:
    now = datetime.now(UTC).isoformat()
    out: list[dict] = []
    for svc in services:
        uri = svc.get("uri") or ""
        domain = svc.get("domain") or ""
        status = svc.get("status", "active")
        if domain not in CLASSIC_DOMAINS or status not in KEEP_STATUS:
            continue
        action = svc.get("action") or ""
        package = svc.get("package") or uri.replace("bos://", "").split("/")[1:2]
        if isinstance(package, list):
            package = package[0] if package else "unknown"
        transport = svc.get("transport", "stdio")
        entry = {
            "uri": uri,
            "domain": domain,
            "package": package,
            "action": action,
            "endpoint": _endpoint_for(svc),
            "protocol": _TRANSPORT_TO_PROTOCOL.get(transport, "internal"),
            "transport": transport,
            "status": status,
            "description": svc.get("description") or "",
            "registered_at": now,
            "registered_by": "bin/ssot/sync-bos-registry.py",
        }
        if svc.get("mcp_tool"):
            entry["mcp_tool"] = svc["mcp_tool"]
        if svc.get("tools"):
            entry["tools"] = list(svc["tools"])
        out.append(entry)
    out.sort(key=lambda r: r["uri"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="exit 1 if drift (no write)")
    ap.add_argument("--write", action="store_true", help="write registry if drift")
    args = ap.parse_args()
    if not args.check and not args.write:
        args.write = True

    data = yaml.safe_load(BOS_YAML.read_text(encoding="utf-8")) or {}
    services = data.get("services") or []
    fresh = build_registry(services)
    current = (
        json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else []
    )
    # Compare without registered_at noise
    def _canon(rows: list[dict]) -> list[dict]:
        out = []
        for r in rows:
            c = {k: v for k, v in r.items() if k != "registered_at"}
            out.append(c)
        out.sort(key=lambda x: x.get("uri", ""))
        return out

    drifted = _canon(current) != _canon(fresh)
    print(
        f"bos-registry: live={len(fresh)} file={len(current)} "
        f"drift={'YES' if drifted else 'no'}"
    )
    if args.check and drifted:
        print(
            "FAIL: .omo/_knowledge/bos-registry.json out of sync with bos-services.yaml\n"
            "  fix: uv run --with pyyaml python bin/ssot/sync-bos-registry.py --write"
        )
        return 1
    if args.write and drifted:
        REGISTRY.parent.mkdir(parents=True, exist_ok=True)
        REGISTRY.write_text(
            json.dumps(fresh, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {REGISTRY.relative_to(WORKSPACE)} ({len(fresh)} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
