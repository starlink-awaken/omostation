"""生态市场 — 工具/能力发布与发现 (Phase 12 / T162)

发布 = 注册一个可以对外提供的能力 (工具/API/模型/知识)
发现 = 按能力/成本/评分搜索可用能力
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any

MARKET_DB = Path.home() / ".kos" / "marketplace.db"


class Marketplace:
    """能力市场"""

    def __init__(self):
        self._ensure_schema()

    def _get_conn(self):
        import sqlite3

        return sqlite3.connect(str(MARKET_DB))

    def _ensure_schema(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS offerings (
                offering_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                provider TEXT NOT NULL,
                capability_type TEXT DEFAULT 'tool',
                entry_point TEXT DEFAULT '',
                pricing TEXT DEFAULT '{}',
                rating REAL DEFAULT 0.0,
                usage_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
        conn.close()

    def publish(
        self,
        name: str,
        description: str,
        provider: str,
        capability_type: str = "tool",
        entry_point: str = "",
        pricing: dict[str, Any] | None = None,
    ) -> dict:
        """发布一项能力到市场。"""
        conn = self._get_conn()
        oid = f"offer:{secrets.token_hex(6)}"
        conn.execute(
            "INSERT INTO offerings (offering_id, name, description, provider, capability_type, entry_point, pricing) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                oid,
                name,
                description,
                provider,
                capability_type,
                entry_point,
                json.dumps(pricing or {}),
            ),
        )
        conn.commit()
        conn.close()
        return {"offering_id": oid, "name": name, "status": "published"}

    def search(
        self, query: str, type_filter: str = "", min_rating: float = 0.0
    ) -> list[dict]:
        """搜索市场中的能力。"""
        conn = self._get_conn()
        sql = "SELECT * FROM offerings WHERE status='active' AND (name LIKE ? OR description LIKE ?)"
        params = [f"%{query}%", f"%{query}%"]
        if type_filter:
            sql += " AND capability_type=?"
            params.append(type_filter)
        if min_rating > 0:
            sql += " AND rating>=?"
            params.append(min_rating)
        sql += " ORDER BY rating DESC, usage_count DESC"

        rows = conn.execute(sql, params).fetchall()
        conn.close()
        cols = [
            "offering_id",
            "name",
            "description",
            "provider",
            "capability_type",
            "entry_point",
            "pricing",
            "rating",
            "usage_count",
            "status",
            "created_at",
        ]
        result: list[dict[str, Any]] = []
        for r in rows:
            d: dict[str, Any] = dict(zip(cols, r, strict=True))
            d["pricing"] = json.loads(d["pricing"])
            result.append(d)
        return result

    def subscribe(self, offering_id: str, subscriber: str) -> dict:
        """订阅一项能力 (相当于部署到本地)。"""
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                sub_id INTEGER PRIMARY KEY AUTOINCREMENT,
                offering_id TEXT NOT NULL,
                subscriber TEXT NOT NULL,
                subscribed_at TEXT DEFAULT (datetime('now')),
                active INTEGER DEFAULT 1
            )
        """)
        conn.execute(
            "INSERT INTO subscriptions (offering_id, subscriber) VALUES (?, ?)",
            (offering_id, subscriber),
        )
        conn.commit()
        conn.close()
        return {
            "offering_id": offering_id,
            "subscriber": subscriber,
            "status": "subscribed",
        }


# ─── 跨组织计费 (T163) ───


class CrossOrgBilling:
    """跨组织计费与微支付"""

    def __init__(self):
        self._ensure_schema()

    def _get_conn(self):
        import sqlite3

        return sqlite3.connect(str(MARKET_DB))

    def _ensure_schema(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS billing_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_org TEXT NOT NULL,
                to_org TEXT NOT NULL,
                service TEXT NOT NULL,
                amount REAL DEFAULT 0.0,
                currency TEXT DEFAULT 'credit',
                description TEXT DEFAULT '',
                billed_at TEXT DEFAULT (datetime('now')),
                settled INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

    def record_usage(
        self,
        from_org: str,
        to_org: str,
        service: str,
        amount: float,
        description: str = "",
    ) -> dict:
        """记录一次跨组织调用费用。"""
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO billing_records (from_org, to_org, service, amount, description) VALUES (?, ?, ?, ?, ?)",
            (from_org, to_org, service, amount, description),
        )
        conn.commit()
        conn.close()
        return {"from": from_org, "to": to_org, "amount": amount, "status": "recorded"}

    def get_balance(self, org: str) -> dict:
        """查询组织当前的计费平衡。"""
        conn = self._get_conn()
        due = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM billing_records WHERE from_org=? AND settled=0",
            (org,),
        ).fetchone()[0]
        owed = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM billing_records WHERE to_org=? AND settled=0",
            (org,),
        ).fetchone()[0]
        conn.close()
        return {
            "org": org,
            "due": round(due, 4),
            "owed": round(owed, 4),
            "net": round(owed - due, 4),
        }

    def settle(self, from_org: str, to_org: str) -> dict:
        """结算两个组织之间的未结费用。"""
        conn = self._get_conn()
        conn.execute(
            "UPDATE billing_records SET settled=1 WHERE from_org=? AND to_org=? AND settled=0",
            (from_org, to_org),
        )
        settled_count = conn.execute("SELECT changes()").fetchone()[0]
        conn.commit()
        conn.close()
        return {"from": from_org, "to": to_org, "settled": settled_count}


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "publish":
        m = Marketplace()
        r = m.publish(sys.argv[2], sys.argv[3], sys.argv[4])
        print(f"Published: {r['offering_id']} — {r['name']}")
    elif len(sys.argv) > 1 and sys.argv[1] == "search":
        m = Marketplace()
        for o in m.search(sys.argv[2]):
            print(
                f"  {o['offering_id']:25s} {o['name']:20s} {o['provider']:20s} rate={o['rating']}"
            )
    elif len(sys.argv) > 1 and sys.argv[1] == "bill":
        b = CrossOrgBilling()
        if sys.argv[2] == "record":
            r = b.record_usage(
                sys.argv[3], sys.argv[4], sys.argv[5], float(sys.argv[6])
            )
            print(f"Recorded: {r['status']}")
        elif sys.argv[2] == "balance":
            r = b.get_balance(sys.argv[3])
            print(f"Balance: due=${r['due']} owed=${r['owed']} net=${r['net']}")
