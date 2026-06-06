"""
Agora Pipeline Metrics Collector

采集和分析Agora Pipeline的业务指标
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PipelineExecution:
    """Pipeline执行记录"""

    name: str
    timestamp: str
    steps: list[dict[str, Any]]
    completed: bool
    total_duration: float


@dataclass
class PipelineMetrics:
    """Pipeline指标数据结构"""

    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_duration: float = 0.0
    recent_executions: list[PipelineExecution] = field(default_factory=list)

    # 按Pipeline名称统计
    pipeline_stats: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def completion_rate(self) -> float:
        """总体完成率"""
        if self.total_executions == 0:
            return 0.0
        return (self.successful_executions / self.total_executions) * 100

    def get_pipeline_completion_rate(self, pipeline_name: str) -> float:
        """获取特定Pipeline的完成率"""
        if pipeline_name not in self.pipeline_stats:
            return 0.0

        stats = self.pipeline_stats[pipeline_name]
        if stats["total"] == 0:
            return 0.0

        return (stats["successful"] / stats["total"]) * 100

    def get_average_duration(self, pipeline_name: str | None = None) -> float:
        """获取平均执行时间"""
        if pipeline_name:
            # 特定Pipeline的平均时间
            if pipeline_name not in self.pipeline_stats:
                return 0.0

            stats = self.pipeline_stats[pipeline_name]
            if stats["total"] == 0:
                return 0.0

            return stats["total_duration"] / stats["total"]
        else:
            # 所有Pipeline的平均时间
            if self.total_executions == 0:
                return 0.0
            return self.total_duration / self.total_executions


class PipelineMetricsCollector:
    """Agora Pipeline指标采集器"""

    def __init__(self, storage_path: str | None = None):
        """
        初始化指标采集器

        Args:
            storage_path: 指标数据存储路径
        """
        path_str = storage_path or str(Path.home() / ".agora" / "metrics")
        self.storage_path = Path(path_str)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # 加载已有指标
        self.metrics = self._load_metrics()

    def _load_metrics(self) -> PipelineMetrics:
        """从文件加载指标数据"""
        filepath = self.storage_path / "pipeline.json"
        if filepath.exists():
            try:
                with open(filepath) as f:
                    data = json.load(f)
                    return PipelineMetrics(**data)
            except Exception as e:
                logger.warning("metrics_load_failed path=%s error=%s", filepath, e)
                return PipelineMetrics()
        return PipelineMetrics()

    def _save_metrics(self) -> None:
        """保存指标数据到文件"""
        filepath = self.storage_path / "pipeline.json"
        try:
            data = self.metrics.__dict__
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2, default=str)

            logger.debug(msg="metrics_saved", extra={"path": str(filepath)})
        except Exception as e:
            logger.error("metrics_save_failed path=%s error=%s", filepath, e)

    def record_pipeline_execution(self, pipeline_name: str, steps: list[dict[str, Any]], completed: bool) -> None:
        """
        记录Pipeline执行

        Args:
            pipeline_name: Pipeline名称
            steps: 执行步骤列表
            completed: 是否完成
        """
        self.metrics.total_executions += 1

        if completed:
            self.metrics.successful_executions += 1
        else:
            self.metrics.failed_executions += 1

        # 计算总执行时间
        total_duration = sum(step.get("duration", 0) for step in steps)
        self.metrics.total_duration += total_duration

        # 记录最近执行
        execution = PipelineExecution(
            name=pipeline_name,
            timestamp=datetime.now().isoformat(),
            steps=steps,
            completed=completed,
            total_duration=total_duration,
        )

        self.metrics.recent_executions.append(execution)

        # 保留最近1000次执行
        if len(self.metrics.recent_executions) > 1000:
            self.metrics.recent_executions.pop(0)

        # 更新Pipeline统计
        if pipeline_name not in self.metrics.pipeline_stats:
            self.metrics.pipeline_stats[pipeline_name] = {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "total_duration": 0.0,
                "first_seen": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat(),
            }

        stats = self.metrics.pipeline_stats[pipeline_name]
        stats["total"] += 1
        stats["last_seen"] = datetime.now().isoformat()

        if completed:
            stats["successful"] += 1
        else:
            stats["failed"] += 1

        stats["total_duration"] += total_duration

        # 保存指标
        self._save_metrics()

    def get_completion_rate(self, pipeline_name: str | None = None) -> float:
        """
        获取完成率

        Args:
            pipeline_name: Pipeline名称（可选）

        Returns:
            完成率 (0-100)
        """
        return self.metrics.get_pipeline_completion_rate(pipeline_name or "")

    def get_average_duration(self, pipeline_name: str | None = None) -> float:
        """
        获取平均执行时间

        Args:
            pipeline_name: Pipeline名称（可选）

        Returns:
            平均执行时间（秒）
        """
        return self.metrics.get_average_duration(pipeline_name)

    def get_recent_executions(self, pipeline_name: str | None = None, limit: int = 10) -> list[PipelineExecution]:
        """
        获取最近的执行记录

        Args:
            pipeline_name: Pipeline名称（可选）
            limit: 返回数量限制

        Returns:
            执行记录列表
        """
        if pipeline_name:
            recent = [exec for exec in self.metrics.recent_executions if exec.name == pipeline_name]
        else:
            recent = self.metrics.recent_executions

        return recent[-limit:]

    def get_pipeline_statistics(self) -> dict[str, dict[str, Any]]:
        """
        获取所有Pipeline的统计信息

        Returns:
            Pipeline统计字典
        """
        return self.metrics.pipeline_stats

    def get_slowest_pipelines(self, limit: int = 5) -> list[dict[str, Any]]:
        """
        获取执行时间最长的Pipeline

        Args:
            limit: 返回数量限制

        Returns:
            Pipeline统计列表（按执行时间降序）
        """
        return sorted(
            [
                {
                    "name": name,
                    "average_duration": stats.get("total_duration", 0) / max(stats.get("total", 1), 1),
                    "total_executions": stats.get("total", 0),
                    "completion_rate": (stats.get("successful", 0) / max(stats.get("total", 1), 1)) * 100,
                }
                for name, stats in self.metrics.pipeline_stats.items()
            ],
            key=lambda x: x["average_duration"],
            reverse=True,
        )[:limit]

    def get_all_metrics(self) -> dict[str, Any]:
        """
        获取所有指标

        Returns:
            指标字典
        """
        return {
            "pipeline": {
                "total_executions": self.metrics.total_executions,
                "successful_executions": self.metrics.successful_executions,
                "failed_executions": self.metrics.failed_executions,
                "completion_rate": self.metrics.completion_rate,
                "average_duration": self.metrics.get_average_duration(),
                "pipeline_statistics": self.metrics.pipeline_stats,
            },
            "recent_executions": [
                {
                    "name": exec.name,
                    "timestamp": exec.timestamp,
                    "completed": exec.completed,
                    "total_duration": exec.total_duration,
                }
                for exec in self.metrics.recent_executions[-10:]  # 最近10次
            ],
            "slowest_pipelines": self.get_slowest_pipelines(),
            "timestamp": datetime.now().isoformat(),
        }

    def reset_metrics(self) -> None:
        """重置所有指标（谨慎使用）"""
        self.metrics = PipelineMetrics()
        self._save_metrics()

        logger.warning("metrics_reset — All pipeline metrics have been reset")


# 全局实例
_global_collector: PipelineMetricsCollector | None = None


def get_pipeline_collector() -> PipelineMetricsCollector:
    """获取全局Pipeline指标采集器实例"""
    global _global_collector
    if _global_collector is None:
        _global_collector = PipelineMetricsCollector()
    return _global_collector


# 便捷函数
def record_execution(pipeline_name: str, steps: list[dict[str, Any]], completed: bool) -> None:
    """记录Pipeline执行（便捷函数）"""
    collector = get_pipeline_collector()
    collector.record_pipeline_execution(pipeline_name, steps, completed)


def get_completion_rate(pipeline_name: str | None = None) -> float:
    """获取完成率（便捷函数）"""
    collector = get_pipeline_collector()
    return collector.get_completion_rate(pipeline_name)


def get_all_pipeline_metrics() -> dict[str, Any]:
    """获取所有Pipeline指标（便捷函数）"""
    collector = get_pipeline_collector()
    return collector.get_all_metrics()
