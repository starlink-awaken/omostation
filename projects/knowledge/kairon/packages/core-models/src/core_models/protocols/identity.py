"""IdentityProtocol — 身份验证与权限控制

所有提供身份验证的服务必须实现此协议。
实现位置: kairon/metaos (core/immune.py + core/gate.py)
"""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class IdentityResult:
    """身份验证结果"""

    identity_id: str
    principal: str
    authenticated: bool
    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    expires_at: float = 0.0
    metadata: dict = field(default_factory=dict)


@runtime_checkable
class IdentityProtocol(Protocol):
    """身份验证协议

    端点: POST /v1/identity/verify
    SLA: p99 < 50ms, availability 99.9%
    实现: kairon/metaos
    """

    async def verify_identity(self, principal: str, credentials: dict) -> IdentityResult:
        """验证主体身份并返回身份结果"""
        ...

    async def check_permission(self, principal: str, action: str, resource: str) -> bool:
        """检查主体对资源的操作权限"""
        ...

    async def get_roles(self, principal: str) -> list[str]:
        """获取主体拥有的角色列表"""
        ...

    async def authenticate(self, credentials: dict) -> IdentityResult:
        """认证并返回身份令牌"""
        ...
