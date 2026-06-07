#!/usr/bin/env python3
"""
SSB Auth — HMAC-based event signing for SSB integrity.
Usage:
  python3 ssb_auth.py keygen              # Generate signing key
  python3 ssb_auth.py verify              # Verify event signatures
Status: Phase 4 — v1.1 (signature verification fixed)
"""

import hashlib
import hmac
import os
import sqlite3
import sys
from pathlib import Path

ECOS_HOME = Path(__file__).resolve().parents[3]
KEY_FILE = ECOS_HOME / "LADS" / "ssb" / ".ssb_key"
DB_PATH = ECOS_HOME / "LADS" / "ssb" / "ecos.db"


def _load_key():
    env_key = os.environ.get("SSB_KEY", "")
    if env_key:
        return env_key.encode()
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()
    return None


def _ensure_schema(db: sqlite3.Connection):
    """确保 ssb_events 表有 agent_signature 列"""
    cols = [r[1] for r in db.execute("PRAGMA table_info(ssb_events)").fetchall()]
    if "agent_signature" not in cols:
        db.execute("ALTER TABLE ssb_events ADD COLUMN agent_signature TEXT")
        db.commit()


def keygen():
    key = os.urandom(32)
    KEY_FILE.write_bytes(key)
    os.chmod(KEY_FILE, 0o600)
    print(f"✅ Key saved to {KEY_FILE} (permissions: 600)")


def compute_signature(seq: int, event_id: str, agent: str, payload: str):
    """计算事件 HMAC-SHA256 签名 (截取前16字符=64bits), 返回None如果无密钥"""
    key = _load_key()
    if not key:
        return None
    content = f"{seq}|{event_id}|{agent}|{payload or ''}"
    return hmac.new(key, content.encode(), hashlib.sha256).hexdigest()[:16]


def verify(limit: int = 100):
    """验证事件签名并返回统计"""
    key = _load_key()
    if not key:
        return {"status": "no_key", "verified": 0, "unsigned": 0, "mismatch": 0}

    db = sqlite3.connect(str(DB_PATH))
    _ensure_schema(db)

    rows = db.execute(
        "SELECT id, seq, payload_json, source_agent, agent_signature FROM ssb_events "
        "WHERE source_agent IN ('HERMES','CAPTURE_WATCHER','FILTER_SCORER','SSB_CLIENT',"
        "'INTEGRATE_PIPELINE','KANBAN_BRIDGE') "
        "ORDER BY seq DESC LIMIT ?",
        (limit,),
    ).fetchall()

    stats = {"verified": 0, "unsigned": 0, "mismatch": 0, "total": len(rows)}

    for eid, seq, payload, agent, stored_sig in rows:
        expected = compute_signature(seq, eid, agent, payload or "")

        if stored_sig is None:
            stats["unsigned"] += 1
        elif stored_sig == expected:
            stats["verified"] += 1
        else:
            stats["mismatch"] += 1

    db.close()

    if stats["mismatch"] > 0:
        print(f"❌ 签名不匹配: {stats['mismatch']}/{stats['total']}")
        return stats
    if stats["unsigned"] > 0:
        print(f"⚠️  未签名: {stats['unsigned']}/{stats['total']} (旧事件, Phase 3 遗留)")
    if stats["verified"] > 0:
        print(f"✅ 已验证: {stats['verified']}/{stats['total']}")

    stats["status"] = "ok" if stats["mismatch"] == 0 else "mismatch"
    return stats


def sign_new_events(limit: int = 50, all_events: bool = False):
    """为新事件签名 (补充 agent_signature 字段)"""
    key = _load_key()
    if not key:
        print("⚠️  No SSB_KEY set")
        return 0

    db = sqlite3.connect(str(DB_PATH))
    _ensure_schema(db)

    if all_events:
        rows = db.execute(
            "SELECT id, seq, payload_json, source_agent FROM ssb_events WHERE agent_signature IS NULL ORDER BY seq"
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT id, seq, payload_json, source_agent FROM ssb_events "
            "WHERE agent_signature IS NULL ORDER BY seq DESC LIMIT ?",
            (limit,),
        ).fetchall()

    signed = 0
    for eid, seq, payload, agent in rows:
        sig = compute_signature(seq, eid, agent, payload or "")
        if sig:
            db.execute("UPDATE ssb_events SET agent_signature = ? WHERE id = ?", (sig, eid))
            signed += 1

    db.commit()
    db.close()
    print(f"✅ 签名 {signed}/{len(rows)} 个事件")
    return signed


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"

    if cmd == "keygen":
        keygen()
    elif cmd == "verify":
        result = verify()
        sys.exit(0 if result.get("status") == "ok" else 1)
    elif cmd == "sign-new":
        all_events = "--all" in sys.argv
        sign_new_events(all_events=all_events)
    else:
        print(f"Unknown: {cmd}")
        print("Commands: keygen | verify | sign-new [--all]")
