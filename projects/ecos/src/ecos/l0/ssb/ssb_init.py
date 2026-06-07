#!/usr/bin/env python3
"""
SSB Init — Initialize or recover SSB SQLite database for eCOS Phase 2.

Usage:
    # First-time init
    python3 ssb_init.py

    # Recover from files (rebuild SQLite from STATE/HANDOFF/FAILURES)
    python3 ssb_init.py --recover

    # Verify existing DB integrity
    python3 ssb_init.py --verify

    # Full reset (WARNING: destroys existing SSB events not backed by files)
    python3 ssb_init.py --reset

    # Stats only (no side effects)
    python3 ssb_init.py --stats
"""

import json
import sys
from pathlib import Path

# Add parent to path so ssb_client is importable
sys.path.insert(0, str(Path(__file__).parent))
from ecos.protocol.ssb.ssb_client import SSB_DB_PATH, SSBClient, _now  # type: ignore[import-not-found]


def do_init():
    """First-time initialization."""
    ssb = SSBClient(auto_init=True)

    if SSB_DB_PATH.exists() and SSB_DB_PATH.stat().st_size > 0:
        print(f"ℹ️  SSB database already exists: {SSB_DB_PATH} ({SSB_DB_PATH.stat().st_size:,} bytes)")
        print("   Use --recover to rebuild from files, or --reset to start fresh.")
        return False

    print(f"✅ SSB database created: {SSB_DB_PATH}")

    # Publish initial SYSTEM event
    eid = ssb.publish(
        {
            "event": {"type": "SIGNAL", "subtype": "SYSTEM_INIT"},
            "source": {"agent": "SSB_CLIENT", "instance": "ssb_init"},
            "timestamp": _now(),
            "payload": {
                "summary": "SSB Phase 2 initialized",
                "detail": "SQLite event table created. Dual-write mode active.",
                "confidence": 1.0,
                "risk_level": "LOW",
                "priority": "P3",
                "action_required": "NONE",
            },
        },
        write_file=False,
    )
    print(f"   Initial event: {eid}")
    return True


def do_recover():
    """Rebuild SQLite from files (STATE.yaml, HANDOFF, FAILURES)."""
    ssb = SSBClient(auto_init=False)
    stats = ssb.recover_from_files()

    total = sum(stats.values())
    print(f"✅ Recovery complete: {total} events restored")
    for k, v in stats.items():
        print(f"   {k}: {v}")

    # Publish recovery event
    ssb.publish(
        {
            "event": {"type": "SIGNAL", "subtype": "RECOVERY_DONE"},
            "source": {"agent": "SSB_CLIENT", "instance": "ssb_init"},
            "timestamp": _now(),
            "payload": {
                "summary": f"SSB recovered: {total} events from files",
                "detail": json.dumps(stats),
                "confidence": 1.0,
                "risk_level": "LOW",
                "action_required": "NONE",
            },
        },
        write_file=False,
    )
    return True


def do_verify():
    """Check database integrity."""
    if not SSB_DB_PATH.exists():
        print("❌ SSB database not found. Run without --recover to initialize.")
        return False

    ssb = SSBClient(auto_init=False)
    conn = ssb._get_conn()
    try:
        # Integrity check
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        if integrity and integrity[0] != "ok":
            print(f"❌ Integrity check failed: {integrity[0]}")
            return False
        print("✅ Integrity: OK")

        # Row count
        total = conn.execute("SELECT COUNT(*) AS c FROM ssb_events").fetchone()["c"]
        print(f"   Events: {total}")

        # By type
        by_type = conn.execute(
            "SELECT event_type, COUNT(*) AS c FROM ssb_events GROUP BY event_type ORDER BY c DESC"
        ).fetchall()
        for r in by_type:
            print(f"   • {r['event_type']:<14} → {r['c']}")

        # Index check
        idx_count = conn.execute(
            "SELECT COUNT(*) AS c FROM sqlite_master WHERE type='index' AND tbl_name='ssb_events'"
        ).fetchone()["c"]
        print(f"   Indexes: {idx_count}")

        # Latest events
        print("\n   Latest events:")
        latest = conn.execute("SELECT seq, event_type, summary FROM ssb_events ORDER BY seq DESC LIMIT 5").fetchall()
        for r in latest:
            print(f"     #{r['seq']} {r['event_type']:<14} {r['summary'][:50]}")

    finally:
        conn.close()
    return True


def do_stats():
    """Print statistics without side effects."""
    if not SSB_DB_PATH.exists():
        print("SSB database: NOT FOUND")
        print(f"  Expected at: {SSB_DB_PATH}")
        return False

    ssb = SSBClient(auto_init=False)
    conn = ssb._get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) AS c FROM ssb_events").fetchone()["c"]

        db_size = SSB_DB_PATH.stat().st_size

        print(f"SSB Database: {SSB_DB_PATH}")
        print(f"  Size: {db_size:,} bytes ({db_size / 1024:.1f} KB)")
        print(f"  Events: {total}")

        by_type = conn.execute(
            "SELECT event_type, COUNT(*) AS c FROM ssb_events GROUP BY event_type ORDER BY c DESC"
        ).fetchall()
        for r in by_type:
            print(f"  • {r['event_type']:<14} → {r['c']}")

        by_risk = conn.execute(
            "SELECT risk_level, COUNT(*) AS c FROM ssb_events GROUP BY risk_level ORDER BY c DESC"
        ).fetchall()
        for r in by_risk:
            print(f"  • risk={r['risk_level']:<8} → {r['c']}")

        by_action = conn.execute(
            "SELECT action_req, COUNT(*) AS c FROM ssb_events GROUP BY action_req ORDER BY c DESC"
        ).fetchall()
        for r in by_action:
            print(f"  • action={r['action_req']:<15} → {r['c']}")

    finally:
        conn.close()
    return True


def do_reset():
    """WARNING: Destroys SQLite, events without file backup are lost."""
    if SSB_DB_PATH.exists():
        backup = SSB_DB_PATH.with_suffix(".db.bak")
        import shutil

        shutil.copy2(str(SSB_DB_PATH), str(backup))
        SSB_DB_PATH.unlink()
        print(f"⚠️  Database deleted. Backup saved: {backup}")
    else:
        print("No database to reset.")

    do_init()
    return True


def main():
    if len(sys.argv) < 2:
        do_init()
        return

    cmd = sys.argv[1]

    if cmd in ("--init", "-i"):
        do_init()
    elif cmd in ("--recover", "-r"):
        do_recover()
    elif cmd in ("--verify", "-v"):
        do_verify()
    elif cmd in ("--stats", "-s"):
        do_stats()
    elif cmd in ("--reset", "-R"):
        print("⚠️  WARNING: Reset will destroy SSB events not backed by files.")
        do_reset()
    elif cmd in ("--help", "-h"):
        print(__doc__)
    else:
        print(f"Unknown option: {cmd}")
        print("Usage: python3 ssb_init.py [--init|--recover|--verify|--stats|--reset|--help]")
        sys.exit(1)


if __name__ == "__main__":
    main()
