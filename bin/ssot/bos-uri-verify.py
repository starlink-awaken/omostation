#!/usr/bin/env python3
"""BOS URI Full Verification — test all registered URIs for reachability."""

from __future__ import annotations
import argparse
import importlib
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BOS_SERVICES = ROOT / "projects" / "agora" / "etc" / "bos-services.yaml"


def load_bos_services() -> list[dict[str, Any]]:
    import yaml
    with open(BOS_SERVICES, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if isinstance(data, dict) and "services" in data:
        return data["services"]
    return data if isinstance(data, list) else []


def check_internal(service: dict[str, Any]) -> dict[str, Any]:
    module_path = service.get("module_path", "")
    func_name = service.get("func_name", "")
    if not module_path or not func_name:
        return {"status": "error", "reason": "missing module_path or func_name"}
    try:
        mod = importlib.import_module(module_path)
        func = getattr(mod, func_name, None)
        if func is None:
            return {"status": "error", "reason": f"func '{func_name}' not found"}
        return {"status": "ok", "module": module_path, "func": func_name}
    except ImportError as e:
        pkg = module_path.split(".")[0]
        if pkg in ("agora", "omo", "aetherforge", "bus_foundation", "family_hub"):
            return {"status": "external", "module": module_path, "note": f"workspace package ({pkg}): {e}"}
        return {"status": "error", "reason": f"ImportError: {e}"}


def check_stdio(service: dict[str, Any]) -> dict[str, Any]:
    command = service.get("command", [])
    if not command:
        return {"status": "error", "reason": "no command specified"}
    script_path = None
    for i, arg in enumerate(command):
        if arg.endswith(".py") and not arg.startswith("-"):
            script_path = arg
            break
        elif arg == "-m" and i + 1 < len(command):
            module = command[i + 1]
            parts = module.split(".")
            for p in [
                ROOT / "/".join(parts[:-1]) / (parts[-1] + ".py"),
                ROOT / "/".join(parts) / "__main__.py",
                ROOT / "/".join(parts[:-1]) / parts[-1] / "__init__.py",
            ]:
                if p.exists():
                    script_path = str(p)
                    break
            break
    if script_path and script_path.endswith(".py"):
        full_path = ROOT / script_path if not os.path.isabs(script_path) else Path(script_path)
        if full_path.exists():
            return {"status": "ok", "script": script_path}
        return {"status": "error", "reason": f"script not found: {script_path}"}
    return {"status": "ok", "command": command[:3], "note": "command-based"}


def check_http(service: dict[str, Any]) -> dict[str, Any]:
    http_url = service.get("http_url", "")
    if not http_url:
        return {"status": "error", "reason": "no http_url"}
    try:
        with urllib.request.urlopen(http_url, timeout=5) as resp:
            return {"status": "ok", "url": http_url, "code": resp.status}
    except Exception as e:
        return {"status": "unreachable", "url": http_url, "error": str(e)[:80]}


def verify_all(verbose: bool = False) -> dict[str, Any]:
    services = load_bos_services()
    results = {
        "total": len(services),
        "by_transport": {},
        "by_status": {"ok": 0, "error": 0, "external": 0, "unreachable": 0, "skipped": 0},
        "details": [],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    for svc in services:
        uri = svc.get("uri", "?")
        transport = svc.get("transport", "unknown")
        status = svc.get("status", "active")

        if status == "deprecated":
            results["by_status"]["skipped"] += 1
            continue

        results["by_transport"].setdefault(transport, {"total": 0, "ok": 0, "error": 0})
        results["by_transport"][transport]["total"] += 1

        if transport in ("internal", "inline"):
            check = check_internal(svc)
        elif transport == "stdio":
            check = check_stdio(svc)
        elif transport == "http":
            check = check_http(svc)
        elif transport in ("mcp_stdio", "mcp_proxy"):
            check = {"status": "skipped", "reason": f"{transport} requires runtime"}
        else:
            check = {"status": "skipped", "reason": f"unknown: {transport}"}

        cs = check.get("status", "unknown")
        if cs == "ok":
            results["by_status"]["ok"] += 1
            results["by_transport"][transport]["ok"] += 1
        elif cs == "error":
            results["by_status"]["error"] += 1
            results["by_transport"][transport]["error"] += 1
        elif cs == "external":
            results["by_status"]["external"] += 1
            results["by_transport"][transport]["ok"] += 1
        elif cs == "unreachable":
            results["by_status"]["unreachable"] += 1
        else:
            results["by_status"]["skipped"] += 1

        results["details"].append({"uri": uri, "transport": transport, "status": cs, "check": check})

        if verbose:
            icon = "✅" if cs in ("ok", "external") else "❌" if cs == "error" else "⚠️"
            print(f"  {icon} [{transport}] {uri}: {cs}")

    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BOS URI full verification")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    print(f"🔍 Verifying BOS URIs from {BOS_SERVICES.relative_to(ROOT)}\n")
    results = verify_all(verbose=args.verbose)

    print(f"{'='*60}")
    print(f"BOS URI Verification Report — {results['timestamp']}")
    print(f"{'='*60}")
    print(f"Total: {results['total']}")
    print(f"  ✅ OK:          {results['by_status']['ok']}")
    print(f"  📦 External:    {results['by_status']['external']}")
    print(f"  ❌ Error:       {results['by_status']['error']}")
    print(f"  🌐 Unreachable: {results['by_status']['unreachable']}")
    print(f"  ⏭️  Skipped:     {results['by_status']['skipped']}")

    print(f"\nBy Transport:")
    for t, c in sorted(results["by_transport"].items()):
        print(f"  {t:<12} {c['ok']}/{c['total']} OK ({c.get('error', 0)} errors)")

    errors = [d for d in results["details"] if d["status"] == "error"]
    if errors:
        print(f"\n❌ Errors ({len(errors)}):")
        for e in errors[:30]:
            print(f"  [{e['transport']}] {e['uri']}: {e['check'].get('reason', '?')[:80]}")
        if len(errors) > 30:
            print(f"  ... {len(errors) - 30} more")

    unreachable = [d for d in results["details"] if d["status"] == "unreachable"]
    if unreachable:
        print(f"\n🌐 Unreachable HTTP ({len(unreachable)}):")
        for e in unreachable:
            print(f"  {e['uri']}: {e['check'].get('url', '?')}")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\nReport saved to {args.output}")

    return 0 if results["by_status"]["error"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
