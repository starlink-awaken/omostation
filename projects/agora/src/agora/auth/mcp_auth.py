from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Mcp Auth ≡ Module
# 内涵 ≝ {Mcp, Auth}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, McpAuth)}
# 功能 ⊢ {Mcp_Auth, Init_Mcp, Validate_Auth}
# =============================================================================

# ---
# domain: D-Gateway
# layer: organ
# status: active
# ---
"""
Bearer Token Authentication Middleware for MCP Server.

Provides JWT-like token validation with TTL expiration checking
for SharedBrain SOVEREIGN_KEY based authentication.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from typing import Any

_log = logging.getLogger(__name__)

# Default token TTL: 24 hours
_DEFAULT_TOKEN_TTL = 86400


class MCPAuthError(Exception):
    """Authentication error with JSON-RPC compatible error code."""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class MCPAuthMiddleware:
    """
    Bearer Token authentication middleware for MCP Server.

    Validates Bearer tokens against SHAREDBRAIN_SOVEREIGN_KEY using HMAC-SHA256.
    Tokens include expiration timestamp for TTL enforcement.
    """

    # Authentication error codes (extend JSON-RPC range)
    ERR_UNAUTHORIZED = -32001
    ERR_INVALID_TOKEN = -32002
    ERR_TOKEN_EXPIRED = -32003

    def __init__(self, sovereign_key: str | None = None, token_ttl: int = _DEFAULT_TOKEN_TTL) -> None:
        """
        Initialize authentication middleware.

        Args:
            sovereign_key: The SHAREDBRAIN_SOVEREIGN_KEY for token validation.
                          If None, will be loaded from SHAREDBRAIN_SOVEREIGN_KEY.
            token_ttl: Token time-to-live in seconds (default: 24 hours).
        """
        self._sovereign_key = sovereign_key
        self._token_ttl = token_ttl

    def _get_sovereign_key(self) -> str:
        """Get the sovereign key from env or cached value."""
        if self._sovereign_key is None:
            self._sovereign_key = os.environ.get(
                "SHAREDBRAIN_SOVEREIGN_KEY",
                "sharedbrain-default-key",
            )
        return self._sovereign_key

    def _validate_bearer_token(self, auth_header: str | None) -> dict[str, Any]:
        """
        Validate a Bearer token and return its payload.

        Token format: "Bearer <payload.signature>"
        Payload format: {"exp": <timestamp>, "nonce": <random_string>}
        Signature: HMAC-SHA256(payload, sovereign_key)

        Args:
            auth_header: The Authorization header value.

        Returns:
            The token payload dictionary.

        Raises:
            MCPAuthError: If token is invalid, malformed, or expired.
        """
        if not auth_header:
            raise MCPAuthError(self.ERR_UNAUTHORIZED, "Missing Authorization header")

        if not auth_header.startswith("Bearer "):
            raise MCPAuthError(self.ERR_UNAUTHORIZED, "Invalid authorization type (expected Bearer)")

        token = auth_header[7:].strip()  # Remove "Bearer " prefix
        if not token:
            raise MCPAuthError(self.ERR_INVALID_TOKEN, "Empty token")

        try:
            # Split token into payload and signature
            if "." not in token:
                raise MCPAuthError(self.ERR_INVALID_TOKEN, "Malformed token (missing signature)")

            payload_b64, signature_b64 = token.rsplit(".", 1)

            # Verify signature FIRST (using original payload_b64 without padding)
            sovereign_key = self._get_sovereign_key()
            expected_sig = self._sign_payload(payload_b64, sovereign_key)
            if not hmac.compare_digest(signature_b64, expected_sig):
                raise MCPAuthError(self.ERR_INVALID_TOKEN, "Invalid token signature")

            # Decode payload (base64url)
            # Add padding if needed for decoding
            payload_b64_padded = payload_b64 + "=" * (-len(payload_b64) % 4)
            payload_json = base64.b64decode(payload_b64_padded)
            payload = json.loads(payload_json)

            # Check expiration
            exp = payload.get("exp")
            if exp is None:
                raise MCPAuthError(self.ERR_INVALID_TOKEN, "Token missing expiration")

            if time.time() > exp:
                raise MCPAuthError(self.ERR_TOKEN_EXPIRED, f"Token expired at {time.ctime(exp)}")

            return payload

        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            _log.debug("[MCPAuth] Token decode error: %s", exc)
            raise MCPAuthError(self.ERR_INVALID_TOKEN, f"Malformed token: {exc}") from exc

    def _sign_payload(self, payload_b64: str, key: str) -> str:
        """Create HMAC-SHA256 signature for base64url-encoded payload."""
        signature = hmac.new(key.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
        # Return base64url-encoded signature (without padding)
        return base64.b64encode(signature).decode("utf-8").rstrip("=")

    def generate_token(self, nonce: str | None = None, ttl: int | None = None) -> str:
        """
        Generate a new Bearer token.

        Args:
            nonce: Optional random nonce for uniqueness.
            ttl: Optional time-to-live override (uses default if not specified).

        Returns:
            A Bearer token string (without "Bearer " prefix).
        """
        sovereign_key = self._get_sovereign_key()
        ttl = ttl if ttl is not None else self._token_ttl

        payload = {
            "exp": int(time.time()) + ttl,
            "nonce": nonce or secrets.token_hex(16),
        }

        payload_json = json.dumps(payload, separators=(",", ":"))
        payload_b64 = base64.b64encode(payload_json.encode()).decode().rstrip("=")

        signature = self._sign_payload(payload_b64, sovereign_key)

        return f"{payload_b64}.{signature}"

    def authenticate_request(self, headers: dict[str, str]) -> dict[str, Any]:
        """
        Authenticate an incoming MCP request.

        Args:
            headers: The HTTP request headers dictionary.

        Returns:
            The validated token payload.

        Raises:
            MCPAuthError: If authentication fails.
        """
        auth_header = headers.get("Authorization")
        payload = self._validate_bearer_token(auth_header)

        _log.info(
            "[MCPAuth] Authentication successful: nonce=%s, exp=%s",
            payload.get("nonce", "unknown"),
            time.ctime(payload["exp"]),
        )

        return payload


# Singleton instance for the application
_auth_middleware: MCPAuthMiddleware | None = None


def get_auth_middleware(token_ttl: int = _DEFAULT_TOKEN_TTL) -> MCPAuthMiddleware:
    """Get or create the global authentication middleware instance."""
    global _auth_middleware
    if _auth_middleware is None:
        _auth_middleware = MCPAuthMiddleware(token_ttl=token_ttl)
    return _auth_middleware
