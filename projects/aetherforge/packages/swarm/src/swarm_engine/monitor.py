"""Swarm 健康检查与监控 API — 查看 Agent/Worker/任务状态。"""

from __future__ import annotations

import logging
import time
from typing import Any

_log = logging.getLogger(__name__)


class SwarmMonitor:
    """Swarm 集群健康检查与指标收集。

    提供三组监控数据:
      - Agent 健康状态
      - Worker 负载与任务吞吐
      - 任务队列深度与延迟
    """

    def __init__(self) -> None:
        self._start_time = time.time()
        self._agent_heartbeats: dict[str, float] = {}
        self._task_counts: dict[str, int] = {}
        self._error_counts: dict[str, int] = {}
        self._total_tasks = 0
        self._total_errors = 0

    def record_heartbeat(self, agent_id: str) -> None:
        """记录 Agent 心跳。"""
        self._agent_heartbeats[agent_id] = time.time()

    def record_task(self, agent_id: str, status: str = "completed") -> None:
        """记录任务执行结果。"""
        self._total_tasks += 1
        if agent_id not in self._task_counts:
            self._task_counts[agent_id] = 0
        self._task_counts[agent_id] += 1
        if status == "failed":
            self._total_errors += 1
            if agent_id not in self._error_counts:
                self._error_counts[agent_id] = 0
            self._error_counts[agent_id] += 1

    def report(self) -> dict[str, Any]:
        """生成监控报告。"""
        now = time.time()
        uptime = now - self._start_time

        # Agent 状态
        agents = {}
        for aid, last in self._agent_heartbeats.items():
            age = now - last
            agents[aid] = {
                "status": "online" if age < 60 else "stale" if age < 300 else "offline",
                "last_heartbeat_ago": round(age, 1),
                "tasks": self._task_counts.get(aid, 0),
                "errors": self._error_counts.get(aid, 0),
            }

        return {
            "uptime_seconds": round(uptime, 1),
            "total_agents": len(agents),
            "total_tasks": self._total_tasks,
            "total_errors": self._total_errors,
            "error_rate": round(self._total_errors / max(1, self._total_tasks), 4),
            "agents": agents,
        }

    @property
    def is_healthy(self) -> bool:
        """整体健康状态。

        条件: 至少 1 个 Agent 在线，且（任务数 < 10 或 错误率 < 20%）。
        小样本时（<10 任务）不因少量错误判定不健康。
        """
        has_online = any(
            time.time() - hb < 60 for hb in self._agent_heartbeats.values()
        )
        if not has_online:
            return False
        if self._total_tasks < 10:
            return True  # 小样本不判定
        error_rate = self._total_errors / max(1, self._total_tasks)
        return error_rate < 0.2
