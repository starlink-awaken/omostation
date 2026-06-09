"""
SSOT Kernel — Enhanced Metrics Collectors
==========================================
增强的指标收集器模块

功能：
1. 多维度指标收集
2. 智能数据聚合
3. 自动化数据处理
4. 实时和历史分析
"""

import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import psutil

from ..engine import DerivationReport
from ..meta_model import DomainConfig
from .environment import EnvironmentAwareMonitor, get_environment_manager


@dataclass
class MetricValue:
    """指标值"""

    name: str
    value: float
    timestamp: str
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "name": self.name,
            "value": self.value,
            "timestamp": self.timestamp,
            "tags": self.tags,
            "metadata": self.metadata,
        }


@dataclass
class AggregatedMetric:
    """聚合指标"""

    name: str
    count: int
    min: float
    max: float
    avg: float
    sum: float
    std: float | None = None
    p50: float | None = None
    p95: float | None = None
    p99: float | None = None
    timestamps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "name": self.name,
            "count": self.count,
            "min": self.min,
            "max": self.max,
            "avg": self.avg,
            "sum": self.sum,
            "std": self.std,
            "p50": self.p50,
            "p95": self.p95,
            "p99": self.p99,
            "time_range": {
                "start": self.timestamps[0] if self.timestamps else None,
                "end": self.timestamps[-1] if self.timestamps else None,
            },
        }


