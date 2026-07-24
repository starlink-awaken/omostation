"""治理事件总线"""

from __future__ import annotations

from typing import Callable

from .primitives import GovernanceEvent


class GovernanceEventBus:
    """治理事件总线"""

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """订阅事件"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """取消订阅"""
        if event_type in self._handlers:
            self._handlers[event_type].remove(handler)

    def publish(self, event: GovernanceEvent) -> None:
        """发布事件"""
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            handler(event)

    def emit_check_started(self, check_id: str, dimension: str) -> None:
        """发射检查开始事件"""
        self.publish(
            GovernanceEvent(
                event_type="check_started",
                dimension=dimension,
                check_id=check_id,
            )
        )

    def emit_check_completed(self, check_id: str, dimension: str, result) -> None:
        """发射检查完成事件"""
        self.publish(
            GovernanceEvent(
                event_type="check_completed",
                dimension=dimension,
                check_id=check_id,
                result=result,
            )
        )

    def emit_alert_triggered(self, check_id: str, dimension: str, result) -> None:
        """发射告警触发事件"""
        self.publish(
            GovernanceEvent(
                event_type="alert_triggered",
                dimension=dimension,
                check_id=check_id,
                result=result,
            )
        )
