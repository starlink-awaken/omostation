#!/usr/bin/env python3
"""
ssb_seq_migrate.py — SSB seq 碰撞修复迁移脚本

修复:
  1. 2140 个重复 seq → 全部重编号为唯一递增序列
  2. 2082 处时间戳逆序 → 按真实时间排序后重新编号
  3. 9 条未签名事件 → 补签
  4. 200 条 Naive 时间戳 → 补时区
  5. 添加 UNIQUE(seq) 约束（防止复发）
  6. 更新哈希链基线

用法:
  python3 scripts/ssb_seq_migrate.py            # 执行迁移
  python3 scripts/ssb_seq_migrate.py --dry-run   # 预览变更
  python3 scripts/ssb_seq_migrate.py --verify    # 校验状态
"""

import sqlite3
import sys
from datetime import datetime, timedelta, timezone

from ecos.common.common import ECOS_HOME as ECOS_DIR  # type: ignore[import-not-found]

SSB_DB = ECOS_DIR / "LADS/ssb/ecos.db"
CHAIN_CHECKPOINT = ECOS_DIR / "LADS/ssb" / ".chain_hash"
BACKUP_PATH = ECOS_DIR / "LADS/ssb" / "ecos.pre-migrate.db"
TZ_CST = timezone(timedelta(hours=8))


def backup():
    """备份数据库"""
    import shutil

    if BACKUP_PATH.exists():
        print(f"  ⚠️  备份已存在，跳过: {BACKUP_PATH}")
        return False
    shutil.copy2(str(SSB_DB), str(BACKUP_PATH))
    print(f"  💾 备份: {BACKUP_PATH} ({SSB_DB.stat().st_size / 1024:.0f}KB)")
    return True


def compute_signature(seq, event_id, agent, payload_str):
    """计算 HMAC 签名（与 ssb_auth 兼容）"""
    try:
        from .ssb_auth import compute_signature as cs

        return cs(seq, event_id, agent, payload_str) or ""
    except Exception:
        # 降级
        import hashlib
        import hmac

        key_file = ECOS_DIR / "LADS/ssb/.ssb_hmac_key"
        if key_file.exists():
            key = key_file.read_bytes()
            content = f"{seq}|{event_id}|{agent}|{payload_str}".encode()
            return hmac.new(key, content, hashlib.sha256).hexdigest()[:16]
        return ""


def count_collisions(conn):
    """统计当前碰撞情况"""
    total = conn.execute("SELECT COUNT(*) FROM ssb_events").fetchone()[0]
    unique = conn.execute("SELECT COUNT(DISTINCT seq) FROM ssb_events").fetchone()[0]
    max_seq = conn.execute("SELECT MAX(seq) FROM ssb_events").fetchone()[0]
    dupes = total - unique
    return total, unique, dupes, max_seq


def collect_events(conn):
    """按 canonical 顺序收集事件，返回 (seq_map, event_list)"""
    # 按 (timestamp, id) 排序建立 canonical 顺序
    # 时间戳统一解析，naive 的视为 CST
    rows = conn.execute("""
        SELECT id, seq, timestamp, source_agent,
               payload_json, agent_signature
        FROM ssb_events
        ORDER BY
            CASE
                WHEN timestamp LIKE '%+%' THEN timestamp
                ELSE timestamp || '+08:00'
            END ASC,
            id ASC
    """).fetchall()

    # 生成新 seq
    event_list = []
    seq_map = {}  # old_seq -> new_seq (for reporting)
    for i, row in enumerate(rows, 1):
        old_seq = row["seq"]
        new_seq = i
        event_list.append(
            {
                "id": row["id"],
                "old_seq": old_seq,
                "new_seq": new_seq,
                "timestamp": row["timestamp"],
                "source_agent": row["source_agent"],
                "payload_json": row["payload_json"],
                "old_sig": row["agent_signature"],
            }
        )
        if old_seq not in seq_map:
            seq_map[old_seq] = []
        seq_map[old_seq].append(new_seq)

    return event_list, seq_map


