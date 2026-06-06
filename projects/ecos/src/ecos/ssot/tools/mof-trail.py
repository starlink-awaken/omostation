#!/usr/bin/env python3
"""
织星 MOF — 审计追踪统一器 (mof-trail)
=====================================
聚合三套审计源，提供统一查询:
  1. CARDS card_history (SQLite)
  2. daemon cycles (daemon-state.db)
  3. healer attempts (healer-state.db)

用法:
    python3 mof-trail.py             # 最近审计事件
    python3 mof-trail.py --since 24h # 24小时内
    python3 mof-trail.py --type debt # 仅债务事件
    python3 mof-trail.py --json      # JSON
"""

import sys, json, sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

HOME = Path.home()
CARDS_DB = HOME / "Workspace" / "data" / "cards" / "cards.db"
DAEMON_DB = HOME / ".ecos" / "daemon-state.db"
HEALER_DB = HOME / ".ecos" / "healer-state.db"


def now(): return datetime.now(timezone.utc)


def trail_cards(since: datetime | None = None) -> list[dict]:
    if not CARDS_DB.exists():
        return []
    conn = sqlite3.connect(str(CARDS_DB))
    
    # Check if card_history table exists
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    
    events = []
    
    if "card_history" in tables:
        try:
            # Try common column names
            cur = conn.execute("SELECT * FROM card_history LIMIT 1")
            cols = [d[0] for d in cur.description]
            query = f"SELECT {', '.join(cols[:5])} FROM card_history"
            if since:
                query += " WHERE timestamp >= ?" if "timestamp" in cols else ""
            cur = conn.execute(query + " ORDER BY 1 DESC LIMIT 10")
            for row in cur.fetchall():
                events.append({
                    "source": "CARDS",
                    "id": str(row[0]),
                    "action": "history",
                    "detail": str(row[1]) if len(row) > 1 else "",
                    "timestamp": str(row[-1]) if row[-1] else "",
                })
        except:
            pass
    
    # Also check cards table for recent changes
    if "cards" in tables:
        query = "SELECT id, type, status, updated_at, substr(title,1,60) FROM cards"
        if since:
            query += " WHERE updated_at >= ?"
            cur = conn.execute(query, (since.isoformat(),))
        else:
            cur = conn.execute(query + " ORDER BY updated_at DESC LIMIT 20")
        for row in cur.fetchall():
            events.append({
                "source": "CARDS",
                "id": row[0],
                "action": f"{row[1]}:{row[2]}",
                "detail": (row[4] or "")[:80],
                "timestamp": row[3],
            })
    
    conn.close()
    return events


def trail_daemon(since: datetime | None = None) -> list[dict]:
    if not DAEMON_DB.exists():
        return []
    conn = sqlite3.connect(str(DAEMON_DB))
    events = []
    
    query = "SELECT id, started_at, completed_at, exit_code, summary FROM cycles"
    if since:
        query += " WHERE started_at >= ?"
        cur = conn.execute(query, (since.isoformat(),))
    else:
        cur = conn.execute(query + " ORDER BY id DESC LIMIT 20")
    
    for row in cur.fetchall():
        events.append({
            "source": "DAEMON",
            "id": f"cycle-{row[0]}",
            "action": f"exit={row[3]}",
            "detail": (row[4] or "")[:80],
            "timestamp": row[1],
        })
    
    # Also check alerts
    try:
        cur = conn.execute("SELECT id, alert_type, message, created_at FROM alerts ORDER BY id DESC LIMIT 10")
        for row in cur.fetchall():
            events.append({
                "source": "DAEMON",
                "id": f"alert-{row[0]}",
                "action": row[1],
                "detail": row[2][:80],
                "timestamp": row[3],
            })
    except:
        pass
    
    conn.close()
    return events


def trail_healer(since: datetime | None = None) -> list[dict]:
    if not HEALER_DB.exists():
        return []
    conn = sqlite3.connect(str(HEALER_DB))
    events = []
    
    query = "SELECT id, check_type, issue, action, result, timestamp FROM heal_attempts"
    if since:
        query += " WHERE timestamp >= ?"
        cur = conn.execute(query, (since.isoformat(),))
    else:
        cur = conn.execute(query + " ORDER BY id DESC LIMIT 20")
    
    for row in cur.fetchall():
        events.append({
            "source": "HEALER",
            "id": f"heal-{row[0]}",
            "action": row[1],
            "detail": f"{row[2][:40]} → {row[3][:30]}: {row[4][:20]}",
            "timestamp": row[5],
        })
    
    conn.close()
    return events


def get_mof_events(since: datetime | None = None) -> list[dict]:
    """MOF 治理事件 (从 gate snapshot 推导)"""
    snap = HOME / ".ecos" / "gate-snapshot.json"
    if not snap.exists():
        return []
    with open(snap) as f:
        data = json.load(f)
    ts = data.get("timestamp", "")
    return [{
        "source": "MOF",
        "id": "gate-snapshot",
        "action": "变更门禁基线",
        "detail": f"{len(data.get('assets', {}))} 资产已注册",
        "timestamp": ts,
    }]


def format_trail(events: list[dict]) -> str:
    # Sort by timestamp descending
    events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    
    lines = ["=" * 64, "  织星 MOF — 统一审计追踪", "=" * 64,
             f"  时间: {now().isoformat()[:19]}",
             f"  事件: {len(events)} 条", ""]
    
    by_source = {}
    for e in events:
        by_source.setdefault(e["source"], []).append(e)
    
    for source in sorted(by_source.keys()):
        evts = by_source[source][:8]
        lines.append(f"  ── {source} ({len(by_source[source])} 条) ──")
        for e in evts:
            ts = (e.get("timestamp", "") or "")[:19]
            lines.append(f"  {ts} | {e['action'][:20]:20s} | {e['detail'][:60]}")
        lines.append("")
    
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", type=str, default="", help="时间范围 (24h/7d/30d)")
    parser.add_argument("--type", type=str, default="all")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    since = None
    if args.since:
        n = int(args.since.replace("h", "").replace("d", "").replace("m", ""))
        if "h" in args.since:
            since = now() - timedelta(hours=n)
        elif "d" in args.since:
            since = now() - timedelta(days=n)
        elif "m" in args.since:
            since = now() - timedelta(days=n * 30)

    events = []
    if args.type in ("all", "cards"):
        events.extend(trail_cards(since))
    if args.type in ("all", "daemon"):
        events.extend(trail_daemon(since))
    if args.type in ("all", "healer"):
        events.extend(trail_healer(since))
    if args.type in ("all", "mof"):
        events.extend(get_mof_events(since))

    if args.json:
        print(json.dumps({"events": len(events), "items": events}, ensure_ascii=False, indent=2))
    else:
        print(format_trail(events))


if __name__ == "__main__":
    main()
