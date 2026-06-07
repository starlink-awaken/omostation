#!/usr/bin/env python3
"""
eCOS v5 X2 — CARDS↔STATE 一致性校验器
========================================
Phase X2 / BKL-013 / DEBT-X-005
对比各域 STATE.md 中的 CARDS 指针与 cards.db 实际状态，检测漂移。

用法:
    python3 check-cards-state-consistency.py --db <cards.db路径> --vault <Documents路径>

输出:
    - 标准模式: 不一致 diff 报告
    - --json: 结构化输出

依赖:
    - cards.db (SQLite)
    - 各域 STATE.md (Markdown)
    - sqlite3 Python 模块 (内置)

退出码:
    0 = 全部一致
    1 = 存在不一致
    2 = 数据库不可读
"""

import sys
import json
import sqlite3
import argparse
import re
from datetime import datetime
from pathlib import Path


# 域 → STATE.md 路径映射 (相对于 vault 根) · v2.2 KEMS标准化
DOMAIN_STATE_MAP = {
    "驾驶舱": "@驾驶舱/_control/DASHBOARD.md",
    "学习进化": "@学习进化/_control/STATE.md",
    "个人": "@个人/_control/STATE.md",
    "公共": "@公共/CLAUDE.md",
    "卫健委": "@工作文档/卫健委/_control/STATE.md",
    "国转中心": "@工作文档/国转中心/_control/STATE.md",
    "家庭生活": "@家庭生活/_control/STATE.md",
}


def read_cards_status(db_path: str) -> dict[str, dict]:
    """从 cards.db 读取所有非终态卡片的状态"""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, title, status, domain, updated_at
        FROM cards
        WHERE status NOT IN ('done','resolved','discarded','archived','superseded','cancelled')
        ORDER BY domain, status
    """)

    cards = {}
    for row in cursor.fetchall():
        cards[row["id"]] = {
            "title": row["title"],
            "status": row["status"],
            "domain": row["domain"],
            "updated_at": row["updated_at"],
        }

    conn.close()
    return cards


def find_state_references(state_path: str) -> list[dict]:
    """从 STATE.md 中提取 CARDS 引用"""
    if not Path(state_path).exists():
        return []

    refs = []
    with open(state_path, "r") as f:
        content = f.read()

    # 匹配模式: CARDS domain 引用、任务ID引用
    # 例: "CARDS: 3 活跃"、"[TASK-xxx]"、domain 字段
    patterns = [
        (r'CARDS[：:]\s*(\d+)', "count"),
        (r'domain[：:]\s*["\']?(\w+)', "domain"),
    ]

    for pattern, ref_type in patterns:
        for match in re.finditer(pattern, content):
            refs.append({
                "type": ref_type,
                "value": match.group(1),
                "line": content[:match.start()].count("\n") + 1,
            })

    return refs


def check_consistency(cards: dict, vault_root: str) -> dict:
    """执行一致性检查"""
    results = {
        "checked_at": datetime.now().isoformat(),
        "total_cards": len(cards),
        "domains_checked": 0,
        "inconsistencies": [],
    }

    # 按域分组卡片
    by_domain = {}
    for card_id, card in cards.items():
        domain = card["domain"] or "unknown"
        if domain not in by_domain:
            by_domain[domain] = []
        by_domain[domain].append(card)

    # 检查每个域的 STATE.md
    for domain, state_relpath in DOMAIN_STATE_MAP.items():
        state_path = Path(vault_root) / state_relpath
        if not state_path.exists():
            results["inconsistencies"].append({
                "domain": domain,
                "type": "missing_state",
                "detail": f"STATE.md 不存在: {state_path}",
            })
            continue

        results["domains_checked"] += 1
        domain_cards = by_domain.get(domain, [])

        # 检查 1: STATE.md 中声明的卡片数 vs 实际活跃卡片数
        refs = find_state_references(str(state_path))
        declared_count = None
        for ref in refs:
            if ref["type"] == "count":
                declared_count = int(ref["value"])

        actual_count = len(domain_cards)
        if declared_count is not None and declared_count != actual_count:
            results["inconsistencies"].append({
                "domain": domain,
                "type": "count_mismatch",
                "declared": declared_count,
                "actual": actual_count,
                "detail": f"STATE.md 声明 {declared_count} 张卡片，实际 {actual_count} 张活跃",
            })

    return results


def format_report(results: dict) -> str:
    """人类可读报告"""
    lines = []
    lines.append("=" * 60)
    lines.append("  eCOS v5 — CARDS↔STATE 一致性检查报告")
    lines.append("=" * 60)
    lines.append(f"  检查时间: {results['checked_at'][:19]}")
    lines.append(f"  活跃卡片: {results['total_cards']}")
    lines.append("")

    if not results["inconsistencies"]:
        lines.append("  ✅ 全部一致 — STATE.md 指针与 CARDS 实际状态无漂移")
    else:
        lines.append(f"  ⚠️  发现 {len(results['inconsistencies'])} 项不一致:")
        lines.append("  " + "-" * 56)
        for inc in results["inconsistencies"]:
            lines.append(f"  [{inc['domain']}] {inc['type']}: {inc['detail']}")

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="eCOS v5 CARDS↔STATE 一致性校验")
    parser.add_argument("--db", required=True, help="cards.db 路径")
    parser.add_argument("--vault", required=True, help="Documents vault 根路径")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"❌ cards.db 不存在: {db_path}", file=sys.stderr)
        sys.exit(2)

    try:
        cards = read_cards_status(str(db_path))
    except Exception as e:
        print(f"❌ 无法读取 cards.db: {e}", file=sys.stderr)
        sys.exit(2)

    results = check_consistency(cards, args.vault)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(format_report(results))

    sys.exit(1 if results["inconsistencies"] else 0)


if __name__ == "__main__":
    main()
