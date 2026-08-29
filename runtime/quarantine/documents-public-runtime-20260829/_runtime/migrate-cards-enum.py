#!/usr/bin/env python3
"""migrate-cards-enum.py — CARDS 状态枚举规范化
====================================================
解决问题: D01 CARDS 状态枚举不规范
  - 当前 14 个不同值:`identified/planned/active/in_progress/done/resolved/discarded/closed/flash/incubated/digest/promoted/publish/published`
  - 应是标准生命周期:`identified/planned/active/in_progress/done/resolved/closed`
  - 异常值: `flash/incubated/digest/promoted/publish/published` → 归一化

落地: @公共/_runtime/migrate-cards-enum.py
用法:
  python3 migrate-cards-enum.py --check   # 只检查
  python3 migrate-cards-enum.py --migrate # 迁移(写入 card_history)
  python3 migrate-cards-enum.py --rollback # 回滚
"""
import sqlite3
import sys
import argparse
from datetime import datetime
from pathlib import Path

DB_PATH = '/Users/xiamingxing/Workspace/data/cards/cards.db'

# 标准生命周期(8 状态)
STANDARD_STATUSES = {
    'identified',  # 已识别
    'planned',     # 已规划
    'active',      # 活跃
    'in_progress', # 进行中
    'done',        # 已完成(未审计)
    'resolved',    # 已解决
    'closed',      # 已关闭
    'discarded',   # 已废弃
}

# 异常值 → 标准值 映射
ABNORMAL_TO_STANDARD = {
    'flash': 'in_progress',      # 灵感闪念 = 进行中
    'incubated': 'in_progress',  # 孵化中 = 进行中
    'digest': 'active',          # 摘要 = 活跃
    'promoted': 'done',          # 已晋升 = 已完成
    'publish': 'done',           # 发布中 = 已完成
    'published': 'resolved',     # 已发布 = 已解决
}


def check_db():
    """检查 DB 中状态分布"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute('SELECT status, COUNT(*) FROM cards GROUP BY status ORDER BY status')
    rows = cur.fetchall()

    print('━' * 60)
    print('  CARDS 状态枚举检查(D01)')
    print('━' * 60)
    print(f'\n  当前状态分布({len(rows)} 个值):\n')

    standard_count = 0
    abnormal_count = 0
    abnormal_list = []

    for status, count in rows:
        if status in STANDARD_STATUSES:
            marker = '🟢'
            standard_count += count
        else:
            marker = '🔴'
            abnormal_count += count
            abnormal_list.append((status, count))
        print(f'    {marker} {status}: {count}')

    total = standard_count + abnormal_count
    print(f'\n  总计:{total} 张')
    print(f'  🟢 标准状态:{standard_count} 张({100*standard_count/total:.1f}%)')
    print(f'  🔴 异常状态:{abnormal_count} 张({100*abnormal_count/total:.1f}%)')

    if abnormal_list:
        print(f'\n  异常状态需迁移:')
        for status, count in abnormal_list:
            target = ABNORMAL_TO_STANDARD.get(status, 'active')
            print(f'    {status} ({count} 张) → {target}')

    conn.close()
    return abnormal_list, abnormal_count, total


def migrate_db():
    """执行迁移"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. 检查 card_history 表是否存在
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='card_history'")
    has_history = cur.fetchone() is not None

    if not has_history:
        # 创建
        cur.execute('''
            CREATE TABLE IF NOT EXISTS card_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id TEXT NOT NULL,
                old_status TEXT,
                new_status TEXT,
                changed_at TEXT NOT NULL,
                changed_by TEXT,
                note TEXT
            )
        ''')
        print('  ✅ 创建 card_history 表')

    # 2. 找出所有异常状态
    abnormal_statuses = list(ABNORMAL_TO_STANDARD.keys())
    placeholders = ','.join('?' * len(abnormal_statuses))
    cur.execute(f'SELECT id, status FROM cards WHERE status IN ({placeholders})', abnormal_statuses)
    rows = cur.fetchall()

    if not rows:
        print('  🟢 无异常状态,无需迁移')
        conn.close()
        return 0

    # 3. 逐个迁移 + 记录历史
    now = datetime.now().isoformat()
    migrated = 0

    for card_id, old_status in rows:
        new_status = ABNORMAL_TO_STANDARD[old_status]
        # 写历史
        cur.execute('''
            INSERT INTO card_history (card_id, old_status, new_status, changed_at, changed_by, note)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (card_id, old_status, new_status, now, 'migrate-cards-enum.py', f'D01 枚举规范化: {old_status} → {new_status}'))
        # 改状态
        cur.execute('UPDATE cards SET status = ? WHERE id = ?', (new_status, card_id))
        migrated += 1

    conn.commit()
    print(f'  ✅ 迁移 {migrated} 张 CARDS')
    print(f'  ✅ 写入 {migrated} 条 card_history 记录')

    # 4. 再检查
    print()
    check_db()

    conn.close()
    return migrated


def rollback_db():
    """回滚(从 card_history 恢复)"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='card_history'")
    if not cur.fetchone():
        print('  ❌ 无 card_history 表,无法回滚')
        return 0

    cur.execute("SELECT card_id, old_status, new_status, note FROM card_history WHERE changed_by = 'migrate-cards-enum.py' ORDER BY id DESC")
    rows = cur.fetchall()

    if not rows:
        print('  ❌ 无可回滚的迁移记录')
        return 0

    rolled_back = 0
    for card_id, old_status, new_status, note in rows:
        cur.execute('UPDATE cards SET status = ? WHERE id = ?', (old_status, card_id))
        rolled_back += 1

    # 删除迁移历史
    cur.execute("DELETE FROM card_history WHERE changed_by = 'migrate-cards-enum.py'")

    conn.commit()
    print(f'  ✅ 回滚 {rolled_back} 张 CARDS')
    conn.close()
    return rolled_back


def main():
    parser = argparse.ArgumentParser(description='CARDS 状态枚举规范化')
    parser.add_argument('--check', action='store_true', help='只检查不修改')
    parser.add_argument('--migrate', action='store_true', help='执行迁移')
    parser.add_argument('--rollback', action='store_true', help='回滚迁移')
    args = parser.parse_args()

    if args.rollback:
        rollback_db()
    elif args.migrate:
        migrate_db()
    else:
        check_db()


if __name__ == '__main__':
    main()