class SystemMetricsCollector:
    """系统指标收集器"""

    def __init__(self, monitor: EnvironmentAwareMonitor | None = None):
        self.monitor = monitor or get_environment_manager().get_monitor("default")
        self.process = psutil.Process()
        self.last_io_stats = None

    def collect_all(self) -> list[MetricValue]:
        """收集所有系统指标"""
        metrics = []

        try:
            # CPU指标
            metrics.extend(self._collect_cpu_metrics())

            # 内存指标
            metrics.extend(self._collect_memory_metrics())

            # IO指标
            metrics.extend(self._collect_io_metrics())

            # 线程和进程指标
            metrics.extend(self._collect_process_metrics())

            # 网络指标
            metrics.extend(self._collect_network_metrics())

        except Exception as e:
            print(f"⚠️  系统指标收集失败: {e}")

        return metrics

    def _collect_cpu_metrics(self) -> list[MetricValue]:
        """收集CPU指标"""
        metrics = []

        try:
            cpu_percent = self.process.cpu_percent(interval=0.1)
            cpu_times = self.process.cpu_times()

            metrics.append(
                MetricValue(
                    name="system.cpu_percent",
                    value=cpu_percent,
                    timestamp=datetime.now().isoformat(),
                    tags=self.monitor.create_environment_tag(),
                )
            )

            # CPU时间分解
            metrics.append(
                MetricValue(
                    name="system.cpu_user_time",
                    value=cpu_times.user,
                    timestamp=datetime.now().isoformat(),
                    tags=self.monitor.create_environment_tag(),
                )
            )

            metrics.append(
                MetricValue(
                    name="system.cpu_system_time",
                    value=cpu_times.system,
                    timestamp=datetime.now().isoformat(),
                    tags=self.monitor.create_environment_tag(),
                )
            )

        except Exception as e:
            print(f"⚠️  CPU指标收集失败: {e}")

        return metrics

    def _collect_memory_metrics(self) -> list[MetricValue]:
        """收集内存指标"""
        metrics = []

        try:
            memory_info = self.process.memory_info()
            memory_percent = self.process.memory_percent()

            # RSS内存
            metrics.append(
                MetricValue(
                    name="system.memory_rss_mb",
                    value=memory_info.rss / 1024 / 1024,
                    timestamp=datetime.now().isoformat(),
                    tags=self.monitor.create_environment_tag(),
                )
            )

            # VMS内存
            metrics.append(
                MetricValue(
                    name="system.memory_vms_mb",
                    value=memory_info.vms / 1024 / 1024,
                    timestamp=datetime.now().isoformat(),
                    tags=self.monitor.create_environment_tag(),
                )
            )

            # 内存百分比
            metrics.append(
                MetricValue(
                    name="system.memory_percent",
                    value=memory_percent,
                    timestamp=datetime.now().isoformat(),
                    tags=self.monitor.create_environment_tag(),
                )
            )

        except Exception as e:
            print(f"⚠️  内存指标收集失败: {e}")

        return metrics

    def _collect_io_metrics(self) -> list[MetricValue]:
        """收集IO指标"""
        metrics = []

        try:
            # 检查平台兼容性
            if hasattr(self.process, "io_counters"):
                io_counters = self.process.io_counters()

                # 读取字节数
                metrics.append(
                    MetricValue(
                        name="system.io_read_bytes",
                        value=io_counters.read_bytes,
                        timestamp=datetime.now().isoformat(),
                        tags=self.monitor.create_environment_tag(),
                    )
                )

                # 写入字节数
                metrics.append(
                    MetricValue(
                        name="system.io_write_bytes",
                        value=io_counters.write_bytes,
                        timestamp=datetime.now().isoformat(),
                        tags=self.monitor.create_environment_tag(),
                    )
                )

                # 读写操作数
                metrics.append(
                    MetricValue(
                        name="system.io_read_count",
                        value=io_counters.read_count,
                        timestamp=datetime.now().isoformat(),
                        tags=self.monitor.create_environment_tag(),
                    )
                )

                metrics.append(
                    MetricValue(
                        name="system.io_write_count",
                        value=io_counters.write_count,
                        timestamp=datetime.now().isoformat(),
                        tags=self.monitor.create_environment_tag(),
                    )
                )
            else:
                # 如果不支持io_counters，跳过IO指标
                pass

        except Exception as e:
            print(f"⚠️  IO指标收集失败: {e}")

        return metrics

    def _collect_process_metrics(self) -> list[MetricValue]:
        """收集进程指标"""
        metrics = []

        try:
            # 线程数
            thread_count = self.process.num_threads()
            metrics.append(
                MetricValue(
                    name="system.thread_count",
                    value=thread_count,
                    timestamp=datetime.now().isoformat(),
                    tags=self.monitor.create_environment_tag(),
                )
            )

            # 文件描述符数（Linux/Unix）
            if hasattr(self.process, "num_fds"):
                fd_count = self.process.num_fds()
                metrics.append(
                    MetricValue(
                        name="system.file_descriptor_count",
                        value=fd_count,
                        timestamp=datetime.now().isoformat(),
                        tags=self.monitor.create_environment_tag(),
                    )
                )

            # 连接数
            if hasattr(self.process, "connections"):
                connections = self.process.connections()
                metrics.append(
                    MetricValue(
                        name="system.connection_count",
                        value=len(connections),
                        timestamp=datetime.now().isoformat(),
                        tags=self.monitor.create_environment_tag(),
                    )
                )

        except Exception as e:
            print(f"⚠️  进程指标收集失败: {e}")

        return metrics

    def _collect_network_metrics(self) -> list[MetricValue]:
        """收集网络指标"""
        metrics = []

        try:
            # 系统网络IO
            net_io = psutil.net_io_counters()

            metrics.append(
                MetricValue(
                    name="system.network_bytes_sent",
                    value=net_io.bytes_sent,
                    timestamp=datetime.now().isoformat(),
                    tags=self.monitor.create_environment_tag(),
                )
            )

            metrics.append(
                MetricValue(
                    name="system.network_bytes_recv",
                    value=net_io.bytes_recv,
                    timestamp=datetime.now().isoformat(),
                    tags=self.monitor.create_environment_tag(),
                )
            )

            metrics.append(
                MetricValue(
                    name="system.network_packets_sent",
                    value=net_io.packets_sent,
                    timestamp=datetime.now().isoformat(),
                    tags=self.monitor.create_environment_tag(),
                )
            )

            metrics.append(
                MetricValue(
                    name="system.network_packets_recv",
                    value=net_io.packets_recv,
                    timestamp=datetime.now().isoformat(),
                    tags=self.monitor.create_environment_tag(),
                )
            )

        except Exception as e:
            print(f"⚠️  网络指标收集失败: {e}")

        return metrics


