"""Resource Accounting — track MCP tool call costs and quotas.

Provides a CallRecord dataclass and ResourceAccountDB for SQLite-backed
persistence of tool-call accounting data with WAL mode concurrency.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import structlog

from agora.auth.identity import (  # type: ignore[import-not-found]
    Identity,
    normalize_identity,
)

logger = structlog.get_logger(__name__)

# Default deepseek pricing: input=$0.15/M, output=$0.60/M
DEFAULT_INPUT_RATE_PER_M = 0.15
DEFAULT_OUTPUT_RATE_PER_M = 0.60

DEFAULT_DAILY_QUOTA = 10.0  # default $10/day per caller


@dataclass
class CallRecord:
    """A record of a single MCP tool call with resource usage."""

    caller_id: str
    service_name: str
    tool_name: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    billed_to: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @classmethod
    def from_identity(
        cls,
        identity: Identity | dict | str,
        *,
        service_name: str,
        tool_name: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        timestamp: str | None = None,
    ) -> CallRecord:
        caller = normalize_identity(identity)
        return cls(
            caller_id=caller.actor,
            service_name=service_name,
            tool_name=tool_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            billed_to=caller.billing_subject,
            timestamp=timestamp or datetime.now(UTC).isoformat(),
        )


def _default_db_path() -> str:
    """Return the default DB path (~/.agora/accounting.db), creating the dir."""
    path = Path.home() / ".agora"
    path.mkdir(parents=True, exist_ok=True)
    return str(path / "accounting.db")


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    input_rate_per_m: float = DEFAULT_INPUT_RATE_PER_M,
    output_rate_per_m: float = DEFAULT_OUTPUT_RATE_PER_M,
) -> float:
    """Estimate cost in USD based on token counts and per-million-token rates.

    Default rates match deepseek pricing:
        input  = $0.15 / million tokens
        output = $0.60 / million tokens
    """
    return (
        input_tokens / 1_000_000 * input_rate_per_m
        + output_tokens / 1_000_000 * output_rate_per_m
    )


# ── 能力市场 P0: 定价解析 (混合三层: 全局默认 + rates.yaml 覆盖) ──────
_PRICING_RATES_PATH: Path | None = None
_PRICING_CACHE: dict[str, tuple[float, float]] | None = None


def _set_pricing_rates_path(path: str | Path) -> None:
    """测试注入: 指定 agora-bos-rates.yaml 路径 (默认自动发现)."""
    global _PRICING_RATES_PATH, _PRICING_CACHE
    _PRICING_RATES_PATH = Path(path)
    _PRICING_CACHE = None


def _find_rates_path() -> Path:
    """定位 agora-bos-rates.yaml (项目默认, 供测试/运行时)."""
    if _PRICING_RATES_PATH is not None:
        return _PRICING_RATES_PATH
    # 自动发现: src/agora/agora-bos-rates.yaml
    here = Path(__file__).resolve().parent
    for cand in (
        here / "agora-bos-rates.yaml",
        here.parent.parent / "etc" / "agora-bos-rates.yaml",
    ):
        if cand.exists():
            return cand
    return here / "agora-bos-rates.yaml"


def resolve_pricing(uri: str) -> tuple[float, float]:
    """解析 URI 的定价 (input_rate_per_m, output_rate_per_m).

    混合三层 (Q5 决策):
    1. 全局默认: deepseek 费率 (DEFAULT_INPUT_RATE_PER_M/DEFAULT_OUTPUT_RATE_PER_M)
    2. rates.yaml routes 的 pricing 覆盖 (最长 prefix 匹配)
    3. (未来) 服务级覆盖

    Returns:
        (input_rate_per_m, output_rate_per_m)
    """
    global _PRICING_CACHE
    if _PRICING_CACHE is None:
        _PRICING_CACHE = {}
        try:
            import yaml

            path = _find_rates_path()
            if path.exists():
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
                for route in data.get("routes", []):
                    pricing = route.get("pricing")
                    if pricing:
                        prefix = route.get("prefix", "")
                        _PRICING_CACHE[prefix] = (
                            float(pricing.get("input_rate_per_m", DEFAULT_INPUT_RATE_PER_M)),
                            float(pricing.get("output_rate_per_m", DEFAULT_OUTPUT_RATE_PER_M)),
                        )
        except Exception:  # defensive: 定价加载失败回退全局默认
            _PRICING_CACHE = {}
    # 最长 prefix 匹配
    best_len = -1
    for prefix, (in_rate, out_rate) in _PRICING_CACHE.items():
        if uri.startswith(prefix) and len(prefix) > best_len:
            best_len = len(prefix)
            best = (in_rate, out_rate)
    if best_len >= 0:
        return best
    return (DEFAULT_INPUT_RATE_PER_M, DEFAULT_OUTPUT_RATE_PER_M)


def _parse_period(period: str) -> datetime:
    """Parse a period string ('day', 'week', 'month') into a cutoff datetime."""
    now = datetime.now(UTC)
    if period == "day":
        return now - timedelta(days=1)
    elif period == "week":
        return now - timedelta(weeks=1)
    elif period == "month":
        return now - timedelta(days=30)
    else:
        # Default to all time
        return datetime.fromtimestamp(0, tz=UTC)


class ResourceAccountDB:
    """SQLite-backed resource accounting database with WAL mode.

    Records MCP tool calls and provides aggregation queries for
    cost tracking and quota management.
    """

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or _default_db_path()
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create the database connection with WAL mode."""
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self):
        """Auto-create the calls table if it doesn't exist."""
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS calls (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                caller_id   TEXT NOT NULL,
                service_name TEXT NOT NULL,
                tool_name   TEXT NOT NULL,
                input_tokens  INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cost_usd    REAL DEFAULT 0.0,
                billed_to   TEXT DEFAULT '',
                timestamp   TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_calls_caller_id
            ON calls(caller_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_calls_timestamp
            ON calls(timestamp)
        """)
        conn.commit()

    def record_call(self, call: CallRecord):
        """Insert a new call record into the database."""
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO calls (caller_id, service_name, tool_name,
                               input_tokens, output_tokens, cost_usd,
                               billed_to, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                call.caller_id,
                call.service_name,
                call.tool_name,
                call.input_tokens,
                call.output_tokens,
                call.cost_usd,
                call.billed_to,
                call.timestamp,
            ),
        )
        conn.commit()

    def get_top_callers(self, period: str = "day", limit: int = 10) -> list[dict]:
        """Get top callers by total cost within a period.

        Args:
            period: 'day', 'week', 'month', or 'all'
            limit: Number of top callers to return

        Returns:
            List of dicts with keys: caller_id, total_cost, call_count
        """
        cutoff = _parse_period(period)
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT caller_id,
                   SUM(cost_usd) AS total_cost,
                   COUNT(*)      AS call_count
            FROM calls
            WHERE timestamp >= ?
            GROUP BY caller_id
            ORDER BY total_cost DESC
            LIMIT ?
            """,
            (cutoff.isoformat(), limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_report(self, period: str = "day") -> dict:
        """Generate a summary report for a period.

        Args:
            period: 'day', 'week', 'month', or 'all'

        Returns:
            Dict with: total_calls, total_cost, unique_callers,
                       avg_cost_per_call, by_service (list)
        """
        cutoff = _parse_period(period)
        conn = self._get_conn()

        total_row = conn.execute(
            """
            SELECT COUNT(*) AS total_calls,
                   COALESCE(SUM(cost_usd), 0.0) AS total_cost,
                   COUNT(DISTINCT caller_id) AS unique_callers
            FROM calls
            WHERE timestamp >= ?
            """,
            (cutoff.isoformat(),),
        ).fetchone()

        by_service = conn.execute(
            """
            SELECT service_name,
                   COUNT(*) AS call_count,
                   COALESCE(SUM(cost_usd), 0.0) AS total_cost,
                   COALESCE(SUM(input_tokens), 0) AS total_input_tokens,
                   COALESCE(SUM(output_tokens), 0) AS total_output_tokens
            FROM calls
            WHERE timestamp >= ?
            GROUP BY service_name
            ORDER BY total_cost DESC
            """,
            (cutoff.isoformat(),),
        ).fetchall()

        total = dict(total_row)
        total["by_service"] = [dict(r) for r in by_service]
        total["period"] = period
        total["avg_cost_per_call"] = (
            round(total["total_cost"] / total["total_calls"], 6)
            if total["total_calls"] > 0
            else 0.0
        )
        return total

    def get_quota(self, caller_id: str) -> dict:
        """Get the total cost for a caller (all time) and today.

        Returns:
            Dict with: caller_id, total_cost, today_cost
        """
        conn = self._get_conn()
        today_start = (
            datetime.now(UTC)
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .isoformat()
        )

        total = conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0.0) AS total_cost FROM calls WHERE caller_id = ?",
            (caller_id,),
        ).fetchone()

        today = conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0.0) AS today_cost FROM calls WHERE caller_id = ? AND timestamp >= ?",
            (caller_id, today_start),
        ).fetchone()

        return {
            "caller_id": caller_id,
            "total_cost": round(float(total["total_cost"]), 6),
            "today_cost": round(float(today["today_cost"]), 6),
        }

    @property
    def db_path(self) -> str:
        return self._db_path

    def close(self):
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
