"""KOS Accounting DB — usage.db 创建、写入、查询。

数据库: ~/.kos/accounting/usage.db
"""

import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DB_DIR = Path.home() / ".kos" / "accounting"
DB_PATH = DB_DIR / "usage.db"

# 服务单价 (USD per 1K tokens)
COST_PER_1K = {
    "minerva.research_now": {"input": 0.003, "output": 0.015},
    "kos.search_knowledge": {"input": 0.001, "output": 0.002},
    "kos.semantic_search": {"input": 0.001, "output": 0.002},
    "self.get_profile": {"input": 0.0005, "output": 0.001},
    "self.get_current_role": {"input": 0.0005, "output": 0.001},
    "self.get_vision_summary": {"input": 0.0005, "output": 0.001},
    "collab.create_task": {"input": 0.001, "output": 0.002},
    "collab.list_tasks": {"input": 0.001, "output": 0.002},
    "consensus.create": {"input": 0.001, "output": 0.002},
    "default": {"input": 0.001, "output": 0.003},
}


def _ensure_dir() -> None:
    DB_DIR.mkdir(parents=True, exist_ok=True)


def get_db() -> sqlite3.Connection:
    _ensure_dir()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _ensure_table(conn)
    return conn


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS resource_usage (
            call_id TEXT PRIMARY KEY,
            caller TEXT NOT NULL,
            service TEXT NOT NULL,
            tokens_input INTEGER DEFAULT 0,
            tokens_output INTEGER DEFAULT 0,
            cost_usd REAL DEFAULT 0,
            timestamp TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_usage_caller ON resource_usage(caller);
        CREATE INDEX IF NOT EXISTS idx_usage_service ON resource_usage(service);
        CREATE INDEX IF NOT EXISTS idx_usage_time ON resource_usage(timestamp);
    """)
    conn.commit()


def record_usage(
    caller: str,
    service: str,
    tokens_input: int = 0,
    tokens_output: int = 0,
    cost_usd: float | None = None,
) -> str:
    """记录一次资源消耗。返回call_id。"""
    if cost_usd is None:
        rates = COST_PER_1K.get(service, COST_PER_1K["default"])
        cost_usd = round(
            tokens_input / 1000 * rates["input"] + tokens_output / 1000 * rates["output"],
            6,
        )

    conn = get_db()
    call_id = uuid.uuid4().hex[:12]
    now = datetime.now(UTC).isoformat()
    conn.execute(
        """INSERT INTO resource_usage (call_id, caller, service, tokens_input, tokens_output, cost_usd, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (call_id, caller, service, tokens_input, tokens_output, cost_usd, now),
    )
    conn.commit()
    conn.close()
    return call_id


class CostSummary:
    """成本汇总查询。"""

    @staticmethod
    def by_period(period: str = "today") -> dict[str, Any]:
        """period: today, week, month"""
        conn = get_db()
        now = datetime.now(UTC)
        if period == "today":
            since = now.strftime("%Y-%m-%d")
        elif period == "week":
            since = (now.replace(hour=0, minute=0, second=0) - __import__("datetime").timedelta(days=7)).isoformat()
        elif period == "month":
            since = (now.replace(day=1, hour=0, minute=0, second=0)).isoformat()
        else:
            since = now.strftime("%Y-%m-%d")

        rows = conn.execute(
            "SELECT * FROM resource_usage WHERE timestamp >= ? ORDER BY timestamp DESC",
            (since,),
        ).fetchall()
        conn.close()

        total_tokens = sum(r["tokens_input"] + r["tokens_output"] for r in rows)
        total_cost = round(sum(r["cost_usd"] for r in rows), 4)

        by_service: dict[str, dict] = {}
        by_caller: dict[str, dict] = {}
        for r in rows:
            svc = r["service"]
            clr = r["caller"]
            for bucket, key in [(by_service, svc), (by_caller, clr)]:
                if key not in bucket:
                    bucket[key] = {"tokens": 0, "cost": 0.0, "calls": 0}
                bucket[key]["tokens"] += r["tokens_input"] + r["tokens_output"]
                bucket[key]["cost"] += r["cost_usd"]
                bucket[key]["calls"] += 1

        return {
            "period": period,
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost,
            "total_calls": len(rows),
            "by_service": {k: {**v, "cost": round(v["cost"], 4)} for k, v in sorted(by_service.items())},
            "by_caller": {k: {**v, "cost": round(v["cost"], 4)} for k, v in sorted(by_caller.items())},
        }

    @staticmethod
    def estimate(text_length: int, service: str = "default") -> dict[str, Any]:
        """估算token消耗 (字符数/4 ≈ tokens)。"""
        tokens = max(1, text_length // 4)
        rates = COST_PER_1K.get(service, COST_PER_1K["default"])
        cost = round(tokens / 1000 * rates["output"], 6)
        return {
            "estimated_tokens": tokens,
            "estimated_cost_usd": cost,
            "service": service,
        }