class ExecutionMetricsCollector:
    """执行指标收集器"""

    def __init__(self, monitor: EnvironmentAwareMonitor | None = None):
        self.monitor = monitor or get_environment_manager().get_monitor("default")
        self.execution_history: deque = deque(maxlen=1000)

    def collect(
        self, report: DerivationReport, execution_time_ms: float
    ) -> list[MetricValue]:
        """收集执行指标"""
        metrics = []
        timestamp = datetime.now().isoformat()
        env_tags = self.monitor.create_environment_tag()

        # 基础执行指标
        metrics.append(
            MetricValue(
                name="execution.total_time_ms",
                value=execution_time_ms,
                timestamp=timestamp,
                tags=env_tags,
                metadata={"total_rules": report.total_rules},
            )
        )

        # 规则处理指标
        metrics.append(
            MetricValue(
                name="execution.total_rules",
                value=report.total_rules,
                timestamp=timestamp,
                tags=env_tags,
            )
        )

        metrics.append(
            MetricValue(
                name="execution.passed_rules",
                value=report.passed,
                timestamp=timestamp,
                tags=env_tags,
            )
        )

        metrics.append(
            MetricValue(
                name="execution.failed_rules",
                value=report.error,
                timestamp=timestamp,
                tags=env_tags,
            )
        )

        metrics.append(
            MetricValue(
                name="execution.blocked_rules",
                value=report.blocker,
                timestamp=timestamp,
                tags=env_tags,
            )
        )

        metrics.append(
            MetricValue(
                name="execution.warn_rules",
                value=report.warn,
                timestamp=timestamp,
                tags=env_tags,
            )
        )

        # 计算衍生指标
        if report.total_rules > 0:
            success_rate = report.passed / report.total_rules
            failure_rate = (report.error + report.blocker) / report.total_rules

            metrics.append(
                MetricValue(
                    name="execution.success_rate",
                    value=success_rate,
                    timestamp=timestamp,
                    tags=env_tags,
                )
            )

            metrics.append(
                MetricValue(
                    name="execution.failure_rate",
                    value=failure_rate,
                    timestamp=timestamp,
                    tags=env_tags,
                )
            )

            # 规则吞吐量
            if execution_time_ms > 0:
                throughput = report.total_rules / (execution_time_ms / 1000)
                metrics.append(
                    MetricValue(
                        name="execution.rules_per_second",
                        value=throughput,
                        timestamp=timestamp,
                        tags=env_tags,
                    )
                )

        # 执行状态
        metrics.append(
            MetricValue(
                name="execution.all_passed",
                value=1.0 if report.all_passed else 0.0,
                timestamp=timestamp,
                tags=env_tags,
            )
        )

        # 记录历史
        self.execution_history.append(
            {
                "timestamp": timestamp,
                "report": report,
                "execution_time_ms": execution_time_ms,
                "metrics": [m.to_dict() for m in metrics],
            }
        )

        return metrics

    def get_execution_statistics(self, window_minutes: int = 60) -> dict[str, Any]:
        """获取执行统计信息"""
        cutoff_time = datetime.now() - timedelta(minutes=window_minutes)

        recent_executions = [
            record
            for record in self.execution_history
            if datetime.fromisoformat(record["timestamp"]) >= cutoff_time
        ]

        if not recent_executions:
            return {
                "window_minutes": window_minutes,
                "total_executions": 0,
                "average_time_ms": 0,
                "success_rate": 0,
                "throughput": 0,
            }

        # 计算统计指标
        times = [record["execution_time_ms"] for record in recent_executions]
        success_count = sum(
            1 for record in recent_executions if record["report"].all_passed
        )

        avg_time = statistics.mean(times)
        success_rate = success_count / len(recent_executions)

        total_rules = sum(record["report"].total_rules for record in recent_executions)
        total_time_sec = (
            sum(record["execution_time_ms"] for record in recent_executions) / 1000
        )
        throughput = total_rules / total_time_sec if total_time_sec > 0 else 0

        return {
            "window_minutes": window_minutes,
            "total_executions": len(recent_executions),
            "average_time_ms": avg_time,
            "min_time_ms": min(times),
            "max_time_ms": max(times),
            "success_rate": success_rate,
            "throughput": throughput,
            "success_count": success_count,
            "failure_count": len(recent_executions) - success_count,
        }


