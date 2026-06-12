"""L0 历史存储 — SQLite 实现"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .optimization import (
    HealthSnapshot,
    HistoryAnalyzer,
    Prediction,
    TrendAnalysis,
)


class SQLiteHistoryStore(HistoryAnalyzer):
    """SQLite 历史存储"""
    
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS health_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    health_score REAL,
                    debt_weight REAL,
                    debt_health REAL,
                    resolved_count INTEGER,
                    unresolved_count INTEGER
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON health_snapshots(timestamp)
            """)
    
    def record(self, snapshot: HealthSnapshot) -> None:
        """记录快照"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO health_snapshots 
                (timestamp, health_score, debt_weight, debt_health, resolved_count, unresolved_count)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.timestamp.isoformat(),
                    snapshot.health_score,
                    snapshot.debt_weight,
                    snapshot.debt_health,
                    snapshot.resolved_count,
                    snapshot.unresolved_count,
                ),
            )
    
    def get_snapshots(self, days: int = 30) -> list[HealthSnapshot]:
        """获取最近 N 天的快照"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT timestamp, health_score, debt_weight, debt_health, 
                       resolved_count, unresolved_count
                FROM health_snapshots
                WHERE timestamp >= ?
                ORDER BY timestamp
                """,
                (cutoff.isoformat(),),
            ).fetchall()
        
        return [
            HealthSnapshot(
                timestamp=datetime.fromisoformat(row[0]),
                health_score=row[1],
                debt_weight=row[2],
                debt_health=row[3],
                resolved_count=row[4],
                unresolved_count=row[5],
            )
            for row in rows
        ]
    
    def analyze_trend(self, metric: str, days: int = 30) -> TrendAnalysis:
        """分析趋势"""
        snapshots = self.get_snapshots(days)
        
        if len(snapshots) < 2:
            return TrendAnalysis(
                metric=metric,
                current=0,
                previous=0,
                change=0,
                trend="stable",
            )
        
        current = getattr(snapshots[-1], metric)
        previous = getattr(snapshots[-2], metric)
        change = current - previous
        
        if change > 0.05:
            trend = "improving"
        elif change < -0.05:
            trend = "degrading"
        else:
            trend = "stable"
        
        return TrendAnalysis(
            metric=metric,
            current=current,
            previous=previous,
            change=change,
            trend=trend,
        )
    
    def predict(self, metric: str, days: int = 7) -> list[Prediction]:
        """预测未来"""
        snapshots = self.get_snapshots(30)
        
        if len(snapshots) < 3:
            return []
        
        values = [getattr(s, metric) for s in snapshots]
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        
        numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        slope = numerator / denominator if denominator != 0 else 0
        intercept = y_mean - slope * x_mean
        
        predictions = []
        for i in range(1, days + 1):
            predicted = slope * (n + i - 1) + intercept
            predictions.append(
                Prediction(
                    metric=metric,
                    days=i,
                    predicted_value=min(max(predicted, 0), 100),
                )
            )
        
        return predictions
