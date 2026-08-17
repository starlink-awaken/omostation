from __future__ import annotations

"""
Extracted from SharedBrain D_Harvest → minerva.

---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# Metrics Collector ≡ Module
# 内涵 ≝ {Metrics, Collector}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, MetricsCollector)}
# 功能 ⊢ {Metrics_Collector, Init_Metrics, Validate_Collector}
# =============================================================================

# ---
# domain: D-Harvest
# layer: observability
# status: active
# ---

"""
D-Harvest 增强指标收集器

遵循 METRICS_SPECIFICATION.md 规范的完整指标实现。
支持Prometheus格式导出、Histogram分桶、多维度标签。

核心特性：
- Counter/Gauge/Histogram完整实现
- Prometheus文本格式导出
- HTTP端点支持
- 线程安全
- 符合SOLID原则
"""

import contextlib
import logging
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from functools import wraps
from pathlib import Path
from typing import ParamSpec, TypeVar

logger = logging.getLogger(__name__)
P = ParamSpec("P")
R = TypeVar("R")

# 组件标识符
COMPONENT = "d_harvest"

# Histogram默认分桶 (秒)
DEFAULT_DURATION_BUCKETS = (0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0)

# Size分桶 (条目数)
DEFAULT_SIZE_BUCKETS = (1, 10, 50, 100, 500, 1000, 5000, 10000)


class MetricType(StrEnum):
    """Prometheus指标类型"""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricFamily:
    """
    Prometheus指标家族

    一个指标名称可以包含多个带不同标签的序列。
    """

    name: str
    metric_type: MetricType
    help_text: str = ""
    samples: dict[frozenset[tuple[str, str]], float] = field(default_factory=dict)
    histogram_buckets: dict[frozenset[tuple[str, str]], list[tuple[float, float]]] = field(default_factory=dict)
    created: float = field(default_factory=time.time)

    def add_sample(self, value: float, labels: dict[str, str] | None = None) -> None:
        """添加或更新样本"""
        key = frozenset(labels.items()) if labels else frozenset()
        self.samples[key] = value

    def get_sample(self, labels: dict[str, str] | None = None) -> float | None:
        """获取样本值"""
        key = frozenset(labels.items()) if labels else frozenset()
        return self.samples.get(key)

    def observe_histogram(
        self, value: float, labels: dict[str, str] | None = None, buckets: tuple[float, ...] = DEFAULT_DURATION_BUCKETS
    ) -> None:
        """记录Histogram观测值"""
        key = frozenset(labels.items()) if labels else frozenset()

        # 初始化bucket结构
        if key not in self.histogram_buckets:
            self.histogram_buckets[key] = [(b, 0.0) for b in buckets] + [(float("inf"), 0.0)]

        # 记录每桶原始计数；Prometheus 导出阶段再转成累计值。
        buckets_list = self.histogram_buckets[key]
        for i, (bound, _) in enumerate(buckets_list):
            if value <= bound:
                buckets_list[i] = (bound, buckets_list[i][1] + 1)
                break

        # 更新sum和count
        sum_key = key | {("__name__", "_sum")}
        count_key = key | {("__name__", "_count")}
        self.samples[sum_key] = self.samples.get(sum_key, 0.0) + value
        self.samples[count_key] = self.samples.get(count_key, 0.0) + 1

    def to_prometheus(self) -> str:
        """导出为Prometheus文本格式"""
        lines = []

        # HELP行
        if self.help_text:
            lines.append(f"# HELP {COMPONENT}_{self.name} {self.help_text}")

        # TYPE行
        lines.append(f"# TYPE {COMPONENT}_{self.name} {self.metric_type.value}")

        # 样本数据
        if self.metric_type == MetricType.HISTOGRAM:
            # Histogram特殊处理
            for label_key, buckets in self.histogram_buckets.items():
                labels = dict(label_key)

                # 基础标签（去掉__name__）
                base_labels = {k: v for k, v in labels.items() if k != "__name__"}

                # 桶数据
                cumulative = 0.0
                for bound, count in buckets:
                    cumulative += count
                    if bound == float("inf"):
                        bucket_le = "+Inf"
                    else:
                        bucket_le = str(bound)

                    if base_labels:
                        label_str = (
                            "{" + ", ".join(f'{k}="{v}"' for k, v in base_labels.items()) + f', le="{bucket_le}"'
                        )
                    else:
                        label_str = '{le="' + bucket_le + '"}'

                    lines.append(f"{COMPONENT}_{self.name}_bucket{label_str} {cumulative}")

                # sum和count
                sum_labels = dict(base_labels)
                if sum_labels:
                    sum_label_str = "{" + ", ".join(f'{k}="{v}"' for k, v in sum_labels.items()) + "}"
                else:
                    sum_label_str = ""

                lines.append(
                    f"{COMPONENT}_{self.name}_sum{sum_label_str} {self.samples.get(label_key | {('__name__', '_sum')}, 0.0)}"
                )
                lines.append(
                    f"{COMPONENT}_{self.name}_count{sum_label_str} {self.samples.get(label_key | {('__name__', '_count')}, 0.0)}"
                )

        else:
            # Counter和Gauge
            for label_key, value in self.samples.items():
                labels = dict(label_key)
                # 跳过内部使用的样本键（如 __name__=_sum/_count）
                if "__name__" in labels:
                    continue

                if labels:
                    label_str = "{" + ", ".join(f'{k}="{v}"' for k, v in sorted(labels.items())) + "}"
                else:
                    label_str = ""

                lines.append(f"{COMPONENT}_{self.name}{label_str} {value}")

        return "\n".join(lines)


class HarvestMetricsCollector:
    """
    D-Harvest 增强指标收集器

    线程安全的指标收集和导出，支持Prometheus抓取。

    遵循原则：
    - SRP: 只负责指标收集，不负责业务逻辑
    - 线程安全: 使用锁保护共享状态
    - KISS: 简洁的API设计
    """

    def __init__(self) -> None:
        """初始化收集器"""
        self._families: dict[str, MetricFamily] = {}
        self._lock = threading.RLock()
        self._start_time = time.time()

        # 注册预定义指标
        self._register_builtins()

    def _register_builtins(self) -> None:
        """注册内置指标"""
        # ============ 收割指标 ============
        self._register_histogram(
            "harvest_duration_seconds",
            "收割操作总耗时",
            buckets=DEFAULT_DURATION_BUCKETS,
        )
        self._register_histogram(
            "harvest_extract_duration_seconds",
            "提取阶段耗时",
            buckets=DEFAULT_DURATION_BUCKETS,
        )
        self._register_histogram(
            "harvest_store_duration_seconds",
            "存储阶段耗时",
            buckets=DEFAULT_DURATION_BUCKETS,
        )
        self._register_histogram(
            "harvest_sync_duration_seconds",
            "同步阶段耗时",
            buckets=DEFAULT_DURATION_BUCKETS,
        )

        self._register_counter("harvests_total", "收割操作总计数")
        self._register_counter("items_harvested_total", "提取的知识条目总数")
        self._register_counter("harvest_errors_total", "收割错误总数")
        self._register_gauge("harvest_error_rate", "收割错误率百分比")

        # ============ 调度指标 ============
        self._register_gauge("scheduler_jobs_total", "作业总数")
        self._register_gauge("scheduler_running_jobs", "当前运行中的作业数")
        self._register_histogram(
            "schedule_execution_delay_seconds",
            "从到期到开始执行的延迟",
            buckets=(0.1, 1.0, 5.0, 10.0, 30.0, 60.0),
        )
        self._register_histogram(
            "schedule_queue_wait_seconds",
            "作业在队列中等待时间",
            buckets=(0.1, 1.0, 5.0, 10.0, 30.0),
        )
        self._register_gauge("scheduler_concurrent_limit", "并发上限配置")
        self._register_gauge("scheduler_concurrent_usage", "当前并发使用数")

        # ============ 质量指标 ============
        self._register_histogram(
            "quality_score",
            "单条知识质量分数 (0-1)",
            buckets=(0.1, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
        )
        self._register_gauge("quality_score_avg", "平均质量分数")
        self._register_counter("quality_gate_passed_total", "门控通过总数")
        self._register_counter("quality_gate_failed_total", "门控拒绝总数")
        self._register_gauge("quality_gate_pass_rate", "门控通过率百分比")

        # ============ 存储指标 ============
        self._register_histogram(
            "storage_insert_duration_seconds",
            "数据库插入耗时",
            buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
        )
        self._register_histogram(
            "storage_query_duration_seconds",
            "查询耗时",
            buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
        )
        self._register_gauge("storage_items_total", "存储的知识条目总数")
        self._register_counter("storage_duplicates_skipped_total", "跳过的重复条目数")
        self._register_gauge("sync_factgraph_lag_items", "待同步到FactGraph的条目数")
        self._register_gauge("sync_vector_lag_items", "待生成向量的条目数")

        # ============ 资源指标 ============
        self._register_gauge("db_connections_active", "活跃数据库连接数")
        self._register_gauge("db_connections_idle", "空闲数据库连接数")
        self._register_gauge("cache_size_items", "缓存条目数")
        self._register_gauge("cache_hit_rate", "缓存命中率百分比")

        # ============ 业务指标 ============
        self._register_gauge("knowledge_coverage_sources", "已覆盖的知识来源数")
        self._register_gauge("knowledge_freshness_seconds", "最新知识距今时间")

    def _register_counter(self, name: str, help_text: str = "", labels: dict[str, str] | None = None) -> MetricFamily:
        """注册或获取Counter指标"""
        with self._lock:
            if name not in self._families:
                self._families[name] = MetricFamily(
                    name=name,
                    metric_type=MetricType.COUNTER,
                    help_text=help_text,
                )
            return self._families[name]

    def _register_gauge(self, name: str, help_text: str = "", labels: dict[str, str] | None = None) -> MetricFamily:
        """注册或获取Gauge指标"""
        with self._lock:
            if name not in self._families:
                self._families[name] = MetricFamily(
                    name=name,
                    metric_type=MetricType.GAUGE,
                    help_text=help_text,
                )
            return self._families[name]

    def _register_histogram(
        self,
        name: str,
        help_text: str = "",
        buckets: tuple[float, ...] = DEFAULT_DURATION_BUCKETS,
    ) -> MetricFamily:
        """注册或获取Histogram指标"""
        with self._lock:
            if name not in self._families:
                self._families[name] = MetricFamily(
                    name=name,
                    metric_type=MetricType.HISTOGRAM,
                    help_text=help_text,
                )
            return self._families[name]

    # ============ 公开API ============

    def inc(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """
        增加Counter指标

        Args:
            name: 指标名称（不含前缀）
            value: 增量值
            labels: 标签维度
        """
        with self._lock:
            if name not in self._families:
                self._register_counter(name)

            current = self._families[name].get_sample(labels) or 0.0
            self._families[name].add_sample(current + value, labels)

    def set(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """
        设置Gauge指标

        Args:
            name: 指标名称（不含前缀）
            value: 指标值
            labels: 标签维度
        """
        with self._lock:
            if name not in self._families:
                self._register_gauge(name)

            self._families[name].add_sample(value, labels)

    def observe(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
        buckets: tuple[float, ...] = DEFAULT_DURATION_BUCKETS,
    ) -> None:
        """
        记录Histogram观测值

        Args:
            name: 指标名称（不含前缀）
            value: 观测值
            labels: 标签维度
            buckets: 分桶定义
        """
        with self._lock:
            if name not in self._families:
                self._register_histogram(name, buckets=buckets)

            self._families[name].observe_histogram(value, labels, buckets)

    def get_metric(self, name: str, labels: dict[str, str] | None = None) -> float | None:
        """获取指标值"""
        with self._lock:
            family = self._families.get(name)
            if family:
                return family.get_sample(labels)
            return None

    def export_prometheus(self) -> str:
        """
        导出所有指标为Prometheus文本格式

        Returns:
            Prometheus文本格式字符串
        """
        with self._lock:
            lines = []

            # 添加进程基础指标
            uptime = time.time() - self._start_time
            lines.append(f"# HELP {COMPONENT}_uptime_seconds 进程运行时间")
            lines.append(f"# TYPE {COMPONENT}_uptime_seconds gauge")
            lines.append(f"{COMPONENT}_uptime_seconds {uptime:.3f}")
            lines.append("")

            # 导出所有指标家族
            for family in self._families.values():
                lines.append(family.to_prometheus())
                lines.append("")

            return "\n".join(lines)

    def save_to_file(self, path: Path) -> bool:
        """
        导出指标到文件供Prometheus抓取

        Args:
            path: 输出文件路径

        Returns:
            写入成功返回True
        """
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            content = self.export_prometheus()
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except OSError as e:
            logger.error(f"Failed to save metrics to {path}: {e}")
            return False

    def reset(self) -> None:
        """重置所有指标（慎用！）"""
        with self._lock:
            self._families.clear()
            self._start_time = time.time()
            self._register_builtins()
            logger.warning("All metrics have been reset")


# ============ 上下文管理器用于计时 ============


@contextlib.contextmanager
def measure_duration(
    collector: HarvestMetricsCollector,
    metric_name: str,
    labels: dict[str, str] | None = None,
    buckets: tuple[float, ...] = DEFAULT_DURATION_BUCKETS,
) -> Iterator[None]:
    """
    测量代码块执行时长的上下文管理器

    Example:
        with measure_duration(collector, "harvest_duration_seconds", {"source_id": "xyz"}):
            do_harvest()
    """
    start = time.time()
    try:
        yield
    finally:
        duration = time.time() - start
        collector.observe(metric_name, duration, labels, buckets)


def timed(
    collector: HarvestMetricsCollector,
    metric_name: str,
    label_func: Callable[P, dict[str, str]] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    装饰器：测量函数执行时长

    Example:
        @timed(collector, "harvest_duration_seconds")
        def harvest(source_id: str):
            ...
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            start = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                labels = label_func(*args, **kwargs) if label_func else None
                collector.observe(metric_name, duration, labels)

        return wrapper

    return decorator


# ============ 单例实例 ============

_global_collector: HarvestMetricsCollector | None = None
_global_lock = threading.Lock()


def get_global_collector() -> HarvestMetricsCollector:
    """获取全局指标收集器实例"""
    global _global_collector
    with _global_lock:
        if _global_collector is None:
            _global_collector = HarvestMetricsCollector()
        return _global_collector


def reset_global_collector() -> None:
    """重置全局收集器（测试用）"""
    global _global_collector
    with _global_lock:
        _global_collector = None