class BusinessMetricsCollector:
    """业务指标收集器"""

    def __init__(self, monitor: EnvironmentAwareMonitor | None = None):
        self.monitor = monitor or get_environment_manager().get_monitor("default")

    def collect(self, domain: DomainConfig) -> list[MetricValue]:
        """收集业务指标"""
        metrics = []
        timestamp = datetime.now().isoformat()
        env_tags = self.monitor.create_environment_tag()

        # 实体指标
        metrics.append(
            MetricValue(
                name="business.entity_count",
                value=len(domain.entities),
                timestamp=timestamp,
                tags=env_tags,
            )
        )

        # 事实指标
        metrics.append(
            MetricValue(
                name="business.fact_count",
                value=len(domain.facts),
                timestamp=timestamp,
                tags=env_tags,
            )
        )

        # 规则指标
        metrics.append(
            MetricValue(
                name="business.rule_count",
                value=len(domain.rules),
                timestamp=timestamp,
                tags=env_tags,
            )
        )

        # 推论指标
        metrics.append(
            MetricValue(
                name="business.inference_count",
                value=len(domain.inferences),
                timestamp=timestamp,
                tags=env_tags,
            )
        )

        # 关系指标
        metrics.append(
            MetricValue(
                name="business.relation_count",
                value=len(domain.relations),
                timestamp=timestamp,
                tags=env_tags,
            )
        )

        # 计算复杂度指标
        entity_complexity = self._calculate_entity_complexity(domain.entities)
        metrics.append(
            MetricValue(
                name="business.entity_complexity",
                value=entity_complexity,
                timestamp=timestamp,
                tags=env_tags,
            )
        )

        # 计算关系密度
        relation_density = self._calculate_relation_density(domain)
        metrics.append(
            MetricValue(
                name="business.relation_density",
                value=relation_density,
                timestamp=timestamp,
                tags=env_tags,
            )
        )

        # 估算数据规模
        domain_size_mb = self._estimate_domain_size(domain)
        metrics.append(
            MetricValue(
                name="business.domain_size_mb",
                value=domain_size_mb,
                timestamp=timestamp,
                tags=env_tags,
            )
        )

        return metrics

    def _calculate_entity_complexity(self, entities: list) -> float:
        """计算实体复杂度"""
        if not entities:
            return 0.0

        total_attributes = sum(len(e.attributes) for e in entities)
        return total_attributes / len(entities)

    def _calculate_relation_density(self, domain: DomainConfig) -> float:
        """计算关系密度"""
        entity_count = len(domain.entities)
        relation_count = len(domain.relations)

        if entity_count <= 1:
            return 0.0

        # 理论最大关系数: n*(n-1)
        max_relations = entity_count * (entity_count - 1)

        return relation_count / max_relations if max_relations > 0 else 0.0

    def _estimate_domain_size(self, domain: DomainConfig) -> float:
        """估算领域数据大小（MB）"""
        import sys

        total_size = 0

        # 实体大小
        for entity in domain.entities:
            total_size += sys.getsizeof(entity)
            total_size += sys.getsizeof(entity.attributes)

        # 事实大小
        for fact in domain.facts:
            total_size += sys.getsizeof(fact)
            total_size += sys.getsizeof(fact.tags)

        # 规则大小
        for rule in domain.rules:
            total_size += sys.getsizeof(rule)
            total_size += sys.getsizeof(rule.premises)

        # 推论大小
        for inference in domain.inferences:
            total_size += sys.getsizeof(inference)
            total_size += sys.getsizeof(inference.derives_from)

        return total_size / 1024 / 1024  # 转换为MB


