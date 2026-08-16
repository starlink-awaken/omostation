"""MetricsProtocol — Prometheus指标暴露

所有服务暴露Prometheus格式的运行指标。

端点: GET /metrics
格式: Prometheus text exposition format
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class MetricsProtocol(Protocol):
    """指标协议"""

    async def metrics(self) -> str:
        """返回Prometheus text格式的运行指标"""
        ...

    async def metric_value(self, name: str, labels: dict | None = None) -> float:
        """查询单个指标的当前值"""
        ...

    def counter(self, name: str, help_text: str = "") -> None:
        """注册一个计数器指标"""
        ...

    def gauge(self, name: str, help_text: str = "") -> None:
        """注册一个仪表指标"""
        ...

    def histogram(self, name: str, help_text: str = "", buckets: list[float] | None = None) -> None:
        """注册一个直方图指标"""
        ...
