#!/usr/bin/env python3
"""SSB Integrity Checker — 哈希链验证 + 序列连续性 + ID去重"""

import hashlib
import sqlite3
import sys
from pathlib import Path

from ecos.common.common import SSB_DB_PATH as DB_PATH  # type: ignore[import-not-found]

CHAIN_CHECKPOINT = (
    Path(__file__).resolve().parent.parent / "LADS" / "ssb" / ".chain_hash"
)


def compute_chain_hash(db):
    """Compute cumulative hash chain across all events."""
    rows = db.execute(
        "SELECT seq, id, timestamp, source_agent, event_type, summary FROM ssb_events ORDER BY seq, id"
    ).fetchall()

    chain = "GENESIS"
    for seq, eid, ts, agent, etype, payload in rows:
        content = f"{seq}|{eid}|{ts or ''}|{agent or ''}|{etype or ''}|{payload or ''}"
        chain = hashlib.sha256((chain + content).encode()).hexdigest()

    return chain, rows, len(rows)


def verify_prefix(rows, stored_hash):
    """Check if stored_hash matches a prefix of the chain (append-only). Returns prefix count or -1."""
    chain = "GENESIS"
    for idx, (seq, eid, ts, agent, etype, payload) in enumerate(rows, 1):
        content = f"{seq}|{eid}|{ts or ''}|{agent or ''}|{etype or ''}|{payload or ''}"
        chain = hashlib.sha256((chain + content).encode()).hexdigest()
        if chain == stored_hash:
            return idx
    return -1


def verify():
    db = sqlite3.connect(str(DB_PATH))
    issues = []

    # 1. Hash chain verification
    current_hash, rows, count = compute_chain_hash(db)

    if CHAIN_CHECKPOINT.exists():
        stored_hash = CHAIN_CHECKPOINT.read_text().strip()
        if stored_hash != current_hash:
            # Check if this is just append-only growth, not modification/tampering
            prefix_count = verify_prefix(rows, stored_hash)
            if prefix_count > 0 and prefix_count < count:
                # Append-only: update checkpoint silently
                CHAIN_CHECKPOINT.write_text(current_hash)
            elif prefix_count == count:
                # Exact match (shouldn't reach here but just in case)
                pass  # will update below
            else:
                issues.append(
                    f"HASH_MISMATCH: stored={stored_hash[:12]}... current={current_hash[:12]}... "
                    f"— existing event data modified or tampered"
                )
    else:
        # First run — establish baseline
        CHAIN_CHECKPOINT.write_text(current_hash)
        print(f"📝 Chain baseline established: {current_hash[:16]}... ({count} events)")

    # 2. Sequence continuity
    rows = db.execute("SELECT seq FROM ssb_events ORDER BY seq").fetchall()
    seqs = [r[0] for r in rows]
    if seqs:
        missing = sorted(set(range(1, seqs[-1] + 1)) - set(seqs))
        if missing:
            issues.append(
                f"Missing seq: {missing[:10]}{'...' if len(missing) > 10 else ''}"
            )

    # 3. Duplicate IDs
    ids = db.execute("SELECT id FROM ssb_events").fetchall()
    id_list = [r[0] for r in ids]
    if len(id_list) != len(set(id_list)):
        from collections import Counter

        dupes = [k for k, v in Counter(id_list).items() if v > 1]
        issues.append(f"Duplicate event_id: {dupes[:5]}")

    db.close()

    # Update checkpoint if no issues
    if not issues:
        CHAIN_CHECKPOINT.write_text(current_hash)

    if issues:
        print("🚨 INTEGRITY VIOLATIONS:")
        for i in issues:
            print(f"  {i}")
        return 1

    print(f"✅ Integrity OK — {count} events, hash={current_hash[:16]}...")
    return 0


if __name__ == "__main__":
    sys.exit(verify())
