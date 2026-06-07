"""
SSOT Kernel — Performance Monitoring
=====================================
性能监控模块

功能：
1. 实时性能监控
2. 资源使用跟踪
3. 指标收集和聚合
4. 性能数据持久化
"""

import json
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psutil

from ..engine import DerivationReport, RuleEngine
from ..meta_model import DomainConfig


@dataclass
class ResourceSnapshot:
    """资源使用快照"""

    timestamp: str
    cpu_percent: float
    memory_usage_mb: float
    memory_percent: float
    thread_count: int
    open_files: int
    io_read_bytes: int
    io_write_bytes: int

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "timestamp": self.timestamp,
            "cpu_percent": self.cpu_percent,
            "memory_usage_mb": self.memory_usage_mb,
            "memory_percent": self.memory_percent,
            "thread_count": self.thread_count,
            "open_files": self.open_files,
            "io_read_bytes": self.io_read_bytes,
            "io_write_bytes": self.io_write_bytes,
        }


@dataclass
class ExecutionMetrics:
    """执行指标"""

    timestamp: str
    duration_ms: float
    rule_count: int
    entity_count: int
    fact_count: int
    passed_rules: int
    failed_rules: int
    blocked_rules: int
    warn_rules: int
    success: bool

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "rule_count": self.rule_count,
            "entity_count": self.entity_count,
            "fact_count": self.fact_count,
            "passed_rules": self.passed_rules,
            "failed_rules": self.failed_rules,
            "blocked_rules": self.blocked_rules,
            "warn_rules": self.warn_rules,
            "success": self.success,
        }


