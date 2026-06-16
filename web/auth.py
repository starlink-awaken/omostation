"""Unified authentication for cockpit.

Supports multiple auth methods:
- API Key (X-API-Key header)
- Bearer token (Authorization: Bearer <token>)
- Session cookie (for web dashboard)

All sub-services are proxied through cockpit's auth.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path

# Auth configuration
AUTH_CONFIG = {
    "api_key": os.environ.get("COCKPIT_API_KEY", os.environ.get("AGORA_API_KEY", "")),
    "bearer_secret": os.environ.get("COCKPIT_BEARER_SECRET", ""),
    "session_ttl": int(os.environ.get("COCKPIT_SESSION_TTL", "3600")),  # 1 hour
    "require_auth": os.environ.get("COCKPIT_REQUIRE_AUTH", "false").lower() == "true",
}

# In-memory session store (for development)
_sessions: dict[str, dict] = {}


def _hash_token(token: str) -> str:
    """Hash a token for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(user: str = "admin", ttl: int | None = None) -> dict:
    """Create a new session."""
    ttl = ttl or AUTH_CONFIG["session_ttl"]
    token = secrets.token_urlsafe(32)
    session = {
        "token": token,
        "user": user,
        "created_at": time.time(),
        "expires_at": time.time() + ttl,
    }
    _sessions[_hash_token(token)] = session
    return session


def validate_session(token: str) -> dict | None:
    """Validate a session token."""
    hashed = _hash_token(token)
    session = _sessions.get(hashed)
    if not session:
        return None
    if time.time() > session["expires_at"]:
        del _sessions[hashed]
        return None
    return session


def revoke_session(token: str) -> bool:
    """Revoke a session."""
    hashed = _hash_token(token)
    if hashed in _sessions:
        del _sessions[hashed]
        return True
    return False


def validate_api_key(provided_key: str) -> bool:
    """Validate an API key."""
    expected = AUTH_CONFIG["api_key"]
    if not expected:
        return True  # No key configured = permissive
    return hmac.compare_digest(provided_key, expected)


def validate_bearer_token(token: str) -> bool:
    """Validate a bearer token."""
    secret = AUTH_CONFIG["bearer_secret"]
    if not secret:
        return True  # No secret configured = permissive
    return hmac.compare_digest(token, secret)


def get_auth_status() -> dict:
    """Get current auth configuration status."""
    return {
        "api_key_configured": bool(AUTH_CONFIG["api_key"]),
        "bearer_secret_configured": bool(AUTH_CONFIG["bearer_secret"]),
        "require_auth": AUTH_CONFIG["require_auth"],
        "active_sessions": len(_sessions),
        "session_ttl": AUTH_CONFIG["session_ttl"],
    }


def extract_auth_from_request(request) -> dict:
    """Extract auth info from a request."""
    # Check API key
    api_key = request.headers.get("X-API-Key", "")
    if api_key:
        return {"method": "api_key", "valid": validate_api_key(api_key)}

    # Check Bearer token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        return {"method": "bearer", "valid": validate_bearer_token(token)}

    # Check session cookie
    session_token = request.cookies.get("cockpit_session", "")
    if session_token:
        session = validate_session(session_token)
        return {"method": "session", "valid": session is not None, "user": session.get("user") if session else None}

    # No auth provided — fail-closed if API key is configured
    if AUTH_CONFIG["api_key"]:
        return {"method": "none", "valid": False}

    # No auth configured — permissive
    return {"method": "none", "valid": not AUTH_CONFIG["require_auth"]}
