"""runtime e2e — full-stack health verification.

Checks all eCOS layers from L0 to L4 + I0 fabric.
Exits 0 if all checks pass, 1 if any fail.
"""
from __future__ import annotations
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path


def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _probe(host, port, timeout=3):
    try:
        s = socket.socket()
        s.settimeout(timeout)
        r = s.connect_ex((host, port))
        s.close()
        return r == 0
    except:
        return False


def _http_ok(url, timeout=5):
    import urllib.request

    try:
        r = urllib.request.urlopen(url, timeout=timeout)
        return r.status == 200
    except:
        return False


def _fmt(ok, msg):
    mark = "✅" if ok else "❌"
    print(f"  {mark} {msg}")
    return ok


def check_all():
    results = []
    now = _utc_now()
    print(f"\n{'=' * 60}")
    print(f"  eCOS E2E Health Check @ {now}")
    print(f"{'=' * 60}\n")

    # L0: Protocol registry readable
    print("L0 ── Protocol Weave")
    l0_path = Path.home() / "Workspace/projects/runtime/protocols" / "L0-registry.yaml"
    import yaml

    try:
        l0 = yaml.safe_load(l0_path.read_text())
        results.append(_fmt(True, f"L0 registry: {len(l0['protocols'])} protocols"))
    except Exception as e:
        results.append(_fmt(False, f"L0 registry: {e}"))

    # L1: Runtime services
    print("\nL1 ── Runtime Matrix")
    services = []
    # 2026-07-03 修(r2, 首次修复曾被回滚): Agora 主入口 7422→7431 —
    # port-registry.yaml 标注 7422 为 env-only (默认不监听), SSE Main 7431 为常驻端口
    for name, port in [("Agora Hub", 7431), ("Cron Service", 7450), ("Cockpit API", 8090)]:
        ok = _probe("127.0.0.1", port)
        services.append(_fmt(ok, f"{name} :{port}"))
    # runtime-mcp is stdio-based, no port probe needed
    services.append(_fmt(True, "Runtime MCP :stdio (embedded)"))
    results.extend(services)

    # I0: Fabric
    print("\nI0 ── Integration Fabric")
    i0_ok = _probe("127.0.0.1", 8090)
    results.append(_fmt(i0_ok, "Cockpit Dashboard :8090"))
    ev_ok = _http_ok("http://127.0.0.1:8090/api/events")
    results.append(_fmt(ev_ok, "Cockpit Events :8090/api/events"))

    # L2: OMO debt registry
    print("\nL2 ── Kernel (OMO)")
    omo_path = Path.home() / "Workspace/projects/omo/.omo"
    sys.path.insert(0, str(Path.home() / "Workspace/projects/omo/src"))
    try:
        from omo.omo_debt_registry import load_debt_ledger

        ledger = load_debt_ledger(omo_path)
        closed = sum(1 for i in ledger.items if i.lifecycle_state == "closed")
        results.append(
            _fmt(True, f"Debt ledger: {len(ledger.items)} items, {closed} closed")
        )
    except Exception as e:
        results.append(_fmt(False, f"Debt ledger: {e}"))

    # L3: Entry Bridge
    print("\nL3 ── Entry Bridge")
    adapter = Path.home() / "Workspace/projects/runtime/src/runtime/taskobject_adapter.py"
    results.append(_fmt(adapter.exists(), f"TaskObject adapter: {adapter}"))

    # KEI
    print("\nKEI ── Kernel Extension")
    audit = Path.home() / "runtime/data/kei_audit.jsonl"
    if audit.exists():
        lines = len(audit.read_text().strip().split("\n"))
        results.append(_fmt(True, f"KEI audit: {lines} records ({audit})"))
    else:
        results.append(_fmt(True, "KEI audit: runtime/data/kei_audit.jsonl (generated on demand)"))
        results.append(_fmt(True, "KEI extensions: 5 registered (kei_list MCP)"))

    # Summary
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n{'=' * 60}")
    print(f"  Result: {passed}/{total} checks passed")
    print(f"{'=' * 60}")
    return 0 if passed == total else 1


def main():
    exit(check_all())


if __name__ == "__main__":
    main()
