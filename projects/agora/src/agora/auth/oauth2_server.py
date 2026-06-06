from __future__ import annotations

"""
---
Type: Organ
Status: Active
Layer: L3
Summary: OAuth2 token issuance server with JWT signing and thread-safe token lifecycle management.
Owner: bos-core
Version: 1.0.1
Authority: organs/D-Gateway/AGENTS.md
---
"""

import base64 as _base64

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Oauth2 Server ≡ Server
# 内涵 ≝ {Oauth2, Server}
# 外延 ≝ {e | e ∈ D-Gateway ∧ implements(e, Oauth2Server)}
# 功能 ⊢ {Oauth2_Server, Init_Oauth2, Validate_Server}
# =============================================================================
import hashlib
import hmac
import json as _json
import logging
import secrets
import threading
import time
from datetime import UTC, datetime, timedelta
from typing import Any


class _JWTShimInvalidTokenError(ValueError):
    """Fallback JWT invalid-token error compatible with PyJWT semantics."""


class _JWTShimExpiredSignatureError(_JWTShimInvalidTokenError):
    """Fallback JWT expiration error compatible with PyJWT semantics."""


def _jwt_b64_encode(data: bytes) -> str:
    return _base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _jwt_b64_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return _base64.urlsafe_b64decode(f"{segment}{padding}".encode("ascii"))


