"""Dashboard CLI — 全局算力资源大盘 (缓存加速版)。

Usage:
    aetherforge dashboard
"""

from __future__ import annotations

import sys
import time


def cmd_dashboard() -> int:
    """大盘: 算力资源 + Provider + 配额 + 网络 + 成本全景。"""
    t0 = time.time()

    # ── 1. 启动 QuotaEngine 后台刷新 ──
    from llm_gateway.quota_engine import QuotaEngine
    qe = QuotaEngine()
    qe.start()
    ready = qe.wait_ready(timeout=25)

    # ── 2. Provider 大盘 (缓存, <0.01s) ──
    print()
    print("=" * 58)
    print("  🔮 AetherForge — 算力资源大盘")
    print("=" * 58)
    print()
    print("  ☁️  云 Provider" + (" (后台刷新中)" if not ready else ""))
    print("  " + "-" * 50)

    summary = qe.get_summary()
    for p in summary["providers"]:
        icon = "🟢" if p["available"] else ("⚪" if p["status"] == "no_credentials" else "🔴")
        q = f'{p["quota_pct"]:.0f}%' if p["quota_pct"] != 100 else "充足"
        src = p["quota_source"] if p["quota_source"] else "—"
        bal = f'¥{p["balance"]:.0f}' if p["balance"] > 0 else ""
        print(f"  {icon} {p['provider']:18s} quota={q:6s} src={src:8s} {bal}")

    print(f"  codexbar: {'✅' if summary['codexbar_available'] else '❌'}")
    print(f"  {summary['available']}/{summary['total']} available")
    t1 = time.time()

    # ── 3. 算力节点 (快速扫描，不做健康检查) ──
    print()
    print("  🖥  算力节点")
    print("  " + "-" * 50)
    try:
        from compute_mesh.topology.scanner import load_static_nodes, probe_local_daemons, detect_cloud_nodes
        from compute_mesh.topology.network_scanner import NetworkScanner

        static = load_static_nodes()
        local = probe_local_daemons()
        cloud = detect_cloud_nodes()
        network = NetworkScanner().scan_all()

        all_nodes = static + local + cloud + network
        seen = {}
        for n in all_nodes:
            seen[n.node_id] = n
        nodes = list(seen.values())

        for n in sorted(nodes, key=lambda x: (x.network_zone, x.node_id))[:15]:
            icon = "🟢" if n.is_online else "🔴"
            m = n.machine_info.summary[:16] if n.machine_info else ""
            print(f"  {icon} {n.node_id:30s} {n.engine_type.value:12s} {n.network_zone:6s} {m}")
        online = sum(1 for n in nodes if n.is_online)
        print(f"  {online}/{len(nodes)} online · {len(set(n.network_zone for n in nodes))} zones")
    except Exception as e:
        print(f"  (节点: {e})")
    t2 = time.time()

    # ── 4. 成本 ──
    print()
    print("  💰  成本")
    print("  " + "-" * 50)
    try:
        from compute_mesh.pool import CostTracker
        from compute_mesh.topology import NodeRegistry
        ct = CostTracker(NodeRegistry())
        r = ct.get_report()
        at = r.get("all_time", {})
        print(f"  累计: ${at.get('total_cost',0):.4f} ({at.get('total_requests',0)} req)")
        print(f"  Token: {at.get('total_prompt_tokens',0)} in / {at.get('total_completion_tokens',0)} out")
        
        # DeepSeek balance from cache
        ds = qe.get_quota("deepseek")
        if ds.balance > 0:
            print(f"  DeepSeek 余额: ¥{ds.balance:.0f} ({ds.quota_pct:.0f}%)")
    except Exception as e:
        print(f"  (成本: {e})")
    t3 = time.time()

    # ── 5. Summary ──
    print()
    print(f"  ⏱  {t3-t0:.1f}s total (cache: {t1-t0:.1f}s · mesh: {t2-t1:.1f}s · cost: {t3-t2:.1f}s)")
    print("=" * 58)
    print()

    # Stop background thread
    qe.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(cmd_dashboard())
