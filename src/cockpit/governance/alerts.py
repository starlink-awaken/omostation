"""治理告警消息处理"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class AlertHandler:
    """告警消息处理器"""

    def __init__(self, log_path: str | Path | None = None):
        self.log_path = Path(log_path) if log_path else Path("/tmp/governance-alerts.log")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def handle(self, alert: dict[str, Any]) -> bool:
        """处理告警"""
        try:
            # 添加时间戳
            alert["timestamp"] = datetime.now(UTC).isoformat()

            # 写入日志
            with open(self.log_path, "a") as f:
                f.write(json.dumps(alert) + "\n")

            return True
        except Exception:  # defensive fallback  # noqa: BLE001
            return False

    def get_recent_alerts(self, limit: int = 10) -> list[dict]:
        """获取最近的告警"""
        try:
            if not self.log_path.exists():
                return []

            with open(self.log_path) as f:
                lines = f.readlines()

            alerts = []
            for line in lines[-limit:]:
                line = line.strip()
                if line:
                    try:
                        alerts.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

            return alerts
        except Exception:  # defensive fallback  # noqa: BLE001
            return []

    def clear_alerts(self) -> bool:
        """清空告警日志"""
        try:
            if self.log_path.exists():
                self.log_path.unlink()
            return True
        except Exception:  # defensive fallback  # noqa: BLE001
            return False


class NotificationChannel:
    """通知渠道"""

    @staticmethod
    def log(alert: dict[str, Any]) -> bool:
        """日志通知"""
        handler = AlertHandler()
        return handler.handle(alert)

    @staticmethod
    def console(alert: dict[str, Any]) -> bool:
        """控制台输出"""
        severity = alert.get("severity", "info")
        message = alert.get("message", "")
        dimension = alert.get("dimension", "")

        if severity == "critical":
            print(f"🔴 CRITICAL [{dimension}]: {message}")
        elif severity == "high":
            print(f"🟠 HIGH [{dimension}]: {message}")
        elif severity == "medium":
            print(f"🟡 MEDIUM [{dimension}]: {message}")
        else:
            print(f"🟢 LOW [{dimension}]: {message}")

        return True

    @staticmethod
    def send(alert: dict[str, Any], channels: list[str] | None = None) -> dict[str, bool]:
        """发送告警到多个渠道"""
        if channels is None:
            channels = ["log", "console"]

        results = {}
        for channel in channels:
            if channel == "log":
                results["log"] = NotificationChannel.log(alert)
            elif channel == "console":
                results["console"] = NotificationChannel.console(alert)

        return results