class ResourceMonitor:
    """
    资源监控器

    功能：
    1. 实时监控CPU、内存、IO使用
    2. 定期收集资源快照
    3. 资源使用趋势分析
    4. 异常资源使用检测
    """

    def __init__(self, sampling_interval: float = 1.0):
        self.sampling_interval = sampling_interval
        self.snapshots: deque = deque(maxlen=1000)
        self.monitoring = False
        self.monitor_thread: threading.Thread | None = None
        self.process = psutil.Process()

        # 资源阈值
        self.thresholds = {
            "cpu_percent": 90.0,
            "memory_mb": 1024.0,
            "memory_percent": 85.0,
        }

    def start(self):
        """启动资源监控"""
        if self.monitoring:
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop(self):
        """停止资源监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)

    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            snapshot = self._collect_snapshot()
            self.snapshots.append(snapshot)

            # 检测异常资源使用
            self._check_anomalies(snapshot)

            time.sleep(self.sampling_interval)

    def _collect_snapshot(self) -> ResourceSnapshot:
        """收集资源快照"""
        try:
            cpu_percent = self.process.cpu_percent()
            memory_info = self.process.memory_info()

            # 获取IO计数器
            io_counters = self.process.io_counters() if hasattr(self.process, "io_counters") else None

            return ResourceSnapshot(
                timestamp=datetime.now().isoformat(),
                cpu_percent=cpu_percent,
                memory_usage_mb=memory_info.rss / 1024 / 1024,
                memory_percent=self.process.memory_percent(),
                thread_count=self.process.num_threads(),
                open_files=len(self.process.open_files()) if hasattr(self.process, "open_files") else 0,
                io_read_bytes=io_counters.read_bytes if io_counters else 0,
                io_write_bytes=io_counters.write_bytes if io_counters else 0,
            )
        except Exception:
            # 如果进程信息获取失败，返回零值快照
            return ResourceSnapshot(
                timestamp=datetime.now().isoformat(),
                cpu_percent=0.0,
                memory_usage_mb=0.0,
                memory_percent=0.0,
                thread_count=0,
                open_files=0,
                io_read_bytes=0,
                io_write_bytes=0,
            )

    def _check_anomalies(self, snapshot: ResourceSnapshot):
        """检测资源异常"""
        anomalies = []

        if snapshot.cpu_percent > self.thresholds["cpu_percent"]:
            anomalies.append(f"CPU使用过高: {snapshot.cpu_percent:.1f}%")

        if snapshot.memory_usage_mb > self.thresholds["memory_mb"]:
            anomalies.append(f"内存使用过高: {snapshot.memory_usage_mb:.1f}MB")

        if snapshot.memory_percent > self.thresholds["memory_percent"]:
            anomalies.append(f"内存占比过高: {snapshot.memory_percent:.1f}%")

        if anomalies:
            print(f"🚨 资源异常检测: {', '.join(anomalies)}")

    def get_current_snapshot(self) -> ResourceSnapshot | None:
        """获取当前快照"""
        return self.snapshots[-1] if self.snapshots else None

    def get_average_usage(self, window: int = 60) -> dict[str, float] | None:
        """获取平均资源使用（最近N秒）"""
        if not self.snapshots:
            return None

        # 计算时间窗口内的快照数量
        target_count = min(len(self.snapshots), int(window / self.sampling_interval))
        recent_snapshots = list(self.snapshots)[-target_count:]

        if not recent_snapshots:
            return None

        return {
            "cpu_percent": sum(s.cpu_percent for s in recent_snapshots) / len(recent_snapshots),
            "memory_usage_mb": sum(s.memory_usage_mb for s in recent_snapshots) / len(recent_snapshots),
            "memory_percent": sum(s.memory_percent for s in recent_snapshots) / len(recent_snapshots),
            "thread_count": sum(s.thread_count for s in recent_snapshots) / len(recent_snapshots),
        }

    def get_peak_usage(self, window: int = 60) -> dict[str, float] | None:
        """获取峰值资源使用（最近N秒）"""
        if not self.snapshots:
            return None

        target_count = min(len(self.snapshots), int(window / self.sampling_interval))
        recent_snapshots = list(self.snapshots)[-target_count:]

        if not recent_snapshots:
            return None

        return {
            "cpu_percent": max(s.cpu_percent for s in recent_snapshots),
            "memory_usage_mb": max(s.memory_usage_mb for s in recent_snapshots),
            "memory_percent": max(s.memory_percent for s in recent_snapshots),
            "thread_count": max(s.thread_count for s in recent_snapshots),
        }

    def export_snapshots(self, filepath: str = "resource_snapshots.json"):
        """导出资源快照"""
        data = [snapshot.to_dict() for snapshot in self.snapshots]

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"📄 资源快照已导出到: {filepath}")


class MetricsCollector:
    """
    指标收集器

    功能：
    1. 收集引擎执行指标
    2. 收集业务指标
    3. 收集质量指标
    4. 统一指标格式
    """

    def collect_engine_metrics(self, engine: RuleEngine) -> dict[str, Any]:
        """收集引擎指标"""
        try:
            pattern_count = len(engine.registry.list_patterns())
        except:  # noqa: E722
            pattern_count = 0

        return {
            "engine": {
                "pattern_count": pattern_count,
                "pattern_types": self._get_pattern_types(engine),
                "registry_size": self._get_registry_size(engine),
            }
        }

    def collect_execution_metrics(self, report: DerivationReport, execution_time_ms: float) -> ExecutionMetrics:
        """收集执行指标"""
        return ExecutionMetrics(
            timestamp=datetime.now().isoformat(),
            duration_ms=execution_time_ms,
            rule_count=report.total_rules,
            entity_count=report.total_rules,  # 简化
            fact_count=report.total_rules,  # 简化
            passed_rules=report.passed,
            failed_rules=report.error,
            blocked_rules=report.blocker,
            warn_rules=report.warn,
            success=report.all_passed,
        )

    def collect_business_metrics(self, domain: DomainConfig) -> dict[str, Any]:
        """收集业务指标"""
        return {
            "business": {
                "entity_count": len(domain.entities),
                "fact_count": len(domain.facts),
                "inference_count": len(domain.inferences),
                "relation_count": len(domain.relations),
                "rule_count": len(domain.rules),
                "domain_size_estimated_mb": self._estimate_domain_size(domain),
            }
        }

    def collect_quality_metrics(self, report: DerivationReport) -> dict[str, Any]:
        """收集质量指标"""
        success_rate = report.passed / report.total_rules if report.total_rules > 0 else 0
        failure_rate = (report.error + report.blocker) / report.total_rules if report.total_rules > 0 else 0

        return {
            "quality": {
                "success_rate": success_rate,
                "failure_rate": failure_rate,
                "warning_rate": report.warn / report.total_rules if report.total_rules > 0 else 0,
                "has_blockers": report.blocker > 0,
                "has_errors": report.error > 0,
                "has_warnings": report.warn > 0,
            }
        }

    def _get_pattern_types(self, engine: RuleEngine) -> list[str]:
        """获取模式类型"""
        try:
            return engine.registry.list_patterns()
        except:  # noqa: E722
            return []

    def _get_registry_size(self, engine: RuleEngine) -> int:
        """获取注册表大小"""
        try:
            return len(engine.registry.list_patterns())
        except:  # noqa: E722
            return 0

    def _estimate_domain_size(self, domain: DomainConfig) -> float:
        """估算领域数据大小（MB）"""
        import sys

        total_size = 0

        # 估算实体大小
        for entity in domain.entities:
            total_size += sys.getsizeof(entity)
            total_size += sys.getsizeof(entity.attributes)

        # 估算事实大小
        for fact in domain.facts:
            total_size += sys.getsizeof(fact)
            total_size += sys.getsizeof(fact.tags)

        # 估算规则大小
        for rule in domain.rules:
            total_size += sys.getsizeof(rule)
            total_size += sys.getsizeof(rule.premises)

        return total_size / 1024 / 1024  # 转换为MB


class PerformanceMonitor:
    """
    综合性能监控器

    功能：
    1. 统一资源监控和指标收集
    2. 执行过程监控
    3. 性能数据聚合
    4. 异常检测和告警
    """

    def __init__(self, enable_resource_monitor: bool = True):
        self.resource_monitor = ResourceMonitor() if enable_resource_monitor else None
        self.metrics_collector = MetricsCollector()
        self.execution_history: list[ExecutionMetrics] = []
        self.callbacks: list[Callable] = []

        # 告警阈值
        self.alert_thresholds = {
            "execution_time_ms": 30000,  # 30秒
            "memory_usage_mb": 1024.0,  # 1GB
            "failure_rate": 0.1,  # 10%失败率
        }

    def start_monitoring(self):
        """开始监控"""
        if self.resource_monitor:
            self.resource_monitor.start()

    def stop_monitoring(self):
        """停止监控"""
        if self.resource_monitor:
            self.resource_monitor.stop()

    def monitor_execution(self, func, *args, **kwargs) -> dict[str, Any]:
        """监控函数执行"""
        self.start_monitoring()

        try:
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            execution_time_ms = (time.perf_counter() - start_time) * 1000

            # 收集执行指标
            execution_metrics = None
            if isinstance(result, DerivationReport):
                execution_metrics = self.metrics_collector.collect_execution_metrics(result, execution_time_ms)
                self.execution_history.append(execution_metrics)

                # 检查告警条件
                self._check_execution_alerts(execution_metrics)

            # 执行回调
            self._execute_callbacks(execution_metrics)

            return {
                "result": result,
                "execution_metrics": execution_metrics,
                "resource_usage": self.resource_monitor.get_average_usage() if self.resource_monitor else None,
            }

        finally:
            self.stop_monitoring()

    def _check_execution_alerts(self, metrics: ExecutionMetrics):
        """检查执行告警"""
        alerts = []

        if metrics.duration_ms > self.alert_thresholds["execution_time_ms"]:
            alerts.append(f"执行时间过长: {metrics.duration_ms / 1000:.1f}s")

        resource_usage = self.resource_monitor.get_average_usage() if self.resource_monitor else None
        if resource_usage and resource_usage.get("memory_usage_mb", 0) > self.alert_thresholds["memory_usage_mb"]:
            alerts.append(f"内存使用过高: {resource_usage['memory_usage_mb']:.1f}MB")

        if metrics.rule_count > 0:
            failure_rate = (metrics.failed_rules + metrics.blocked_rules) / metrics.rule_count
            if failure_rate > self.alert_thresholds["failure_rate"]:
                alerts.append(f"失败率过高: {failure_rate * 100:.1f}%")

        if alerts:
            print(f"🚨 执行告警: {', '.join(alerts)}")

    def register_callback(self, callback: Callable):
        """注册回调函数"""
        self.callbacks.append(callback)

    def _execute_callbacks(self, execution_metrics: ExecutionMetrics | None):
        """执行回调函数"""
        for callback in self.callbacks:
            try:
                callback(execution_metrics)
            except Exception as e:
                print(f"⚠️  回调执行失败: {e}")

    def get_performance_summary(self) -> dict[str, Any]:
        """获取性能摘要"""
        if not self.execution_history:
            return {"status": "no_data"}

        # 计算统计指标
        durations = [m.duration_ms for m in self.execution_history]
        success_rates = [m.passed_rules / m.rule_count if m.rule_count > 0 else 0 for m in self.execution_history]

        return {
            "total_executions": len(self.execution_history),
            "average_duration_ms": sum(durations) / len(durations),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "average_success_rate": sum(success_rates) / len(success_rates),
            "resource_usage": self.resource_monitor.get_average_usage() if self.resource_monitor else None,
        }

    def export_metrics(self, filepath: str = "performance_metrics.json"):
        """导出性能指标"""
        data = {
            "execution_history": [m.to_dict() for m in self.execution_history],
            "performance_summary": self.get_performance_summary(),
            "export_timestamp": datetime.now().isoformat(),
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"📄 性能指标已导出到: {filepath}")

    def reset(self):
        """重置监控数据"""
        self.execution_history.clear()
        if self.resource_monitor:
            self.resource_monitor.snapshots.clear()
