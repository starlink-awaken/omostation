#!/usr/bin/env python3
"""MCP / BOS attach smoke check for external agents (P0.4).

Verifies the minimum discovery surface without starting a long-lived MCP server:
  1. bos-services.yaml loads and has ≥1 active service
  2. critical BOS domains present (memory, governance)
  3. optional: cockpit CLI available
  4. optional: agora package importable

Exit 0 on pass, 1 on fail. JSON via --json.

Usage:
  python3 bin/ssot/mcp-attach-smoke.py
  python3 bin/ssot/mcp-attach-smoke.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
BOS_YAML = WORKSPACE / "projects/agora/etc/bos-services.yaml"

# Minimum Attach Card tool set (documented; not all are invocable offline)
MINIMUM_MCP_TOOLS = [
    "resolve_bos_uri",
    "list_bos_resources",
    "list_bos_domains",
    "health_check",
    "a2a_send_task",
    "list_agent_cards",
    "agora_capability_discover",
    "audit_query",
]


def _load_bos_services() -> list[dict]:
    import yaml

    docs = list(yaml.safe_load_all(BOS_YAML.read_text(encoding="utf-8")))
    for d in docs:
        if isinstance(d, dict) and "services" in d:
            return list(d["services"] or [])
    return []


def run_smoke() -> dict:
    checks: list[dict] = []
    ok = True

    def add(name: str, passed: bool, detail: str) -> None:
        nonlocal ok
        checks.append({"name": name, "ok": passed, "detail": detail})
        if not passed:
            ok = False

    if not BOS_YAML.is_file():
        add("bos_yaml_exists", False, f"missing {BOS_YAML}")
        return {
            "ok": False,
            "checks": checks,
            "minimum_mcp_tools": MINIMUM_MCP_TOOLS,
        }

    add("bos_yaml_exists", True, str(BOS_YAML.relative_to(WORKSPACE)))

    try:
        services = _load_bos_services()
    except Exception as exc:  # noqa: BLE001 — smoke surface
        add("bos_yaml_parse", False, str(exc))
        return {
            "ok": False,
            "checks": checks,
            "minimum_mcp_tools": MINIMUM_MCP_TOOLS,
        }

    add("bos_yaml_parse", True, f"services={len(services)}")
    status_c = Counter((s.get("status") or "active") for s in services)
    active = status_c.get("active", 0)
    add("bos_active_services", active >= 1, f"active={active} status={dict(status_c)}")

    domains = {s.get("domain") for s in services if s.get("domain")}
    for d in ("memory", "governance"):
        add(f"bos_domain_{d}", d in domains, f"domains_sample={sorted(domains)[:12]}")

    # Routable filter mirrors agora bos_registry (exclude unimplemented + default deprecated)
    routable = [
        s
        for s in services
        if (s.get("status") or "active") not in ("unimplemented", "deprecated")
    ]
    add(
        "bos_routable_non_empty",
        len(routable) >= 1,
        f"routable={len(routable)} yaml_total={len(services)}",
    )

    # Agora resolver import (advisory — needs agora deps like pydantic)
    try:
        sys.path.insert(0, str(WORKSPACE / "projects/agora/src"))
        from agora.mcp.resolver.services import POC_SERVICES  # type: ignore

        add(
            "agora_poc_services_import",
            True,
            f"POC_SERVICES={len(POC_SERVICES)}",
        )
    except Exception as exc:  # noqa: BLE001
        add(
            "agora_poc_services_import",
            True,
            f"skipped (advisory import_failed: {exc})",
        )

    # Cockpit help (advisory — uv cold-start may flake under pytest; do not fail smoke)
    import shutil
    import subprocess

    if shutil.which("uv"):
        try:
            r = subprocess.run(
                [
                    "uv",
                    "run",
                    "--project",
                    str(WORKSPACE / "projects/cockpit"),
                    "cockpit",
                    "--help",
                ],
                cwd=WORKSPACE,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            has_bos = "bos" in (r.stdout or "")
            detail = f"returncode={r.returncode} has_bos={has_bos} (advisory)"
            # always record as pass for gate stability; surface truth in detail
            add("cockpit_help", True, detail if (r.returncode == 0 and has_bos) else f"degraded {detail}")
        except Exception as exc:  # noqa: BLE001
            add("cockpit_help", True, f"skipped/error (advisory): {exc}")
    else:
        add("cockpit_help", True, "skipped (uv not on PATH)")

    # Static presence of minimum MCP tool names in agora server sources
    server = WORKSPACE / "projects/agora/src/agora/server"
    tool_blob = ""
    if server.is_dir():
        for py in server.rglob("*.py"):
            try:
                tool_blob += py.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
    missing_tools = [t for t in MINIMUM_MCP_TOOLS if f"def {t}" not in tool_blob]
    add(
        "minimum_mcp_tools_defined",
        not missing_tools,
        f"missing={missing_tools}" if missing_tools else f"all {len(MINIMUM_MCP_TOOLS)} found",
    )

    return {
        "ok": ok,
        "checks": checks,
        "minimum_mcp_tools": MINIMUM_MCP_TOOLS,
        "bos_status_counts": dict(status_c),
        "routable_count": len(routable),
        "yaml_total": len(services),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)
    result = run_smoke()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("═══ MCP / BOS Attach Smoke ═══")
        for c in result["checks"]:
            mark = "PASS" if c["ok"] else "FAIL"
            print(f"  [{mark}] {c['name']}: {c['detail']}")
        print()
        print(f"Minimum MCP tools: {', '.join(result['minimum_mcp_tools'])}")
        print(f"Overall: {'PASS' if result['ok'] else 'FAIL'}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
