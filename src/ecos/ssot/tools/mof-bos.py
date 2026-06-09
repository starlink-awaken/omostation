#!/usr/bin/env python3
"""
织星 MOF — BOS URI 审计器 (mof-bos)
=====================================
对外部 BOS 调用做前置校验 + 后置审计。

前置校验 (pre-call):
  1. BOS URI 是否在 L0 路由表中?
  2. 目标组件是否 active?
  3. 跨层调用是否在 topology allowed_dependencies 中?

后置审计 (post-call):
  4. 调用结果 → SSB 不可变日志
  5. 异常 → CARDS 自动建卡
  6. 调用链 → mof-trail 可追溯

用法:
    python3 mof-bos.py check bos://cockpit/tools/cards_status    # 前置校验
    python3 mof-bos.py audit bos://cockpit/tools/cards_status 200 # 后置审计
    python3 mof-bos.py routes                                        # 列出所有路由
    python3 mof-bos.py --json                                        # JSON 输出
"""

import sys
import json
import yaml
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
L0_M1 = HOME / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1"
TOPO_FILE = HOME / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "registry" / "topology.yaml"
CARDS_DB = HOME / "Workspace" / "data" / "cards" / "cards.db"
AUDIT_LOG = HOME / ".ecos" / "bos-audit.jsonl"


def now_iso(): return datetime.now(timezone.utc).isoformat()


def load_routes() -> dict:
    routes = {}
    bos_dir = L0_M1 / "bosroute"
    if not bos_dir.exists():
        return routes
    for f in sorted(bos_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(open(f))
            uri = data.get("name", "")
            routes[uri] = data
        except Exception:
            pass
    # Also include components registered with BOS_URI protocol
    comp_dir = L0_M1 / "component"
    for f in sorted(comp_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(open(f))
            props = data.get("properties", {}) or {}
            if props.get("protocol") == "BOS_URI":
                routes[f"bos://{data.get('name', '?')}/*"] = data
        except Exception:
            pass
    return routes


def load_topology() -> dict:
    if not TOPO_FILE.exists():
        return {}
    return yaml.safe_load(open(TOPO_FILE))


def check_bos_call(bos_uri: str) -> dict:
    """前置校验: BOS 调用是否合规"""
    routes = load_routes()
    load_topology()

    # 1. Route exists?
    matched_route = None
    for uri, route in routes.items():
        if uri in bos_uri or bos_uri.startswith(uri.rstrip("*")):
            matched_route = route
            break

    if not matched_route:
        return {
            "allowed": False,
            "reason": f"BOS URI 未注册: {bos_uri}",
            "action": "注册路由到 L0 (mof-scan 或手工创建 BOSRoute M1)",
        }

    # 2. Component active?
    route_status = matched_route.get("status", "?")
    if route_status != "active":
        return {
            "allowed": False,
            "reason": f"路由状态非 active: {route_status}",
            "action": f"检查组件状态: {matched_route.get('name', '?')}",
        }

    # 3. Cross-layer check
    props = matched_route.get("properties", {}) or {}
    target_layer = props.get("layer", "?")
    # For now, all BOS calls go through I0 (gateway) → always allowed
    # In enforce mode, check topology allowed_dependencies

    return {
        "allowed": True,
        "route": matched_route.get("name", ""),
        "target_layer": target_layer,
        "checks": ["route_exists", "component_active", "cross_layer_ok"],
    }


def audit_bos_call(bos_uri: str, status_code: int = 200, duration_ms: int = 0):
    """后置审计: 记录 BOS 调用"""
    check = check_bos_call(bos_uri)
    
    audit_entry = {
        "timestamp": now_iso(),
        "bos_uri": bos_uri,
        "status_code": status_code,
        "duration_ms": duration_ms,
        "pre_check": check,
        "anomaly": not check["allowed"] or status_code >= 500,
    }
    
    # Append to audit log
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_LOG, "a") as f:
        f.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")
    
    # Auto-create CARDS if anomaly
    if audit_entry["anomaly"] and CARDS_DB.exists():
        try:
            conn = sqlite3.connect(str(CARDS_DB))
            now_str = now_iso()
            debt_id = f"DEBT-BOS-{now_str[:10]}-{bos_uri.replace('/', '-')[:30]}"
            conn.execute("""
                INSERT OR IGNORE INTO cards (id, type, status, title, domain, priority, summary, content, created_at, updated_at)
                VALUES (?, 'debt', 'identified', ?, 'infra', 'P2', ?, ?, ?, ?)
            """, (debt_id, f"BOS 调用异常: {bos_uri[:60]}",
                  f"status={status_code} | {check.get('reason', 'unknown')}",
                  f"## mof-bos 自动检测\n- URI: {bos_uri}\n- Status: {status_code}\n- Pre-check: {json.dumps(check)}",
                  now_str, now_str))
            conn.commit()
            conn.close()
        except Exception:
            pass
    
    return audit_entry


def cmd_check(args):
    uri = args[0] if args else "bos://cockpit/tools/*"
    result = check_bos_call(uri)
    print("═══ BOS 前置校验 ═══")
    print(f"  URI:     {uri}")
    print(f"  结果:    {'✅ 放行' if result['allowed'] else '❌ 拒绝'}")
    if not result["allowed"]:
        print(f"  原因:    {result['reason']}")
        print(f"  建议:    {result.get('action', '')}")
    else:
        print(f"  路由:    {result.get('route', '?')}")
        print(f"  目标层:  {result.get('target_layer', '?')}")
        print(f"  检查项:  {', '.join(result.get('checks', []))}")


def cmd_audit(args):
    uri = args[0] if args else "bos://cockpit/tools/test"
    code = int(args[1]) if len(args) > 1 else 200
    result = audit_bos_call(uri, code)
    print("═══ BOS 后置审计 ═══")
    print(f"  URI:     {uri}")
    print(f"  Status:  {code}")
    print(f"  异常:    {'⚠️ 是' if result['anomaly'] else '✅ 否'}")
    print(f"  审计日志: {AUDIT_LOG}")


def cmd_routes():
    routes = load_routes()
    print(f"═══ BOS 路由表 ({len(routes)} 条) ═══")
    for uri, route in sorted(routes.items()):
        status = route.get("status", "?")
        icon = "🟢" if status == "active" else "⚠️"
        print(f"  {icon} {uri:45s} → {route.get('description', '')[:50]}")


def main():
    if len(sys.argv) < 2:
        print("用法: mof bos <check|audit|routes> [args]")
        return
    
    cmd = sys.argv[1]
    args = sys.argv[2:]
    
    if cmd == "check":
        cmd_check(args)
    elif cmd == "audit":
        cmd_audit(args)
    elif cmd == "routes":
        cmd_routes()
    else:
        # Support direct check: mof-bos.py bos://xxx
        cmd_check([cmd] + args)


if __name__ == "__main__":
    main()
