"""
织星 MOF — Agora BOS Hook 适配器 (mof_agora_hook)
==================================================
供 Agora 直接 import 使用的 BOS 审计模块。
Agora 在处理每个 BOS 请求时调用 pre_check / post_audit。

用法 (在 Agora 代码中):
    from mof_agora_hook import pre_check, post_audit
    
    # 请求进入时
    ok, reason = pre_check("bos://cockpit/tools/cards_status")
    if not ok:
        return 403, reason
    
    # 请求完成后
    post_audit("bos://cockpit/tools/cards_status", 200, 45)

性能:
    - 路由表缓存在内存，首次加载后 < 1ms
    - 异常时异步写审计日志，不阻塞请求
"""

import json, yaml, sqlite3, time
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
ROUTES_CACHE = None
ROUTES_CACHE_TIME = 0
CACHE_TTL = 300  # 5 min
AUDIT_LOG = HOME / ".ecos" / "bos-audit.jsonl"
CARDS_DB = HOME / "Workspace" / "data" / "cards" / "cards.db"
L0_M1 = HOME / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1"

# ── 性能统计 ──
stats = {"total_checks": 0, "total_audits": 0, "blocked": 0, "anomalies": 0, "start_time": time.time()}


def _load_routes() -> dict:
    """加载 BOS 路由表 (带内存缓存)"""
    global ROUTES_CACHE, ROUTES_CACHE_TIME
    
    now = time.time()
    if ROUTES_CACHE and (now - ROUTES_CACHE_TIME) < CACHE_TTL:
        return ROUTES_CACHE
    
    routes = {}
    
    # Load from BOSRoute M1 nodes
    bos_dir = L0_M1 / "bosroute"
    if bos_dir.exists():
        for f in bos_dir.glob("*.yaml"):
            try:
                data = yaml.safe_load(open(f))
                uri = data.get("name", "")
                if uri:
                    routes[uri] = {
                        "status": data.get("status", "?"),
                        "layer": (data.get("properties", {}) or {}).get("layer", "?"),
                        "description": data.get("description", ""),
                    }
            except:
                pass
    
    # Load from Component nodes with BOS_URI protocol
    comp_dir = L0_M1 / "component"
    if comp_dir.exists():
        for f in comp_dir.glob("*.yaml"):
            try:
                data = yaml.safe_load(open(f))
                props = data.get("properties", {}) or {}
                if props.get("protocol") == "BOS_URI":
                    name = data.get("name", "")
                    uri = f"bos://{name}/*"
                    routes[uri] = {
                        "status": data.get("status", "?"),
                        "layer": props.get("layer", "?"),
                        "description": data.get("description", ""),
                    }
            except:
                pass
    
    ROUTES_CACHE = routes
    ROUTES_CACHE_TIME = now
    return routes


def _match_route(bos_uri: str, routes: dict) -> dict | None:
    """匹配 BOS URI 到路由"""
    for uri, route in routes.items():
        pattern = uri.rstrip("*")
        if bos_uri.startswith(pattern):
            return route
    return None


def pre_check(bos_uri: str) -> tuple[bool, str]:
    """
    前置校验 — Agora 在路由前调用
    
    Returns:
        (True, "ok") — 放行
        (False, reason) — 拒绝，返回 403
    """
    stats["total_checks"] += 1
    
    routes = _load_routes()
    route = _match_route(bos_uri, routes)
    
    if not route:
        stats["blocked"] += 1
        return False, f"BOS URI 未注册: {bos_uri}"
    
    if route["status"] != "active":
        stats["blocked"] += 1
        return False, f"路由已废弃: {route['status']}"
    
    return True, "ok"


def post_audit(bos_uri: str, status_code: int, duration_ms: int = 0):
    """
    后置审计 — Agora 在响应后调用
    
    同步写审计日志。Agora Server 是长进程，CLI 模式也不丢失。
    """
    stats["total_audits"] += 1
    
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "bos_uri": bos_uri,
        "status_code": status_code,
        "duration_ms": duration_ms,
        "anomaly": status_code >= 500,
    }
    
    if entry["anomaly"]:
        stats["anomalies"] += 1
    
    # 同步写入审计日志
    try:
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_LOG, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass
    
    # 异常时自动创建 CARDS 债务卡片
    if entry["anomaly"] and CARDS_DB.exists():
        try:
            conn = sqlite3.connect(str(CARDS_DB))
            now_str = datetime.now(timezone.utc).isoformat()
            debt_id = f"DEBT-BOS-{now_str[:10]}-{bos_uri.replace('/', '-')[:30]}"
            conn.execute("""
                INSERT OR IGNORE INTO cards (id, type, status, title, domain, priority, summary, content, created_at, updated_at)
                VALUES (?, 'debt', 'identified', ?, 'infra', 'P2', ?, ?, ?, ?)
            """, (debt_id, f"BOS 异常: {bos_uri[:60]}",
                  f"status={status_code} duration={duration_ms}ms",
                  f"## mof-bos auto-detect\n- URI: {bos_uri}\n- Status: {status_code}\n- Duration: {duration_ms}ms",
                  now_str, now_str))
            conn.commit()
            conn.close()
        except Exception:
            pass


def health_check() -> dict:
    """健康检查 — 供 Agora 监控"""
    routes = _load_routes()
    uptime = time.time() - stats["start_time"]
    return {
        "status": "healthy",
        "routes_count": len(routes),
        "cache_age": time.time() - ROUTES_CACHE_TIME,
        "stats": {
            "total_checks": stats["total_checks"],
            "total_audits": stats["total_audits"],
            "blocked": stats["blocked"],
            "anomalies": stats["anomalies"],
            "block_rate": f"{stats['blocked']/max(stats['total_checks'],1)*100:.1f}%",
            "uptime_hours": f"{uptime/3600:.1f}h",
        },
    }


# ── CLI for testing ──
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python3 mof_agora_hook.py <bos_uri>")
        print(f"  路由数: {len(_load_routes())}")
        print(f"  健康: {health_check()}")
        sys.exit(0)
    
    uri = sys.argv[1]
    ok, reason = pre_check(uri)
    print(f"Pre-check: {'✅' if ok else '❌'} {reason}")
    if ok:
        post_audit(uri, 200, 12)
        print(f"Post-audit: logged")
        print(f"Stats: {health_check()['stats']}")
