"""HealthProtocol — 服务健康检查

所有注册到神经中枢的服务必须实现此协议。

端点: GET /health
SLA: 探测间隔30s，连续3次失败触发告警
"""

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable


@dataclass
class HealthStatus:
    """健康状态"""

    service: str
    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    uptime_seconds: float = 0.0
    checks: dict[str, bool] = field(default_factory=dict)
    message: str = ""


@runtime_checkable
class HealthProtocol(Protocol):
    """健康协议"""

    async def health(self) -> HealthStatus:
        """返回服务健康状态"""
        ...

    async def readiness(self) -> bool:
        """就绪探测：服务是否准备好接收流量"""
        ...

    async def liveness(self) -> bool:
        """存活探测：服务是否需要重启"""
        ...
