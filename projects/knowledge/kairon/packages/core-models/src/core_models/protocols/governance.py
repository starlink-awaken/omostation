"""GovernanceProtocol — 治理策略声明

每个服务声明其遵守的治理策略和合规级别。
"""

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable


@dataclass
class GovernancePolicy:
    """治理策略"""

    service: str
    policies: list[str] = field(default_factory=list)
    compliance_level: Literal["full", "partial", "none"] = "none"
    audit_enabled: bool = False
    data_retention_days: int = 90
    auto_recovery: bool = False
    threat_response: Literal["alert", "quarantine", "block"] = "alert"


@runtime_checkable
class GovernanceProtocol(Protocol):
    """治理协议"""

    def governance_policy(self) -> GovernancePolicy:
        """返回服务的治理策略声明"""
        ...

    async def audit_log(self, event: str, details: dict) -> None:
        """写入审计日志"""
        ...

    async def compliance_check(self) -> dict[str, bool]:
        """执行合规检查并返回结果"""
        ...
