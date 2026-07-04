#!/usr/bin/env python3
"""Matrix SSOT consistency linter (ADR-0120 Layer 3).

Validates ~/runtime/matrix.yaml against:
  - protocols/port-registry.yaml (port registration)
  - launchctl list (launchd job existence, local only)
  - Internal type constraints (daemon must have launchd_label or docker_container)

Rules:
  R1 ERROR  daemon must have launchd_label or docker_container
  R2 WARN   port must be registered in port-registry.yaml
  R3 WARN   non-daemon types (scheduled/integrated/mcp/cli) should not have port
  R4 WARN   port owner in port-registry should semantically match service name
  R5 ERROR  launchd_label should exist in launchctl list (local only, CI_SKIP)

Usage:
  python3 bin/matrix-consistency-lint.py [--skip-launchd] [--json]
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
MATRIX_PATH = Path(os.environ.get("RUNTIME_HOME", Path.home() / "runtime")) / "matrix.yaml"
PORT_REGISTRY_PATH = WORKSPACE / "protocols" / "port-registry.yaml"


def _parse_matrix(path: Path) -> list[dict]:
    """Parse matrix.yaml using the same logic as runtime.matrix.load_matrix."""
    services: list[dict] = []
    current: dict = {}
    state_outside = 0
    state_services = 1
    state_groups = 3
    state = state_outside

    if not path.exists():
        return services

    with open(path) as f:
        for line in f:
            s = line.rstrip()
            if s.startswith("  ") and not s.startswith("    ") and ":" in s:
                key = s.split(":")[0].strip()
                if key == "services":
                    state = state_services
                    continue
                elif key in ("migrations", "groups"):
                    state = state_groups
                    continue
                else:
                    continue
            if not s or s.startswith("#"):
                continue
            if state == state_groups:
                continue
            if state == state_services:
                if s.startswith("    - name:"):
                    if current:
                        services.append(current)
                    current = {"name": s.split('"')[1] if '"' in s else s.split(":")[1].strip()}
                    continue
                if s.startswith("    #"):
                    continue
                if current and s.startswith("      "):
                    if ":" in s:
                        key, _, val = s.partition(":")
                        key = key.strip()
                        val_part = val.strip().strip('"')
                        if key:
                            current[key] = val_part if val_part and val_part.lower() != "null" else None
                    continue
                if current and s.startswith("        "):
                    continue
                if s.strip() and not s.startswith("    "):
                    if current:
                        services.append(current)
                        current = {}
                    state = state_outside
    if current:
        services.append(current)
    return services


def _load_port_registry() -> dict:
    if not PORT_REGISTRY_PATH.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(PORT_REGISTRY_PATH.read_text()) or {}
    except Exception:
        return {}


def _get_launchd_labels() -> set[str]:
    try:
        r = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=10)
        labels = set()
        for line in r.stdout.strip().split("\n")[1:]:
            parts = line.split("\t")
            if len(parts) >= 3:
                labels.add(parts[2].strip())
        return labels
    except Exception:
        return set()


def lint(skip_launchd: bool = False) -> tuple[list[str], list[str]]:
    """Run all checks. Returns (errors, warnings)."""
    services = _parse_matrix(MATRIX_PATH)
    port_registry = _load_port_registry()
    registered_ports = set(str(k) for k in (port_registry.get("ports") or {}).keys())

    errors: list[str] = []
    warnings: list[str] = []

    for svc in services:
        name = svc.get("name", "?")
        svc_type = svc.get("type", "unknown")
        port = svc.get("port")
        launchd_label = svc.get("launchd_label")
        docker_container = svc.get("docker_container")
        health_url = svc.get("health_url")

        # R1: daemon must have launchd_label or docker_container
        if svc_type == "daemon" and not launchd_label and not docker_container:
            errors.append(
                f"R1 ERROR: '{name}' is type=daemon but has no launchd_label or docker_container "
                f"(scheduler will mark unmanaged, cannot self-heal)"
            )

        # R2: port must be in port-registry.yaml
        if port:
            if str(port) not in registered_ports:
                warnings.append(
                    f"R2 WARN: '{name}' port {port} not found in port-registry.yaml"
                )

        # R3: non-daemon types should not have port (unless health_url implies HTTP)
        if svc_type in ("scheduled", "integrated", "mcp", "cli") and port:
            if not health_url:
                warnings.append(
                    f"R3 WARN: '{name}' type={svc_type} has port={port} but no health_url "
                    f"(non-daemon services typically don't listen on ports)"
                )

        # R4: port owner semantic match (best-effort)
        if port and str(port) in registered_ports:
            reg_entry = (port_registry.get("ports") or {}).get(str(port), "")
            name_lower = name.lower().replace("-", "").replace("_", "")
            reg_lower = reg_entry.lower().replace("-", "").replace("_", "").split("#")[0].strip()
            # Check if service name appears in registry entry or vice versa
            if name_lower and reg_lower:
                if name_lower not in reg_lower and reg_lower[:10] not in name_lower:
                    # Allow known mappings (agora-gateway -> agora-mcp-http, etc.)
                    if not any(alias in reg_lower for alias in ["agora", "mcp"] if alias in name_lower):
                        warnings.append(
                            f"R4 WARN: '{name}' port {port} registered as '{reg_entry.strip()}' "
                            f"(possible semantic mismatch)"
                        )

    # R5: launchd_label should exist (local only)
    # NOTE: scheduled type services may have a launchd_label for the cron job
    # that isn't currently loaded (e.g., gbrain-index daily 02:00). Only flag
    # daemon/server types as ERROR; scheduled types get WARN.
    if not skip_launchd:
        launchd_labels = _get_launchd_labels()
        if launchd_labels:
            for svc in services:
                name = svc.get("name", "?")
                svc_type = svc.get("type", "unknown")
                label = svc.get("launchd_label")
                if label and label not in launchd_labels:
                    if svc_type in ("daemon", "service", "server"):
                        errors.append(
                            f"R5 ERROR: '{name}' launchd_label '{label}' not found in launchctl list"
                        )
                    else:
                        warnings.append(
                            f"R5 WARN: '{name}' launchd_label '{label}' not found in launchctl list "
                            f"(type={svc_type}, may be scheduled/unloaded)"
                        )

    return errors, warnings


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Matrix SSOT consistency linter")
    parser.add_argument("--skip-launchd", action="store_true", help="Skip R5 launchd checks (CI mode)")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    errors, warnings = lint(skip_launchd=args.skip_launchd)

    if args.json:
        print(json.dumps({"errors": errors, "warnings": warnings, "ok": len(errors) == 0}))
    else:
        for w in warnings:
            print(w)
        for e in errors:
            print(e, file=sys.stderr)
        if errors:
            print(f"\n{len(errors)} ERROR(s), {len(warnings)} WARN(s)", file=sys.stderr)
        elif warnings:
            print(f"\n{len(warnings)} WARN(s), 0 ERRORs")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
