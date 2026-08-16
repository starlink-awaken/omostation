"""SharedBrain Core — 协议定义

本包定义共享的接口协议，SharedBrain协调运行时与kairon服务实现。
所有协议基于Python Protocol类型，支持运行时和静态类型检查。

协议:
  - IdentityProtocol: 身份验证与权限控制
  - HealthProtocol: 服务健康检查
  - CircuitProtocol: 回路状态机执行
  - MetricsProtocol: Prometheus指标暴露
  - GovernanceProtocol: 治理策略声明
"""

from core_models.protocols.circuit import CircuitDefinition, CircuitProtocol, CircuitRun
from core_models.protocols.governance import GovernancePolicy, GovernanceProtocol
from core_models.protocols.health import HealthProtocol, HealthStatus
from core_models.protocols.identity import IdentityProtocol, IdentityResult
from core_models.protocols.metrics import MetricsProtocol

__all__ = [
    "IdentityProtocol",
    "IdentityResult",
    "HealthProtocol",
    "HealthStatus",
    "CircuitProtocol",
    "CircuitDefinition",
    "CircuitRun",
    "MetricsProtocol",
    "GovernanceProtocol",
    "GovernancePolicy",
]
