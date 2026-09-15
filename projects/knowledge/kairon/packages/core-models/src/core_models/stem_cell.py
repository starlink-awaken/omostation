"""StemCellValidator — 干细胞接口验证器

新服务注册到神经中枢前，必须通过干细胞验证：
实现5个必要接口(Health + Identity + Metrics + Circuit + Governance)
采用渐进式采纳：当前只强制Health + Identity，其余按需。

验证流程:
1. 服务启动时调用 POST /neural/register
2. 干细胞验证器逐一检查接口
3. 全部必要接口通过 → 注册成功，分配神经元ID
4. 任一必要接口失败 → 拒绝注册，返回缺失接口清单
"""

from dataclasses import dataclass, field
from typing import Any, Protocol

from core_models.protocols.circuit import CircuitProtocol
from core_models.protocols.governance import GovernanceProtocol
from core_models.protocols.health import HealthProtocol
from core_models.protocols.identity import IdentityProtocol
from core_models.protocols.metrics import MetricsProtocol

# 渐进取采纳：当前只强制Health + Identity
REQUIRED_INTERFACES: list[type[Protocol]] = [  # type: ignore[valid-type]
    HealthProtocol,
    IdentityProtocol,
]

# 可选接口：服务可按需实现
OPTIONAL_INTERFACES: list[type[Protocol]] = [  # type: ignore[valid-type]
    MetricsProtocol,
    CircuitProtocol,
    GovernanceProtocol,
]


@dataclass
class ValidationResult:
    """干细胞验证结果"""

    service_name: str
    passed: bool
    required_passed: list[str] = field(default_factory=list)
    required_failed: list[str] = field(default_factory=list)
    optional_implemented: list[str] = field(default_factory=list)
    neuron_id: str = ""


def validate_service(service: Any, service_name: str) -> ValidationResult:
    """验证一个服务是否实现了必要的干细胞接口

    渐进式采纳：只检查REQUIRED_INTERFACES中的接口。
    可选接口通过OPTIONAL_INTERFACES列表告知服务可实现的额外能力。

    Args:
        service: 待验证的服务实例
        service_name: 服务名称

    Returns:
        ValidationResult: 验证结果，包含通过的接口和失败的接口
    """
    result = ValidationResult(service_name=service_name, passed=True)

    for iface in REQUIRED_INTERFACES:
        iface_name = iface.__name__
        if isinstance(service, iface):
            result.required_passed.append(iface_name)
        else:
            result.required_failed.append(iface_name)
            result.passed = False

    for iface in OPTIONAL_INTERFACES:
        iface_name = iface.__name__
        if isinstance(service, iface):
            result.optional_implemented.append(iface_name)

    if result.passed:
        result.neuron_id = f"neuron-{service_name}"

    return result