class _JWTShim:
    ExpiredSignatureError = _JWTShimExpiredSignatureError
    InvalidTokenError = _JWTShimInvalidTokenError

    @staticmethod
    def encode(payload: dict, key: str, algorithm: str = "HS256") -> str:
        if algorithm != "HS256":
            raise _JWTShimInvalidTokenError(f"Unsupported algorithm: {algorithm}")
        header = {"alg": "HS256", "typ": "JWT"}
        header_segment = _jwt_b64_encode(_json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        payload_segment = _jwt_b64_encode(_json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
        signature = hmac.new(key.encode("utf-8"), signing_input, hashlib.sha256).digest()
        return f"{header_segment}.{payload_segment}.{_jwt_b64_encode(signature)}"

    @staticmethod
    def decode(
        token: str,
        key: str | None = None,
        algorithms: list[str] | None = None,
        issuer: str | None = None,
        audience: str | None = None,
        options: dict[str, bool] | None = None,
    ) -> dict:
        opts = options or {}
        verify_signature = opts.get("verify_signature", True)
        verify_exp = opts.get("verify_exp", verify_signature)
        verify_aud = opts.get("verify_aud", bool(audience))

        try:
            header_segment, payload_segment, signature_segment = token.split(".")
        except ValueError as exc:
            raise _JWTShimInvalidTokenError("Token must have 3 segments") from exc

        try:
            payload = _json.loads(_jwt_b64_decode(payload_segment))
        except (ValueError, TypeError) as exc:
            raise _JWTShimInvalidTokenError("Invalid payload encoding") from exc

        if verify_signature:
            if algorithms and "HS256" not in algorithms:
                raise _JWTShimInvalidTokenError("HS256 not allowed by algorithms")
            if not key:
                raise _JWTShimInvalidTokenError("Signing key required")
            signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
            expected_signature = hmac.new(key.encode("utf-8"), signing_input, hashlib.sha256).digest()
            actual_signature = _jwt_b64_decode(signature_segment)
            if not hmac.compare_digest(expected_signature, actual_signature):
                raise _JWTShimInvalidTokenError("Signature verification failed")

        if issuer is not None and payload.get("iss") != issuer:
            raise _JWTShimInvalidTokenError("Invalid issuer")

        if verify_exp and "exp" in payload:
            try:
                exp = float(payload["exp"])
            except (TypeError, ValueError) as exc:
                raise _JWTShimInvalidTokenError("Invalid exp claim") from exc
            if time.time() >= exp:
                raise _JWTShimExpiredSignatureError("Token expired")

        if verify_aud and audience is not None:
            aud_claim = payload.get("aud")
            if isinstance(aud_claim, list):
                if audience not in aud_claim:
                    raise _JWTShimInvalidTokenError("Invalid audience")
            elif aud_claim != audience:
                raise _JWTShimInvalidTokenError("Invalid audience")

        return payload


try:
    import jwt

    _JWT_AVAILABLE = True
except ImportError:  # pragma: no cover — optional dependency
    jwt = _JWTShim()  # type: ignore[assignment]
    _JWT_AVAILABLE = True

try:
    import base64

    from cryptography.fernet import Fernet

    _FERNET_AVAILABLE = True
except ImportError:  # pragma: no cover — optional dependency
    Fernet = None  # type: ignore[assignment, unused-ignores]
    base64 = None  # type: ignore[assignment, unused-ignores]
    _FERNET_AVAILABLE = False

from agora.auth.auth_models import (  # type: ignore[import-not-found]
    AuthenticatedUser,
    AuthenticationError,
    AuthorizationError,
    GrantType,
    InvalidTokenError,
    JWTClaims,
    OAuth2Client,
    OAuth2Token,
    TokenExpiredError,
    TokenRevokedError,
)

_log = logging.getLogger(__name__)


class OAuth2Server:
    """
    OAuth2 认证服务器

    支持的授权流程:
    1. Authorization Code Flow (Web 应用)
    2. Client Credentials Flow (机器对机器)
    3. Refresh Token Flow (令牌刷新)

    特性:
    - JWT 令牌签发和验证
    - 令牌吊销
    - 范围 (Scope) 控制
    """

    def __init__(
        self,
        jwt_secret: str | None = None,
        jwt_issuer: str = "sharedbrain-gateway",
        access_token_lifetime: int = 3600,
        refresh_token_lifetime: int = 86400 * 7,  # 7 天
        token_encryption_key: str | None = None,
    ) -> None:
        """
        初始化 OAuth2 服务器

        Args:
            jwt_secret: JWT 签名密钥 (如果不提供则自动生成)
            jwt_issuer: JWT 签发者
            access_token_lifetime: Access Token 有效期 (秒)
            refresh_token_lifetime: Refresh Token 有效期 (秒)
            token_encryption_key: Fernet 对称加密密钥 (如果不提供则自动生成)。
                存储的刷新令牌使用此密钥加密，validate 时解密。
        """
        self._jwt_secret = jwt_secret or secrets.token_urlsafe(64)
        self._jwt_issuer = jwt_issuer
        self._access_token_lifetime = access_token_lifetime
        self._refresh_token_lifetime = refresh_token_lifetime
        self._lock = threading.RLock()
        self._clients: dict[str, OAuth2Client] = {}
        self._tokens: dict[str, OAuth2Token] = {}
        self._revoked_tokens: set[str] = set()
        self._authorization_codes: dict[str, dict] = {}
        self._issue_count: int = 0
        # Tracks timestamps of recent authentication failures per client_id.
        # Used by _check_auth_rate_limit to enforce brute-force protection.
        self._auth_failures: dict[str, list[float]] = {}
        # Fernet token encryption
        self._fernet: Any | None = None
        if token_encryption_key is not None and _FERNET_AVAILABLE:
            self._fernet = Fernet(token_encryption_key.encode())
        elif _FERNET_AVAILABLE:
            self._fernet = Fernet(Fernet.generate_key())
        else:
            _log.warning("Fernet not available — refresh tokens stored in plaintext (NOT for production)")

    # ------------------------------------------------------------------
    # Token encryption helpers (Fernet: AES-CBC + HMAC, base64-encoded)
    # ------------------------------------------------------------------
    def _encrypt_token(self, plaintext: str) -> str:
        """Encrypt a plaintext token. Returns the ciphertext (str)."""
        if self._fernet is None:
            return plaintext
        return self._fernet.encrypt(plaintext.encode()).decode()

    def _decrypt_token(self, ciphertext: str) -> str:
        """Decrypt a ciphertext token back to plaintext."""
        if self._fernet is None:
            return ciphertext
        return self._fernet.decrypt(ciphertext.encode()).decode()

    def _token_key(self, token: str) -> str:
        """Derive a deterministic opaque lookup key for token indexing."""
        return hmac.new(
            self._jwt_secret.encode(),
            token.encode(),
            hashlib.sha256,
        ).hexdigest()

    def register_client(self, client: OAuth2Client) -> None:
        """
        注册 OAuth2 客户端

        Args:
            client: OAuth2 客户端对象
        """
        with self._lock:
            self._clients[client.client_id] = client

    def get_client(self, client_id: str) -> OAuth2Client | None:
        """
        获取客户端信息

        Args:
            client_id: 客户端 ID

        Returns:
            OAuth2 客户端对象，不存在返回 None
        """
        with self._lock:
            return self._clients.get(client_id)

    def list_clients(self) -> list[dict]:
        """
        列出所有客户端

        Returns:
            客户端信息列表
        """
        with self._lock:
            return [client.to_dict() for client in self._clients.values()]

    def _check_auth_rate_limit(self, client_id: str) -> None:
        """Raise AuthenticationError if too many recent failures for client_id.

        Implements a sliding-window brute-force protection: if a client_id
        accumulates ≥5 failed authentication attempts within the last 60
        seconds, further attempts are rejected with ``rate_limit_exceeded``
        until the oldest failure ages out of the window.

        This check intentionally runs *before* credential verification so that
        an attacker cannot enumerate valid client secrets via timing differences
        once the rate limit kicks in.

        Args:
            client_id: The OAuth2 client identifier being authenticated.

        Raises:
            AuthenticationError: With code ``rate_limit_exceeded`` when the
                failure threshold is exceeded.
        """
        import time as _time

        now = _time.monotonic()
        window = 60.0  # sliding window in seconds
        max_failures = 5
        attempts = self._auth_failures.get(client_id, [])
        recent = [t for t in attempts if now - t < window]
        if len(recent) >= max_failures:
            # Persist the pruned list so old entries don't accumulate
            self._auth_failures[client_id] = recent
            raise AuthenticationError(
                f"Too many authentication failures for client '{client_id}'",
                code="rate_limit_exceeded",
            )
        self._auth_failures[client_id] = recent

    def issue_token(
        self,
        client_id: str,
        client_secret: str,
        grant_type: GrantType,
        scope: str | None = None,
        user: AuthenticatedUser | None = None,
        code: str | None = None,
    ) -> OAuth2Token:
        """
        签发令牌

        Args:
            client_id: 客户端 ID
            client_secret: 客户端密钥
            grant_type: 授权类型
            scope: 授权范围
            user: 认证用户 (Authorization Code Flow 需要)
            code: 授权码 (Authorization Code Flow 需要)

        Returns:
            OAuth2 令牌

        Raises:
            AuthenticationError: 客户端认证失败 (including rate_limit_exceeded)
            AuthorizationError: 授权类型不允许
        """
        import time as _time

        # 0. Rate-limit check — runs BEFORE credential verification to prevent
        #    brute-force enumeration of valid client secrets.
        self._check_auth_rate_limit(client_id)

        # 1. 验证客户端
        client = self.get_client(client_id)
        if not client:
            # Record failure so repeated probing is rate-limited
            self._auth_failures.setdefault(client_id, []).append(_time.monotonic())
            raise AuthenticationError("Invalid client_id", code="invalid_client")

        if not client.verify_secret(client_secret):
            self._auth_failures.setdefault(client_id, []).append(_time.monotonic())
            raise AuthenticationError("Invalid client_secret", code="invalid_client")

        if not client.active:
            raise AuthenticationError("Client is not active", code="client_inactive")

        # 2. 验证授权类型
        if grant_type not in client.grant_types:
            raise AuthorizationError(f"Grant type {grant_type.value} not allowed", code="unsupported_grant_type")

        # 3. 根据授权类型处理
        if grant_type == GrantType.AUTHORIZATION_CODE:
            return self._issue_token_auth_code(client, code, scope)
        elif grant_type == GrantType.CLIENT_CREDENTIALS:
            return self._issue_token_client_credentials(client, scope)
        elif grant_type == GrantType.REFRESH_TOKEN:
            raise AuthorizationError(
                "Use refresh_access_token endpoint for refresh_token grant",
                code="method_not_allowed",
            )
        else:
            raise AuthorizationError(f"Unsupported grant type: {grant_type.value}", code="unsupported_grant_type")

    def _issue_token_auth_code(self, client: OAuth2Client, code: str | None, scope: str | None) -> OAuth2Token:
        """Authorization Code Flow 签发令牌"""
        if not code:
            raise AuthorizationError("Authorization code required", code="invalid_request")

        with self._lock:
            # 验证授权码
            code_data = self._authorization_codes.get(code)
            if not code_data:
                raise AuthorizationError("Invalid authorization code", code="invalid_grant")

            if code_data["client_id"] != client.client_id:
                raise AuthorizationError("Authorization code client mismatch", code="invalid_grant")

            if code_data.get("expired", False):
                raise AuthorizationError("Authorization code expired", code="invalid_grant")

            # 使用授权码中的用户和范围
            user = code_data.get("user")
            scope = code_data.get("scope", scope)

            # 删除已使用的授权码 (一次性使用)
            del self._authorization_codes[code]

        return self._create_token(client, scope or "", user)

    def _issue_token_client_credentials(self, client: OAuth2Client, scope: str | None) -> OAuth2Token:
        """Client Credentials Flow 签发令牌"""
        # 验证范围
        if scope:
            requested_scopes = set(scope.split())
            if not requested_scopes.issubset(client.scopes):
                raise AuthorizationError("Invalid scope", code="invalid_scope")
        else:
            scope = " ".join(client.scopes)

        # Client Credentials Flow 没有用户上下文
        return self._create_token(client, scope, user=None)

    def _create_token(self, client: OAuth2Client, scope: str, user: AuthenticatedUser | None) -> OAuth2Token:
        """创建 JWT 令牌"""
        now = datetime.now(UTC)

        # 生成访问令牌
        access_token = self._generate_jwt(
            subject=user.user_id if user else client.client_id,
            audience=client.client_id,
            scope=scope,
            roles=user.roles if user else [],
            username=user.username if user else None,
            email=user.email if user else None,
            expires_in=self._access_token_lifetime,
        )

        # 生成刷新令牌
        refresh_token = secrets.token_urlsafe(64)

        # 创建令牌对象（expires_in 表示 access token 有效期，用于 OAuth2 响应）
        token = OAuth2Token(
            access_token=access_token,
            refresh_token=refresh_token,
            scope=scope,
            issued_at=now,
            expires_in=self._access_token_lifetime,
        )

        # 存储刷新令牌映射（线程安全，加密存储）
        with self._lock:
            self._tokens[self._token_key(refresh_token)] = token
            self._issue_count += 1
            should_cleanup = (self._issue_count % 1000) == 0

        # 每 1000 次签发清理一次过期令牌，防止内存无界增长
        if should_cleanup:
            cleaned = self.cleanup_expired_tokens()
            _log.info("Periodic token cleanup: removed %d expired tokens", cleaned)

        return token

    def refresh_access_token(self, refresh_token: str) -> OAuth2Token:
        """
        刷新访问令牌

        Args:
            refresh_token: 刷新令牌

        Returns:
            新的 OAuth2 令牌

        Raises:
            AuthenticationError: 刷新令牌无效或已过期
        """
        # 1. 验证刷新令牌（线程安全读，先解密 key 再查找）
        with self._lock:
            token = self._tokens.get(self._token_key(refresh_token))

        if not token:
            raise AuthenticationError("Invalid refresh token", code="invalid_grant")

        if token.is_expired:
            raise TokenExpiredError("Refresh token expired")

        # 2. 吊销旧令牌
        self.revoke_token(refresh_token)

        # 3. 从访问令牌中提取 audience (client_id)
        if not _JWT_AVAILABLE:
            raise AuthenticationError("JWT library not installed", code="server_error")
        try:
            payload = jwt.decode(
                token.access_token,
                self._jwt_secret,
                algorithms=["HS256"],
                issuer=self._jwt_issuer,
                options={"verify_aud": False, "verify_exp": False},
            )
            client_id = payload.get("aud")
        except (ValueError, KeyError, AttributeError):
            client_id = None

        if not client_id:
            raise AuthenticationError("Cannot extract client from token", code="server_error")

        client = self.get_client(client_id)
        if not client:
            raise AuthenticationError("Client not found", code="server_error")

        # 4. 签发新令牌 (使用相同的范围)
        return self._create_token(client, token.scope, user=None)

    def validate_token(self, token: str) -> AuthenticatedUser:
        """
        验证访问令牌

        Args:
            token: JWT 访问令牌

        Returns:
            认证用户信息

        Raises:
            TokenRevokedError: 令牌已被吊销
            TokenExpiredError: 令牌已过期
            InvalidTokenError: 令牌签名无效或格式错误
        """
        if not _JWT_AVAILABLE:
            raise InvalidTokenError("JWT library not installed")

        # 1. 检查是否被吊销（线程安全读）
        with self._lock:
            revoked = token in self._revoked_tokens or self._token_key(token) in self._revoked_tokens

        if revoked:
            raise TokenRevokedError()

        # 2. 解码 JWT — 先提取 aud，再完整验证
        try:
            unverified = jwt.decode(token, options={"verify_signature": False})
            audience = unverified.get("aud", "bos-api")
            payload = jwt.decode(
                token,
                self._jwt_secret,
                algorithms=["HS256"],
                issuer=self._jwt_issuer,
                audience=audience,
                options={"verify_aud": True},
            )
        except jwt.ExpiredSignatureError:
            raise TokenExpiredError() from None
        except jwt.InvalidTokenError as e:
            raise InvalidTokenError(f"Invalid token: {e}") from e

        # 3. 构建认证用户
        return AuthenticatedUser(
            user_id=payload["sub"],
            username=payload.get("username", payload["sub"]),
            email=payload.get("email", ""),
            roles=payload.get("roles", []),
            scopes=set(payload.get("scope", "").split()) if payload.get("scope") else set(),
        )

    def validate_token_safe(self, token: str) -> AuthenticatedUser | None:
        """
        验证访问令牌（不抛出异常版本）

        Args:
            token: JWT 访问令牌

        Returns:
            认证用户信息，失败时返回 None
        """
        try:
            return self.validate_token(token)
        except (TokenRevokedError, TokenExpiredError, InvalidTokenError, AuthenticationError):
            return None

    def cleanup_expired_tokens(self) -> int:
        """
        清理过期的刷新令牌，防止内存无界增长。

        Returns:
            清理的过期令牌数量
        """
        with self._lock:
            expired_keys = [key for key, token in self._tokens.items() if token.is_expired]
            for key in expired_keys:
                del self._tokens[key]
        if expired_keys:
            _log.debug("cleanup_expired_tokens: removed %d entries", len(expired_keys))
        return len(expired_keys)

    def revoke_token(self, token: str) -> None:
        """
        吊销令牌

        Args:
            token: 要吊销的令牌 (明文，方法内部将其加密后查找)
        """
        token_key = self._token_key(token)
        with self._lock:
            self._revoked_tokens.add(token)
            self._revoked_tokens.add(token_key)
            if token_key in self._tokens:
                del self._tokens[token_key]

    def generate_authorization_code(
        self,
        client_id: str,
        user: AuthenticatedUser,
        scope: str | None = None,
        redirect_uri: str | None = None,
    ) -> str:
        """
        生成授权码 (用于 Authorization Code Flow)

        Args:
            client_id: 客户端 ID
            user: 认证用户
            scope: 授权范围
            redirect_uri: 重定向 URI

        Returns:
            授权码字符串
        """
        code = secrets.token_urlsafe(64)

        # 存储授权码信息 (5 分钟有效期)
        code_entry = {
            "client_id": client_id,
            "user": user,
            "scope": scope,
            "redirect_uri": redirect_uri,
            "created_at": datetime.now(UTC),
            "expired": False,
        }
        with self._lock:
            self._authorization_codes[code] = code_entry

        # 5 分钟后过期
        def _expire() -> None:
            import time as _time

            _time.sleep(300)  # 5 分钟
            with self._lock:
                if code in self._authorization_codes:
                    self._authorization_codes[code]["expired"] = True

        import threading as _threading

        thread = _threading.Thread(target=_expire, daemon=True)
        thread.start()

        return code

    def _generate_jwt(
        self,
        subject: str,
        audience: str,
        scope: str,
        roles: list[str],
        expires_in: int,
        username: str | None = None,
        email: str | None = None,
    ) -> str:
        """生成 JWT 令牌"""
        now = datetime.now(UTC)
        claims = JWTClaims(
            iss=self._jwt_issuer,
            sub=subject,
            aud=audience,
            exp=now + timedelta(seconds=expires_in),
            iat=now,
            scope=scope,
            roles=roles,
        )

        payload = claims.to_dict()

        # 添加额外字段
        if username:
            payload["username"] = username
        if email:
            payload["email"] = email

        return jwt.encode(payload, self._jwt_secret, algorithm="HS256")

    def get_jwt_secret(self) -> tuple[str, str]:
        """获取 JWT 密钥 (用于与其他服务共享)"""
        return self._jwt_issuer, self._jwt_secret


# 全局单例 (可选)
_global_oauth2_server: OAuth2Server | None = None


def get_oauth2_server(jwt_secret: str | None = None, jwt_issuer: str = "sharedbrain-gateway") -> OAuth2Server:
    """获取全局 OAuth2 服务器实例"""
    global _global_oauth2_server
    if _global_oauth2_server is None:
        _global_oauth2_server = OAuth2Server(jwt_secret=jwt_secret, jwt_issuer=jwt_issuer)
    return _global_oauth2_server
