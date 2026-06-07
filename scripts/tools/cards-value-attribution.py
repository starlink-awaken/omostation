#!/usr/bin/env python3
"""
eCOS v5 X3 — CARDS 价值归因脚本
==================================
Phase X3 / BKL-015 / DEBT-X-007
读取 cards.db，按域/状态/周期统计价值贡献。

用法:
    python3 cards-value-attribution.py --db <cards.db路径>

输出:
    - 标准模式: 价值归因报告（按域汇总 + 全局摘要）
    - --json: 结构化输出

退出码:
    0 = 成功
    2 = 数据库不可读
"""

import sys
import json
import sqlite3
import argparse
from datetime import datetime, timedelta
from pathlib import Path


def read_cards(db_path: str) -> list[dict]:
    """读取所有卡片"""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    cursor = conn.execute("""
        SELECT id, title, status, domain, priority, created_at, updated_at
        FROM cards
        ORDER BY domain, status
    """)

    cards = []
    for row in cursor.fetchall():
        cards.append({
            "id": row["id"],
            "title": row["title"],
            "status": row["status"],
            "domain": row["domain"] or "unknown",
            "priority": row["priority"] or "medium",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        })

    conn.close()
    return cards


def compute_attribution(cards: list[dict]) -> dict:
    """计算价值归因"""
    now = datetime.now()
    domains = {}
    status_counts = {}
    total_cycle_days = 0
    cards_with_dates = 0

    for card in cards:
        domain = card["domain"]
        status = card["status"]

        # 初始化域统计
        if domain not in domains:
            domains[domain] = {
                "total": 0,
                "active": 0,
                "closed": 0,
                "cycle_days_sum": 0,
                "cycle_count": 0,
                "by_status": {},
                "by_priority": {},
            }

        d = domains[domain]
        d["total"] += 1

        # 按状态
        d["by_status"][status] = d["by_status"].get(status, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1

        # 按优先级
        priority = card["priority"]
        d["by_priority"][priority] = d["by_priority"].get(priority, 0) + 1

        # 活跃 vs 关闭（与 CARDS 校验脚本保持一致）
        CLOSED = {"done", "resolved", "discarded", "archived", "cancelled", "superseded"}
        if status in CLOSED:
            d["closed"] += 1
        else:
            d["active"] += 1

        # 周期计算（仅对已关闭的卡片）
        if card["created_at"] and card["updated_at"] and d["closed"] > 0:
            try:
                created = datetime.fromisoformat(card["created_at"].replace("Z", "+00:00"))
                updated = datetime.fromisoformat(card["updated_at"].replace("Z", "+00:00"))
                cycle_days = (updated - created).days
                if cycle_days >= 0:
                    d["cycle_days_sum"] += cycle_days
                    d["cycle_count"] += 1
                    total_cycle_days += cycle_days
                    cards_with_dates += 1
            except (ValueError, TypeError):
                pass

    # 计算价值得分
    for domain, d in domains.items():
        total = d["total"]
        active = d["active"]
        closed = d["closed"]

        # 关闭率
        close_rate = closed / total if total > 0 else 0

        # 平均周期
        avg_cycle = d["cycle_days_sum"] / d["cycle_count"] if d["cycle_count"] > 0 else None

        # 价值得分 (0-100):
        #   关闭率 40% + 活跃度 30% + 时效性 30%
        close_score = close_rate * 40
        active_score = min(active / 10, 1.0) * 30  # 10 张以上活跃 = 满分
        cycle_score = max(0, (14 - (avg_cycle or 14)) / 14) * 30  # 14 天以下 = 满分

        d["metrics"] = {
            "close_rate": round(close_rate, 3),
            "avg_cycle_days": round(avg_cycle, 1) if avg_cycle else None,
            "value_score": round(close_score + active_score + cycle_score, 1),
        }

    # 终态集合
    CLOSED_STATUSES = {"done", "resolved", "discarded", "archived", "cancelled", "superseded"}

    total_active = sum(d["active"] for d in domains.values())
    total_closed = sum(d["closed"] for d in domains.values())

    return {
        "generated_at": now.isoformat(),
        "total_cards": len(cards),
        "domains": domains,
        "global": {
            "active": total_active,
            "closed": total_closed,
            "avg_cycle_days": round(total_cycle_days / cards_with_dates, 1) if cards_with_dates > 0 else None,
        },
    }


def format_report(result: dict) -> str:
    """人类可读报告"""
    lines = []
    lines.append("=" * 64)
    lines.append("  eCOS v5 — CARDS 价值归因报告")
    lines.append("=" * 64)
    lines.append(f"  生成时间: {result['generated_at'][:19]}")
    lines.append(f"  总卡片数: {result['total_cards']}")
    lines.append(f"  活跃: {result['global']['active']}  关闭: {result['global']['closed']}")
    if result["global"]["avg_cycle_days"]:
        lines.append(f"  全局平均周期: {result['global']['avg_cycle_days']} 天")
    lines.append("")

    # 按域汇总
    lines.append("  按域价值归因:")
    lines.append("  " + "-" * 60)
    lines.append(f"  {'域':12s} {'总数':>4s} {'活跃':>4s} {'关闭率':>6s} {'均周期':>6s} {'价值分':>6s}")
    lines.append("  " + "-" * 60)

    sorted_domains = sorted(
        result["domains"].items(),
        key=lambda x: x[1]["metrics"]["value_score"],
        reverse=True,
    )

    for domain, d in sorted_domains:
        m = d["metrics"]
        cycle_str = f"{m['avg_cycle_days']}d" if m["avg_cycle_days"] else "—"
        score_bar = "█" * int(m["value_score"] / 10) + "░" * (10 - int(m["value_score"] / 10))
        lines.append(
            f"  {domain:12s} {d['total']:4d} {d['active']:4d} "
            f"{m['close_rate']:5.0%}  {cycle_str:>6s}  "
            f"{m['value_score']:5.1f} {score_bar}"
        )

    lines.append("")
    lines.append("=" * 64)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="eCOS v5 CARDS 价值归因")
    parser.add_argument("--db", required=True, help="cards.db 路径")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"❌ cards.db 不存在: {db_path}", file=sys.stderr)
        sys.exit(2)

    try:
        cards = read_cards(str(db_path))
    except Exception as e:
        print(f"❌ 无法读取 cards.db: {e}", file=sys.stderr)
        sys.exit(2)

    result = compute_attribution(cards)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        print(format_report(result))


if __name__ == "__main__":
    main()
