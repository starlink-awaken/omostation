"""
Minerva Business Metrics Collector

采集和分析Minerva的业务指标，包括：
- 研究成功率
- Pipeline完成率
- 用户活跃度
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ResearchMetrics:
    """研究指标数据结构"""

    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    recent_attempts: list[dict[str, Any]] = field(default_factory=list)
    top_errors: list[dict[str, Any]] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """研究成功率"""
        if self.total_attempts == 0:
            return 0.0
        return (self.successful_attempts / self.total_attempts) * 100


@dataclass
class PipelineMetrics:
    """Pipeline指标数据结构"""

    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_duration: float = 0.0
    recent_executions: list[dict[str, Any]] = field(default_factory=list)

    @property
    def completion_rate(self) -> float:
        """Pipeline完成率"""
        if self.total_executions == 0:
            return 0.0
        return (self.successful_executions / self.total_executions) * 100

    @property
    def average_duration(self) -> float:
        """平均执行时间（秒）"""
        if self.total_executions == 0:
            return 0.0
        return self.total_duration / self.total_executions


class BusinessMetricsCollector:
    """Minerva业务指标采集器"""

    def __init__(self, storage_path: str | None = None) -> None:
        """
        初始化指标采集器

        Args:
            storage_path: 指标数据存储路径
        """
        self.storage_path = Path(storage_path or Path.home() / ".minerva" / "metrics")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # 加载已有指标
        self.research_metrics = self._load_metrics("research.json", ResearchMetrics())
        self.pipeline_metrics = self._load_metrics("pipeline.json", PipelineMetrics())

    def _load_metrics(self, filename: str, default_class: Any) -> Any:
        """从文件加载指标数据"""
        filepath = self.storage_path / filename
        if filepath.exists():
            try:
                with open(filepath) as f:
                    data = json.load(f)
                    # 将字典转换为数据类
                    if isinstance(default_class, ResearchMetrics):
                        return ResearchMetrics(**data)
                    elif isinstance(default_class, PipelineMetrics):
                        return PipelineMetrics(**data)
                    else:
                        return default_class
            except Exception as e:
                logger.warning("metrics_load_failed: path=%s, error=%s", str(filepath), str(e))
                return default_class
        return default_class

    def _save_metrics(self, filename: str, metrics: Any) -> None:
        """保存指标数据到文件"""
        filepath = self.storage_path / filename
        try:
            # 将数据类转换为字典
            data = metrics.__dict__ if hasattr(metrics, "__dict__") else metrics

            with open(filepath, "w") as f:
                json.dump(data, f, indent=2, default=str)

            logger.debug("metrics_saved: path=%s", str(filepath))
        except Exception as e:
            logger.error("metrics_save_failed: path=%s, error=%s", str(filepath), str(e))

    def record_research_attempt(
        self, success: bool, error: str | None = None, query: str | None = None, level: str = "unknown"
    ) -> None:
        """
        记录研究尝试

        Args:
            success: 是否成功
            error: 错误信息（如果失败）
            query: 研究查询
            level: 研究级别
        """
        self.research_metrics.total_attempts += 1

        if success:
            self.research_metrics.successful_attempts += 1
        else:
            self.research_metrics.failed_attempts += 1

        # 记录最近尝试
        attempt = {"timestamp": datetime.now().isoformat(), "success": success, "query": query, "level": level}

        if error:
            attempt["error"] = error

        self.research_metrics.recent_attempts.append(attempt)

        # 保留最近1000次尝试
        if len(self.research_metrics.recent_attempts) > 1000:
            self.research_metrics.recent_attempts.pop(0)

        # 更新错误统计
        if error:
            self._update_error_statistics(error)

        # 保存指标
        self._save_metrics("research.json", self.research_metrics)

    def record_pipeline_execution(self, pipeline_name: str, steps: list[dict[str, Any]], completed: bool) -> None:
        """
        记录Pipeline执行

        Args:
            pipeline_name: Pipeline名称
            steps: 执行步骤列表
            completed: 是否完成
        """
        self.pipeline_metrics.total_executions += 1

        if completed:
            self.pipeline_metrics.successful_executions += 1
        else:
            self.pipeline_metrics.failed_executions += 1

        # 计算总执行时间
        total_duration = sum(step.get("duration", 0) for step in steps)
        self.pipeline_metrics.total_duration += total_duration

        # 记录最近执行
        execution = {
            "timestamp": datetime.now().isoformat(),
            "pipeline_name": pipeline_name,
            "completed": completed,
            "steps": steps,
            "total_duration": total_duration,
        }

        self.pipeline_metrics.recent_executions.append(execution)

        # 保留最近1000次执行
        if len(self.pipeline_metrics.recent_executions) > 1000:
            self.pipeline_metrics.recent_executions.pop(0)

        # 保存指标
        self._save_metrics("pipeline.json", self.pipeline_metrics)

    def _update_error_statistics(self, error: str) -> None:
        """更新错误统计"""
        # 查找或创建错误统计
        for error_stat in self.research_metrics.top_errors:
            if error_stat["error"] == error:
                error_stat["count"] += 1
                error_stat["last_seen"] = datetime.now().isoformat()
                return

        # 新错误
        self.research_metrics.top_errors.append(
            {
                "error": error,
                "count": 1,
                "first_seen": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat(),
            }
        )

        # 保留前10个错误
        self.research_metrics.top_errors = sorted(
            self.research_metrics.top_errors, key=lambda x: x["count"], reverse=True
        )[:10]

    def get_research_success_rate(self, hours: int = 24) -> float:
        """
        获取最近N小时的研究成功率

        Args:
            hours: 小时数

        Returns:
            成功率 (0-100)
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_attempts = [
            attempt
            for attempt in self.research_metrics.recent_attempts
            if datetime.fromisoformat(attempt["timestamp"]) > cutoff
        ]

        if not recent_attempts:
            return 0.0

        successful = len([attempt for attempt in recent_attempts if attempt["success"]])

        return (successful / len(recent_attempts)) * 100

    def get_pipeline_completion_rate(self, pipeline_name: str | None = None) -> float:
        """
        获取Pipeline完成率

        Args:
            pipeline_name: Pipeline名称（可选）

        Returns:
            完成率 (0-100)
        """
        recent_executions = (
            [exec for exec in self.pipeline_metrics.recent_executions if exec["pipeline_name"] == pipeline_name]
            if pipeline_name
            else self.pipeline_metrics.recent_executions
        )

        if not recent_executions:
            return 0.0

        completed = len([exec for exec in recent_executions if exec["completed"]])
        return (completed / len(recent_executions)) * 100

    def get_research_trend(self, hours: int = 24) -> dict[str, Any]:
        """
        获取研究趋势

        Args:
            hours: 小时数

        Returns:
            趋势数据
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_attempts = [
            attempt
            for attempt in self.research_metrics.recent_attempts
            if datetime.fromisoformat(attempt["timestamp"]) > cutoff
        ]

        if not recent_attempts:
            return {"rate": 0.0, "trend": "stable", "sample_count": 0}

        successful = len([attempt for attempt in recent_attempts if attempt["success"]])
        rate = (successful / len(recent_attempts)) * 100

        # 计算趋势
        mid = len(recent_attempts) // 2
        first_half = recent_attempts[:mid]
        second_half = recent_attempts[mid:]

        first_half_rate = (
            (len([attempt for attempt in first_half if attempt["success"]]) / len(first_half) * 100)
            if first_half
            else 0.0
        )

        second_half_rate = (
            (len([attempt for attempt in second_half if attempt["success"]]) / len(second_half) * 100)
            if second_half
            else 0.0
        )

        # 趋势判断
        if second_half_rate > first_half_rate + 5:
            trend = "up"
        elif second_half_rate < first_half_rate - 5:
            trend = "down"
        else:
            trend = "stable"

        return {
            "rate": rate,
            "trend": trend,
            "first_half_rate": first_half_rate,
            "second_half_rate": second_half_rate,
            "sample_count": len(recent_attempts),
        }

    def get_top_errors(self, limit: int = 5) -> list[dict[str, Any]]:
        """
        获取最常见的错误

        Args:
            limit: 返回数量限制

        Returns:
            错误统计列表
        """
        return sorted(self.research_metrics.top_errors, key=lambda x: x["count"], reverse=True)[:limit]

    def get_all_metrics(self) -> dict[str, Any]:
        """
        获取所有指标

        Returns:
            指标字典
        """
        return {
            "research": {
                "total_attempts": self.research_metrics.total_attempts,
                "successful_attempts": self.research_metrics.successful_attempts,
                "failed_attempts": self.research_metrics.failed_attempts,
                "success_rate": self.research_metrics.success_rate,
                "recent_trend": self.get_research_trend(),
                "top_errors": self.get_top_errors(),
            },
            "pipeline": {
                "total_executions": self.pipeline_metrics.total_executions,
                "successful_executions": self.pipeline_metrics.successful_executions,
                "failed_executions": self.pipeline_metrics.failed_executions,
                "completion_rate": self.pipeline_metrics.completion_rate,
                "average_duration": self.pipeline_metrics.average_duration,
            },
            "timestamp": datetime.now().isoformat(),
        }

    def reset_metrics(self) -> None:
        """重置所有指标（谨慎使用）"""
        self.research_metrics = ResearchMetrics()
        self.pipeline_metrics = PipelineMetrics()

        self._save_metrics("research.json", self.research_metrics)
        self._save_metrics("pipeline.json", self.pipeline_metrics)

        logger.warning("metrics_reset: message=%s", "All metrics have been reset")


# 全局实例
_global_collector: BusinessMetricsCollector | None = None


def get_metrics_collector() -> BusinessMetricsCollector:
    """获取全局指标采集器实例"""
    global _global_collector
    if _global_collector is None:
        _global_collector = BusinessMetricsCollector()
    return _global_collector


# 便捷函数
def record_research_attempt(success: bool, error: str | None = None, **kwargs: Any) -> None:
    """记录研究尝试（便捷函数）"""
    collector = get_metrics_collector()
    collector.record_research_attempt(success, error, **kwargs)


def record_pipeline_execution(pipeline_name: str, steps: list[dict[str, Any]], completed: bool) -> None:
    """记录Pipeline执行（便捷函数）"""
    collector = get_metrics_collector()
    collector.record_pipeline_execution(pipeline_name, steps, completed)


def get_all_metrics() -> dict[str, Any]:
    """获取所有指标（便捷函数）"""
    collector = get_metrics_collector()
    return collector.get_all_metrics()
