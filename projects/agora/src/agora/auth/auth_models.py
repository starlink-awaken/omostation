"""Authentication and authorization models for OAuth2/JWT-based access control.

Extracted from SharedBrain D_Gateway.  Self-contained dataclasses and
exception hierarchy — no nucleus dependencies.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class TokenType(Enum):
    """令牌类型"""

    ACCESS_TOKEN = "access_token"  # noqa: S105
    REFRESH_TOKEN = "refresh_token"  # noqa: S105
    ID_TOKEN = "id_token"  # noqa: S105


class GrantType(Enum):
    """授权类型"""

    AUTHORIZATION_CODE = "authorization_code"
    CLIENT_CREDENTIALS = "client_credentials"
    REFRESH_TOKEN = "refresh_token"  # noqa: S105


@dataclass
class OAuth2Client:
    """
    OAuth2 客户端定义

    Security contract
    -----------------
    ``verify_secret`` uses :func:`secrets.compare_digest` for **constant-time**
    comparison.  This prevents timing-based side-channel attacks that could
    allow an attacker to brute-force the client secret by measuring response
    latency.  Do NOT replace this with a plain ``==`` comparison.

    Attributes:
        client_id: 客户端 ID
        client_secret: 客户端密钥 (哈希存储)
        client_name: 客户端名称
        redirect_uris: 重定向 URI 列表
        grant_types: 允许的授权类型
        scopes: 允许的范围
        active: 是否激活
    """

    client_id: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    client_secret: str = field(default_factory=lambda: secrets.token_urlsafe(64))
    client_name: str = ""
    redirect_uris: list[str] = field(default_factory=list)
    grant_types: list[GrantType] = field(default_factory=list)
    scopes: set[str] = field(default_factory=set)
    active: bool = True
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        self.created_at = _normalize_utc(self.created_at)

    def verify_secret(self, secret: str) -> bool:
        """Verify a client secret in constant time.

        Security contract
        -----------------
        Uses :func:`secrets.compare_digest` so that comparison time is
        **independent of where the strings first differ**.  This eliminates the
        timing side-channel that a plain ``==`` comparison would expose,
        preventing attackers from enumerating valid secrets character-by-character.

        Args:
            secret: The plaintext secret provided by the caller.

        Returns:
            ``True`` if *secret* matches the stored client secret, ``False`` otherwise.
        """
        # secrets.compare_digest provides timing-safe comparison — do NOT change
        # this to a plain equality check.
        return secrets.compare_digest(self.client_secret, secret)

    def to_dict(self) -> dict:
        """转换为字典 (不包含敏感信息)"""
        return {
            "client_id": self.client_id,
            "client_name": self.client_name,
            "redirect_uris": self.redirect_uris,
            "grant_types": [gt.value for gt in self.grant_types],
            "scopes": list(self.scopes),
            "active": self.active,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class OAuth2Token:
    """
    OAuth2 令牌定义

    Attributes:
        access_token: 访问令牌
        token_type: 令牌类型
        expires_in: 过期时间 (秒)
        refresh_token: 刷新令牌
        scope: 授权范围
        issued_at: 签发时间
    """

    access_token: str
    token_type: str = "Bearer"  # noqa: S105
    expires_in: int = 3600  # 默认 1 小时
    refresh_token: str | None = None
    scope: str = ""
    issued_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        self.issued_at = _normalize_utc(self.issued_at)

    @property
    def expires_at(self) -> datetime:
        """获取过期时间"""
        return self.issued_at + timedelta(seconds=self.expires_in)

    @property
    def is_expired(self) -> bool:
        """检查是否过期"""
        return _utc_now() >= self.expires_at

    def to_dict(self) -> dict:
        """转换为字典 (用于 JSON 响应)"""
        return {
            "access_token": self.access_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "refresh_token": self.refresh_token,
            "scope": self.scope,
        }


@dataclass
class AuthenticatedUser:
    """
    认证用户定义

    Attributes:
        user_id: 用户 ID
        username: 用户名
        email: 邮箱
        roles: 角色列表
        permissions: 权限列表
        scopes: 授权范围
    """

    user_id: str
    username: str
    email: str
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)
    scopes: set[str] = field(default_factory=set)

    def has_permission(self, permission: str) -> bool:
        """检查是否有指定权限"""
        return permission in self.permissions

    def has_scope(self, scope: str) -> bool:
        """检查是否有指定范围"""
        return scope in self.scopes

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "roles": self.roles,
            "permissions": list(self.permissions),
            "scopes": list(self.scopes),
        }


@dataclass
class JWTClaims:
    """
    JWT 声明定义

    Attributes:
        iss: 签发者
        sub: 主题 (用户 ID)
        aud: 受众 (客户端 ID)
        exp: 过期时间
        iat: 签发时间
        jti: JWT ID
        scope: 授权范围
        roles: 角色列表
    """

    iss: str
    sub: str
    aud: str
    exp: datetime
    iat: datetime = field(default_factory=_utc_now)
    jti: str = field(default_factory=lambda: secrets.token_urlsafe(16))
    scope: str = ""
    roles: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.exp = _normalize_utc(self.exp)
        self.iat = _normalize_utc(self.iat)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "iss": self.iss,
            "sub": self.sub,
            "aud": self.aud,
            "exp": int(self.exp.timestamp()),
            "iat": int(self.iat.timestamp()),
            "jti": self.jti,
            "scope": self.scope,
            "roles": self.roles,
        }

    @classmethod
    def from_dict(cls, data: dict) -> JWTClaims:
        """从字典创建"""
        return cls(
            iss=data["iss"],
            sub=data["sub"],
            aud=data["aud"],
            exp=datetime.fromtimestamp(data["exp"], UTC),
            iat=datetime.fromtimestamp(data.get("iat", _utc_now().timestamp()), UTC),
            jti=data.get("jti", ""),
            scope=data.get("scope", ""),
            roles=data.get("roles", []),
        )


class AuthenticationError(Exception):
    """认证错误"""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code or "authentication_failed"


class AuthorizationError(Exception):
    """授权错误"""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code or "authorization_failed"


class TokenRevokedError(AuthenticationError):
    """令牌已被吊销"""

    def __init__(self, message: str = "Token has been revoked") -> None:
        super().__init__(message, code="token_revoked")


class TokenExpiredError(AuthenticationError):
    """令牌已过期"""

    def __init__(self, message: str = "Token has expired") -> None:
        super().__init__(message, code="token_expired")


class InvalidTokenError(AuthenticationError):
    """无效令牌"""

    def __init__(self, message: str = "Invalid token") -> None:
        super().__init__(message, code="invalid_token")