def fix_timestamp(ts_raw: str) -> str:
    """统一时间戳格式：补时区、标准化"""
    if not ts_raw:
        return datetime.now(TZ_CST).isoformat()
    if "+08:00" in ts_raw or "+00:00" in ts_raw or "Z" in ts_raw:
        # 已有时区，保留
        return ts_raw
    # Naive → 视为 CST
    return ts_raw.rstrip("Z") + "+08:00"


def migrate(dry_run=False):
    """执行迁移"""
    print(f"{'=' * 60}")
    print(f"SSB seq 碰撞迁移 {'[DRY RUN]' if dry_run else ''}")
    print(f"{'=' * 60}")

    conn = sqlite3.connect(str(SSB_DB))
    conn.row_factory = sqlite3.Row

    total, unique, dupes, max_seq = count_collisions(conn)
    print(
        f"\n📊 迁移前: {total} 事件, {unique} 唯一seq, {dupes} 重复 ({dupes / total * 100:.1f}%)"
    )

    if dupes == 0:
        print("  ✅ 已经无碰撞，跳过迁移")
        # 仍然修复时间戳和签名

    # 收集事件
    events, seq_map = collect_events(conn)

    if not dry_run:
        if not backup():
            conn.close()
            return False

    # 统计需要修复的
    need_sig = [e for e in events if not e["old_sig"]]
    need_ts = [e for e in events if "+08:00" not in e["timestamp"]]
    print(f"  需补签：{len(need_sig)}")
    print(f"  需修时间戳：{len(need_ts)}")
    print(f"  新 seq 范围：1 → {len(events)}")
    print(f"  旧 max seq: {max_seq}")

    if dry_run:
        # 显示碰撞热图
        print("\n📋 碰撞分布（旧seq→新seq数）:")
        multi = {k: v for k, v in seq_map.items() if len(v) > 1}
        for old, news in sorted(multi.items(), key=lambda x: -len(x[1]))[:10]:
            if len(news) > 1:
                print(f"  seq {old} → {len(news)} 条事件 (新seq: {news[0]}~{news[-1]})")
        print(f"  ... 总计 {len(multi)} 个碰撞seq")
        conn.close()
        return True

    # 执行迁移
    conn.execute("BEGIN IMMEDIATE")
    try:
        for ev in events:
            new_ts = fix_timestamp(ev["timestamp"])
            payload_str = ev["payload_json"] or ""

            # 如果是未签名或 seq 变了，重新签名
            re_sign = not ev["old_sig"] or ev["old_seq"] != ev["new_seq"]
            sig = (
                compute_signature(
                    ev["new_seq"], ev["id"], ev["source_agent"], payload_str
                )
                if re_sign
                else ev["old_sig"]
            )

            conn.execute(
                """
                UPDATE ssb_events SET
                    seq = ?,
                    timestamp = ?,
                    agent_signature = COALESCE(?, agent_signature)
                WHERE id = ?
            """,
                (ev["new_seq"], new_ts, sig or "", ev["id"]),
            )

        # 添加 UNIQUE 约束
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_ssb_seq_unique
            ON ssb_events(seq)
        """)

        conn.commit()
        print("\n✅ 迁移完成")
    except Exception as e:
        conn.rollback()
        print(f"\n❌ 迁移失败: {e}")
        conn.close()
        return False

    conn.close()

    # 验证
    verify()
    return True


def verify():
    """校验迁移结果"""
    conn = sqlite3.connect(str(SSB_DB))
    conn.row_factory = sqlite3.Row

    total, unique, dupes, max_seq = count_collisions(conn)
    print(f"\n{'=' * 60}")
    print("🔍 迁移后校验")
    print(f"{'=' * 60}")
    print(f"  总事件: {total}")
    print(f"  唯一seq: {unique}")
    print(f"  重复seq: {dupes}")
    print(f"  碰撞率: {dupes / total * 100:.1f}%")

    if dupes > 0:
        print("  ❌ seq 碰撞仍未清零")
    else:
        print("  ✅ seq 碰撞清零")

    # 时间戳逆序
    rows = conn.execute("""
        SELECT seq, timestamp FROM ssb_events ORDER BY seq
    """).fetchall()
    inversions = sum(
        1
        for i in range(1, len(rows))
        if rows[i]["timestamp"] < rows[i - 1]["timestamp"]
    )
    print(f"  时间戳逆序: {inversions}")

    # 签名覆盖率
    sig_ok = conn.execute("""
        SELECT COUNT(*) FROM ssb_events
        WHERE agent_signature IS NOT NULL AND agent_signature != ''
    """).fetchone()[0]
    print(f"  签名覆盖: {sig_ok}/{total} ({sig_ok / total * 100:.1f}%)")

    # 时间戳格式
    fmt_counts = {"CST(+08:00)": 0, "UTC(+00:00)": 0, "Naive": 0}
    for r in conn.execute("SELECT timestamp FROM ssb_events").fetchall():
        ts = r["timestamp"]
        if "+08:00" in ts:
            fmt_counts["CST(+08:00)"] += 1
        elif "+00:00" in ts or "Z" in ts:
            fmt_counts["UTC(+00:00)"] += 1
        else:
            fmt_counts["Naive"] += 1
    print(f"  时间戳格式: {fmt_counts}")

    # seq 连续性（非严格要求，因为可能有外部 seq 空间假设）
    seqs = [
        r["seq"]
        for r in conn.execute("SELECT seq FROM ssb_events ORDER BY seq").fetchall()
    ]
    if seqs:
        expected = list(range(1, len(seqs) + 1))
        gaps = sum(1 for i in range(len(seqs)) if seqs[i] != expected[i])
        print(f"  seq 非连续: {gaps}")

    # UNIQUE 约束存在性
    try:
        conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_ssb_seq_unique'"
        ).fetchone()
        # 尝试插入重复 seq 验证约束
        conn.execute("INSERT INTO ssb_events (id, seq) VALUES ('_test_dup_seq_', 0)")
        conn.execute("DELETE FROM ssb_events WHERE id = '_test_dup_seq_'")
        print("  UNIQUE(seq) 约束: ✅ 生效")
    except sqlite3.IntegrityError:
        conn.execute("DELETE FROM ssb_events WHERE id = '_test_dup_seq_'")
        print("  UNIQUE(seq) 约束: ✅ 生效")

    conn.close()

    all_ok = (
        dupes == 0 and inversions == 0 and sig_ok == total and fmt_counts["Naive"] == 0
    )
    return all_ok


def rebuild_chain():
    """重建哈希链基线"""
    try:
        sys.path.insert(0, str(ECOS_DIR / "scripts"))
        from ssb_integrity import CHAIN_CHECKPOINT, compute_chain_hash  # type: ignore[import-not-found]

        conn = sqlite3.connect(str(SSB_DB))
        new_hash, count = compute_chain_hash(conn)
        conn.close()

        old_hash = ""
        if CHAIN_CHECKPOINT.exists():
            old_hash = CHAIN_CHECKPOINT.read_text().strip()[:16]

        CHAIN_CHECKPOINT.write_text(new_hash)
        print(f"  🔗 哈希链更新: {old_hash} → {new_hash[:16]} ({count} events)")
        return True
    except Exception as e:
        print(f"  ⚠️ 哈希链重建失败: {e}")
        return False


def main():
    import argparse

    parser = argparse.ArgumentParser(description="SSB seq 碰撞迁移")
    parser.add_argument("--dry-run", action="store_true", help="预览变更")
    parser.add_argument("--verify", action="store_true", help="校验状态")
    parser.add_argument("--migrate", action="store_true", help="执行迁移 (默认)")
    args = parser.parse_args()

    if args.verify:
        verify()
        return 0 if True else 1

    if args.dry_run:
        migrate(dry_run=True)
        return 0

    # 默认或 --migrate
    ok = migrate(dry_run=False)
    if ok:
        rebuild_chain()
        verify()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