class QualityMetricsCollector:
    """质量指标收集器"""

    def __init__(self, monitor: EnvironmentAwareMonitor | None = None):
        self.monitor = monitor or get_environment_manager().get_monitor("default")

    def collect(self, report: DerivationReport) -> list[MetricValue]:
        """收集质量指标"""
        metrics = []
        timestamp = datetime.now().isoformat()
        env_tags = self.monitor.create_environment_tag()

        # 基础质量指标
        metrics.append(
            MetricValue(
                name="quality.passed_ratio",
                value=report.passed / report.total_rules
                if report.total_rules > 0
                else 0,
                timestamp=timestamp,
                tags=env_tags,
            )
        )

        metrics.append(
            MetricValue(
                name="quality.failed_ratio",
                value=report.error / report.total_rules
                if report.total_rules > 0
                else 0,
                timestamp=timestamp,
                tags=env_tags,
            )
        )

        metrics.append(
            MetricValue(
                name="quality.blocked_ratio",
                value=report.blocker / report.total_rules
                if report.total_rules > 0
                else 0,
                timestamp=timestamp,
                tags=env_tags,
            )
        )

        metrics.append(
            MetricValue(
                name="quality.warn_ratio",
                value=report.warn / report.total_rules if report.total_rules > 0 else 0,
                timestamp=timestamp,
                tags=env_tags,
            )
        )

        # 质量评分
        quality_score = self._calculate_quality_score(report)
        metrics.append(
            MetricValue(
                name="quality.score",
                value=quality_score,
                timestamp=timestamp,
                tags=env_tags,
                metadata={"max_possible": 100.0},
            )
        )

        # 问题严重程度
        severity_score = self._calculate_severity_score(report)
        metrics.append(
            MetricValue(
                name="quality.severity_score",
                value=severity_score,
                timestamp=timestamp,
                tags=env_tags,
                metadata={"higher_is_worse": False},
            )
        )

        return metrics

    def _calculate_quality_score(self, report: DerivationReport) -> float:
        """计算质量得分（0-100）"""
        if report.total_rules == 0:
            return 100.0

        # 基础得分：通过率权重50%
        pass_score = (report.passed / report.total_rules) * 50

        # 惩罚：阻塞和错误有重惩罚
        penalty = (report.blocker * 2 + report.error) / report.total_rules * 10

        # 最终得分
        score = pass_score - penalty
        return max(0, min(100, score))

    def _calculate_severity_score(self, report: DerivationReport) -> float:
        """计算严重程度得分（0-100，越低越好）"""
        if report.total_rules == 0:
            return 0.0

        # 问题加权
        weighted_issues = report.blocker * 3 + report.error * 2 + report.warn * 1

        # 严重程度得分
        severity_score = (weighted_issues / report.total_rules) * 10

        return min(100, severity_score)


