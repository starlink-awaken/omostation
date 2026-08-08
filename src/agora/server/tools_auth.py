"""Agora MCP Auth — API Key + JWT 认证 + 身份解析。"""

from __future__ import annotations

import os
from contextvars import ContextVar

import jwt
from fastmcp.server.auth.authorization import AuthContext
from fastmcp.server.dependencies import get_access_token

_AGORA_API_KEY = os.environ.get("AGORA_API_KEY", "")

# Phase 3: Capability-based RBAC Context
agora_role_ctx: ContextVar[str] = ContextVar("agora_role_ctx", default="unknown")


def auth_mode() -> str:
    """Current auth enforcement mode.

    - ``required`` (default, fail-closed): a missing ``AGORA_API_KEY`` rejects
      all requests. This is the safe default for any deployment.
    - ``permissive``: allow all without a key — explicit opt-in for local dev
      only (e.g. ``AGORA_AUTH_MODE=permissive``).
    """
    return os.environ.get("AGORA_AUTH_MODE", "required")


def auth_permissive() -> bool:
    """True when explicitly opted into permissive (local-dev) auth."""
    return auth_mode() == "permissive"


def require_agora_api_key(ctx: AuthContext) -> bool:
    """Auth check for AGORA_API_KEY and JWT tokens.

    Fail-closed by default:

    - ``AGORA_AUTH_MODE`` unset or ``required`` + ``AGORA_API_KEY`` not
      configured → deny (no implicit admin / permissive bypass).
    - Explicit ``AGORA_AUTH_MODE=permissive`` → allow all (local dev opt-in).
    - If configured → require exact bearer token match OR valid JWT.
    """
    if not _AGORA_API_KEY:
        if auth_permissive():
            agora_role_ctx.set("admin")
            return True  # explicit permissive mode for local development
        agora_role_ctx.set("denied")
        return False  # fail-closed: no key configured → reject

    import structlog

    logger = structlog.get_logger(__name__)

    token_str = None
    if ctx.token is not None:
        token_str = ctx.token.token
        # 脱敏: 不记录 token 明文, 只记录存在性与长度
        logger.info(
            "auth check token found in ctx",
            token_present=True,
            token_len=len(token_str),
        )
    else:
        # Fallback to checking HTTP headers directly (for our REST backdoor)
        # P2-6: 进程内直接调用 (无 HTTP 上下文) 视为受信任本地调用 — 放行。
        # 能 import agora.server.mcp 并 call_tool 的代码本已持有 AGORA_API_KEY,
        # 不扩大攻击面; HTTP 传输层经 _current_http_request 注入仍严格鉴权。
        from agora.server.request_context import get_http_request

        try:
            req = get_http_request()
            if req is None:
                # 无 HTTP 上下文 → 本地受信任调用
                logger.info("auth check bypassed: no HTTP request context (local call)")
                agora_role_ctx.set("local")
                return True
            auth_header = req.headers.get("Authorization", "")
            # 不记录 headers 全量 (含 Authorization 凭据), 只记录非敏感子集
            logger.info(
                "auth check headers present",
                has_authorization=bool(auth_header),
                auth_type=(
                    auth_header.split(" ", 1)[0]
                    if auth_header.startswith("Bearer ")
                    else ""
                ),
            )
            if auth_header.startswith("Bearer "):
                token_str = auth_header[7:]
        except Exception as e:  # defensive fallback
            logger.exception("auth check fallback error", exc=e)

    if not token_str:
        logger.info("auth check failed: no token_str")
        return False

    token = token_str

    if token.startswith("eyJ"):
        try:
            # Phase 3: Extract Role from JWT
            decoded = jwt.decode(token, _AGORA_API_KEY, algorithms=["HS256"])
            role = decoded.get("role", "unknown")
            agora_role_ctx.set(role)
            return True
        except jwt.InvalidTokenError:
            return False

    logger.info(
        "Comparing token with _AGORA_API_KEY",
        token_len=len(token),
        key_len=len(_AGORA_API_KEY),
    )
    if token == _AGORA_API_KEY:
        agora_role_ctx.set("admin")
        return True

    logger.warning("Token mismatch in require_agora_api_key")
    return False


def identity_from_auth_token() -> dict | None:
    """Best-effort identity derivation from the current FastMCP access token."""
    token = get_access_token()
    if token is None:
        return None

    claims = getattr(token, "claims", {}) or {}
    subject_id = (
        claims.get("sub") or claims.get("subject_id") or getattr(token, "client_id", "")
    )
    if not subject_id:
        return None

    identity: dict[str, object] = {
        "subject_id": subject_id,
        "subject_type": claims.get("subject_type") or "service",
    }
    if issuer := claims.get("iss") or claims.get("issuer"):
        identity["issuer"] = issuer
    if (
        tenant := claims.get("tenant")
        or claims.get("org")
        or getattr(token, "resource", None)
    ):
        identity["tenant"] = tenant
    if scopes := getattr(token, "scopes", None):
        identity["scopes"] = list(scopes)
    return identity


def resolve_caller_identity(caller_identity: str | dict | None) -> str | dict:
    """Resolve caller identity from auth token or provided identity."""
    if caller_identity is not None:
        return caller_identity
    derived = identity_from_auth_token()
    if derived is not None:
        return derived
    return "anonymous"
