"""Agora MCP Auth — API Key + JWT 认证 + 身份解析。"""

from __future__ import annotations

import os
from contextvars import ContextVar

import jwt
from fastmcp.server.auth.authorization import AuthContext
from fastmcp.server.dependencies import get_access_token

from agora.auth.mcp_auth import MCPAuthError  # type: ignore[import-not-found]

_AGORA_API_KEY = os.environ.get("AGORA_API_KEY", "")

# Phase 3: Capability-based RBAC Context
agora_role_ctx: ContextVar[str] = ContextVar("agora_role_ctx", default="unknown")


def require_agora_api_key(ctx: AuthContext) -> bool:
    """Auth check for AGORA_API_KEY and JWT tokens.

    - If AGORA_API_KEY is not configured → permissive mode (allow all, local dev).
    - If configured → require exact bearer token match OR valid JWT.
    """
    if not _AGORA_API_KEY:
        agora_role_ctx.set("admin")
        return True  # permissive mode for local development

    import structlog

    logger = structlog.get_logger(__name__)

    token_str = None
    if ctx.token is not None:
        token_str = ctx.token.token
        logger.info("auth check token found in ctx", token_str=token_str)
    else:
        # Fallback to checking HTTP headers directly (for our REST backdoor)
        try:
            from fastmcp.server.dependencies import (
                _current_http_request,
                get_http_request,
            )

            try:
                req = _current_http_request.get()
            except LookupError:
                req = get_http_request()
            if req is None:
                raise MCPAuthError(401, "No HTTP request context")
            logger.info("auth check all headers", headers=dict(req.headers))
            auth_header = req.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token_str = auth_header[7:]
            logger.info("auth check auth_header", auth_header=auth_header)
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