class EnhancedMetricsCollector:
    """增强的指标收集器"""

    def __init__(self, monitor: EnvironmentAwareMonitor | None = None):
        self.monitor = monitor or get_environment_manager().get_monitor("default")

        # 专用收集器
        self.system_collector = SystemMetricsCollector(self.monitor)
        self.execution_collector = ExecutionMetricsCollector(self.monitor)
        self.business_collector = BusinessMetricsCollector(self.monitor)
        self.quality_collector = QualityMetricsCollector(self.monitor)

        # 指标缓存
        self.metrics_cache: dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))

        # 聚合数据
        self.aggregated_metrics: dict[str, AggregatedMetric] = {}

    def collect_all(
        self,
        report: DerivationReport | None = None,
        execution_time_ms: float = 0,
        domain: DomainConfig | None = None,
    ) -> dict[str, list[MetricValue]]:
        """收集所有指标"""
        all_metrics = {"system": [], "execution": [], "business": [], "quality": []}

        # 系统指标（始终收集）
        if self.monitor.should_collect():
            system_metrics = self.system_collector.collect_all()
            all_metrics["system"].extend(system_metrics)
            self._cache_metrics("system", system_metrics)

        # 执行指标
        if report:
            if self.monitor.should_collect():
                execution_metrics = self.execution_collector.collect(
                    report, execution_time_ms
                )
                all_metrics["execution"].extend(execution_metrics)
                self._cache_metrics("execution", execution_metrics)

        # 业务指标
        if domain:
            if self.monitor.should_collect():
                business_metrics = self.business_collector.collect(domain)
                all_metrics["business"].extend(business_metrics)
                self._cache_metrics("business", business_metrics)

        # 质量指标
        if report:
            if self.monitor.should_collect():
                quality_metrics = self.quality_collector.collect(report)
                all_metrics["quality"].extend(quality_metrics)
                self._cache_metrics("quality", quality_metrics)

        return all_metrics

    def _cache_metrics(self, category: str, metrics: list[MetricValue]):
        """缓存指标"""
        for metric in metrics:
            key = self.monitor.generate_isolation_key(category, metric.name)
            self.metrics_cache[key].append(metric)

            # 记录到监控器
            self.monitor.record_collection(metric.name, metric.value, metric.tags)

    def aggregate_metrics(
        self, metric_name: str, time_window_minutes: int = 5
    ) -> AggregatedMetric | None:
        """聚合指标"""
        self.monitor.generate_isolation_key("all", metric_name)

        # 从所有分类中查找指标
        all_metrics = []
        for cache_key, cached_metrics in self.metrics_cache.items():
            if metric_name in cache_key:
                cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)
                recent_metrics = [
                    m
                    for m in cached_metrics
                    if datetime.fromisoformat(m.timestamp) >= cutoff_time
                ]
                all_metrics.extend(recent_metrics)

        if not all_metrics:
            return None

        # 提取值和时间戳
        values = [m.value for m in all_metrics]
        timestamps = [m.timestamp for m in all_metrics]

        # 计算聚合统计
        aggregated = AggregatedMetric(
            name=metric_name,
            count=len(values),
            min=min(values),
            max=max(values),
            avg=statistics.mean(values),
            sum=sum(values),
            timestamps=timestamps,
        )

        # 计算标准差
        if len(values) > 1:
            aggregated.std = statistics.stdev(values)

        # 计算百分位数
        if len(values) >= 4:
            aggregated.p50 = statistics.median(values)
            sorted_values = sorted(values)
            p95_index = int(len(sorted_values) * 0.95)
            p99_index = int(len(sorted_values) * 0.99)
            aggregated.p95 = sorted_values[min(p95_index, len(sorted_values) - 1)]
            aggregated.p99 = sorted_values[min(p99_index, len(sorted_values) - 1)]

        return aggregated

    def get_realtime_snapshot(self) -> dict[str, Any]:
        """获取实时快照"""
        return {
            "timestamp": datetime.now().isoformat(),
            "environment": self.monitor.environment_type.value,
            "system_metrics": self._get_latest_metrics("system"),
            "execution_metrics": self._get_latest_metrics("execution"),
            "business_metrics": self._get_latest_metrics("business"),
            "quality_metrics": self._get_latest_metrics("quality"),
            "cache_stats": {
                "total_cached_metrics": sum(
                    len(cache) for cache in self.metrics_cache.values()
                ),
                "categories": len(self.metrics_cache),
            },
        }

    def _get_latest_metrics(self, category: str) -> dict[str, float]:
        """获取最新指标"""
        latest_metrics = {}

        for cache_key, cached_metrics in self.metrics_cache.items():
            if category in cache_key and cached_metrics:
                latest_metric = cached_metrics[-1]
                metric_name = latest_metric.name
                latest_metrics[metric_name] = latest_metric.value

        return latest_metrics

    def generate_summary_report(self) -> str:
        """生成汇总报告"""
        report = []

        report.append("=" * 70)
        report.append("📊 SSOT 指标收集汇总报告")
        report.append("=" * 70)

        # 实时快照
        snapshot = self.get_realtime_snapshot()

        report.append(f"\n🕐 时间: {snapshot['timestamp']}")
        report.append(f"🌍 环境: {snapshot['environment']}")

        # 系统指标
        system_metrics = snapshot["system_metrics"]
        if system_metrics:
            report.append("\n🖥️  系统指标:")
            for name, value in system_metrics.items():
                icon = (
                    "🔥"
                    if "cpu_percent" in name and value > 80
                    else ("🔴" if "memory_percent" in name and value > 80 else "✅")
                )
                report.append(f"  {icon} {name}: {value:.2f}")

        # 缓存统计
        cache_stats = snapshot["cache_stats"]
        report.append("\n📈 缓存统计:")
        report.append(f"  总缓存指标: {cache_stats['total_cached_metrics']}")
        report.append(f"  指标分类数: {cache_stats['categories']}")

        # 执行统计（如果有）
        if hasattr(self.execution_collector, "get_execution_statistics"):
            exec_stats = self.execution_collector.get_execution_statistics(
                window_minutes=60
            )
            report.append("\n⚡ 执行统计 (最近60分钟):")
            report.append(f"  总执行次数: {exec_stats['total_executions']}")
            report.append(f"  平均执行时间: {exec_stats['average_time_ms']:.2f}ms")
            report.append(f"  成功率: {exec_stats['success_rate'] * 100:.1f}%")
            report.append(f"  吞吐量: {exec_stats['throughput']:.1f} rules/s")

        report.append("=" * 70)

        return "\n".join(report)
