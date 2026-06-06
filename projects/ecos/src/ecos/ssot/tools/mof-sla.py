#!/usr/bin/env python3
"""
织星 MOF — SLA 执行器 + M0 快照 (mof-sla)
=============================================
1. 检测逾期任务（基于 Mechanism.sla_target）
2. 生成 M0 运行时快照（协议衰减·daemon状态·任务健康）
3. 逾期任务自动创建 CARDS

用法:
    python3 mof-sla.py                   # SLA检查 + M0快照
    python3 mof-sla.py --snapshot-only   # 仅生成 M0 快照
"""

import sys, json, yaml, sqlite3
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
WS = HOME / "Workspace"
L0_NODES = WS / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "nodes"
M0_FILE = WS / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "M0-snapshot.yaml"
CARDS_DB = WS / "data" / "cards" / "cards.db"
DAEMON_DB = HOME / ".ecos" / "daemon-state.db"
CONSTRAINTS = HOME / "Documents" / "学习进化" / "2-knowledge" / "基建架构" / "L0-constraints.yaml"


def now(): return datetime.now(timezone.utc)


def check_task_sla() -> list[dict]:
    """检查 Mechanism 节点的 SLA"""
    stale = []
    if not L0_NODES.exists():
        return stale
    
    for f in L0_NODES.glob("MECH-*.yaml"):
        try:
            data = yaml.safe_load(open(f))
        except: continue
        
        props = data.get("properties", {}) or {}
        sla = props.get("sla_target", {}) or {}
        max_stale = sla.get("max_stale_hours", 0)
        if max_stale <= 0:
            continue
        
        # Check last modified time as proxy for last run
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        try:
            if mtime.tzinfo is not None:
                mtime = mtime.replace(tzinfo=None)
            hours_since = (now().replace(tzinfo=None) - mtime).total_seconds() / 3600
        except:
            hours_since = 0
        
        if hours_since > max_stale:
            stale.append({
                "task": f.stem,
                "type": data.get("subtype", "?"),
                "hours_stale": round(hours_since, 1),
                "max_allowed": max_stale,
                "severity": "critical" if hours_since > max_stale * 2 else "high",
            })
    
    return stale


def generate_m0_snapshot() -> dict:
    """生成 M0 运行时快照"""
    snap = {
        "generated_at": now().isoformat(),
        "version": "1.0.0",
    }
    
    # Daemon state
    if DAEMON_DB.exists():
        conn = sqlite3.connect(str(DAEMON_DB))
        cur = conn.execute("SELECT COUNT(*), MAX(exit_code) FROM cycles")
        cycles, max_exit = cur.fetchone()
        conn.close()
        snap["daemon"] = {"cycles": cycles, "healthy": max_exit == 0 if max_exit is not None else False, "last_exit": max_exit}
    else:
        snap["daemon"] = {"status": "unknown"}
    
    # Protocol decay
    if CONSTRAINTS.exists():
        with open(CONSTRAINTS) as f:
            data = yaml.safe_load(f)
        registry = data.get("protocol_registry", [])
        protocols = {}
        now_dt = now()
        for p in registry:
            intro = datetime.strptime(p["introduced"], "%Y-%m-%d")
            try:
                if intro.tzinfo is not None:
                    intro = intro.replace(tzinfo=None)
                age = (now_dt.replace(tzinfo=None) - intro).days
            except:
                age = 0
            half = p["half_life_days"]
            decay = min(1.0, age / half) if half > 0 else 1.0
            protocols[p["id"]] = {"decay": round(decay, 2), "remaining_pct": round(max(0, (1-decay)*100), 1), "age_days": age, "status": "expired" if decay >= 1.0 else ("aging" if decay >= 0.5 else "fresh")}
        snap["protocols"] = protocols
    
    # M1 node count
    if L0_NODES.exists():
        snap["m1_node_count"] = len(list(L0_NODES.glob("*.yaml")))
    
    return snap


def save_m0_snapshot(snap: dict):
    M0_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(M0_FILE, 'w') as f:
        f.write("# M0 运行时快照 (自动生成)\n")
        f.write(f"# 更新: {snap['generated_at']}\n\n")
        yaml.dump(snap, f, allow_unicode=True, default_flow_style=False)


def create_stale_card(task: dict):
    if not CARDS_DB.exists():
        return
    try:
        conn = sqlite3.connect(str(CARDS_DB))
        now_dt = now().isoformat()
        debt_id = f"DEBT-STALE-{task['task'][:30]}"
        conn.execute("""
            INSERT OR IGNORE INTO cards (id, type, status, title, domain, priority, summary, content, created_at, updated_at)
            VALUES (?, 'debt', 'identified', ?, 'meta', 'P2', ?, ?, ?, ?)
        """, (debt_id, f"SLA逾期: {task['task'][:60]}",
              f"逾期 {task['hours_stale']}h (上限 {task['max_allowed']}h)",
              f"## mof-sla 自动检测\n- 任务: {task['task']}\n- 逾期: {task['hours_stale']}h\n- 上限: {task['max_allowed']}h",
              now_dt, now_dt))
        conn.commit()
        conn.close()
    except: pass


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    # SLA check
    stale = check_task_sla() if not args.snapshot_only else []
    
    # M0 snapshot
    snap = generate_m0_snapshot()
    save_m0_snapshot(snap)

    if args.json:
        print(json.dumps({"stale_tasks": len(stale), "items": stale, "m0": snap}, ensure_ascii=False, indent=2))
        return

    print("=" * 56)
    print("  织星 MOF — SLA + M0 快照")
    print("=" * 56)
    print(f"  时间: {now().isoformat()[:19]}")
    print(f"\n  ── M0 快照 ──")
    print(f"  Daemon: {snap.get('daemon',{})}")
    protocols = snap.get("protocols", {})
    for pid, state in protocols.items():
        icon = "🔴" if state["status"] == "expired" else ("🟡" if state["status"] == "aging" else "🟢")
        print(f"  {icon} {pid:10s}: {state['remaining_pct']:5.0f}% remaining ({state['age_days']}d)")

    if stale:
        print(f"\n  ── SLA 逾期 ({len(stale)}) ──")
        for s in stale:
            print(f"  {'🔴' if s['severity']=='critical' else '🟡'} {s['task'][:40]}: {s['hours_stale']}h (上限 {s['max_allowed']}h)")
            create_stale_card(s)
    else:
        print(f"\n  ✅ 无 SLA 逾期")
    print("=" * 56)


if __name__ == "__main__":
    main()
