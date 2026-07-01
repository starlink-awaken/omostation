#!/usr/bin/env python3
"""OMO SelfHealingEngine Trend — 事件趋势分析拆分 (P110-D).

TASK-F7114ABA (omo lint god-module 800L 硬规则).
omo_self_healing.py 810L 拆分: EventTrend + TrendTracker (~52L) 独立到本模块,
omo_self_healing.py 降至 758L (<800L 阈值).

业务 (2 classes): EventTrend + TrendTracker
- EventTrend: 事件趋势快照 (timestamp, total_events, events_by_type, triggers, fixes, debts)
- TrendTracker: 追踪 10 个快照点, 提供 get_trends() / get_summary() 接口.

模式: 新模块 import 业务 (EventTrend 跨模块引用, lazy import 解决循环).
保持 `from omo.omo_self_healing import EventTrend, TrendTracker` 仍可用.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime

__all__ = ["EventTrend", "TrendTracker"]


@dataclass
class EventTrend:
    """事件趋势快照。"""

    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    total_events: int = 0
    events_by_type: dict[str, int] = field(default_factory=dict)
    triggers: int = 0
    fixes: int = 0
    debts: int = 0


class TrendTracker:
    """追踪事件趋势 (10 个快照点)。"""

    def __init__(self, max_snapshots: int = 10):
        self._snapshots: deque[EventTrend] = deque(maxlen=max_snapshots)
        self._total_triggers: int = 0
        self._total_fixes: int = 0
        self._total_debts: int = 0

    def record(self, trend: EventTrend) -> None:
        self._snapshots.append(trend)
        self._total_triggers += trend.triggers
        self._total_fixes += trend.fixes
        self._total_debts += trend.debts

    def get_trends(self) -> list[dict]:
        return [
            {
                "ts": t.timestamp,
                "total_events": t.total_events,
                "events": dict(t.events_by_type),
                "events_by_type": dict(t.events_by_type),
                "triggers": t.triggers,
                "fixes": t.fixes,
                "debts": t.debts,
            }
            for t in self._snapshots
        ]

    def is_escalating(self, event_type: str) -> bool:
        """Check if a specific event type is trending upward (>=3 snapshots, strictly increasing)."""
        snapshots = list(self._snapshots)
        if len(snapshots) < 3:
            return False
        values = [s.events_by_type.get(event_type, 0) for s in snapshots[-3:]]
        return values[0] < values[1] < values[2]

    def get_summary(self) -> dict:
        return {
            "total_triggers": self._total_triggers,
            "total_fixes": self._total_fixes,
            "total_debts": self._total_debts,
            "snapshot_count": len(self._snapshots),
        }

    def reset(self) -> None:
        """清空所有累计计数 (用于测试隔离)."""
        self._snapshots.clear()
        self._total_triggers = 0
        self._total_fixes = 0
        self._total_debts = 0
