from __future__ import annotations

# ruff: noqa: RUF001
import logging
import os
import sqlite3
from pathlib import Path

_log = logging.getLogger(__name__)


def _get_default_db_path() -> Path:
    """Resolve database path for economy seed."""
    return Path(
        os.environ.get(
            "BOS_ECONOMY_DB",
            str(Path.home() / ".bos" / "data" / "economy" / "metabolic.db"),
        )
    )


class EnergyLedger:
    def __init__(self) -> None:
        self.db_path = _get_default_db_path()
        self._init_db()

    def validate_internal_state(self) -> bool:
        return self.db_path.exists()

    def _init_db(self) -> None:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass  # May fail in test environments with read-only BOS_ROOT
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS eu_balance (id INTEGER PRIMARY KEY, balance REAL)""")

        # 物理注入"原初 EU 启动资金" (代谢冷启动解决)
        c.execute("SELECT COUNT(*) FROM eu_balance")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO eu_balance (id, balance) VALUES (1, 100000.0)")
            _log.info("💥 [Economy] 账本实例化完成，注入原初能量: 100000.0 EU")
        conn.commit()
        conn.close()

    def get_balance(self) -> float:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT balance FROM eu_balance WHERE id=1")
        val = c.fetchone()[0]
        conn.close()
        return val

    def consume(self, amount: float, reason: str) -> bool:
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("UPDATE eu_balance SET balance = balance - ? WHERE id=1", (amount,))
        conn.commit()
        conn.close()
        _log.info("[Economy] Consumed %.2f EU -> %s", amount, reason)
        return True


try:
    Ledger: EnergyLedger | None = EnergyLedger()
except (sqlite3.Error, OSError, ValueError):
    Ledger = None
