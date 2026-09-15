"""Web middleware — input validation, rate limiting, error boundaries."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class InputGuardMiddleware(BaseHTTPMiddleware):
    """Enforce input limits on all requests."""

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        # Query string length limit
        if len(request.url.query) > 4096:
            return JSONResponse({"error": "Query string too long (>4KB)"}, status_code=414)
        # Body size limit
        if request.headers.get("content-length"):
            try:
                if int(request.headers["content-length"]) > 65536:
                    return JSONResponse({"error": "Body too large (>64KB)"}, status_code=413)
            except ValueError:
                pass
        # Query param value limits
        for _key, value in request.query_params.items():
            if len(value) > 2048:
                return JSONResponse({"error": "Parameter too long (>2KB)"}, status_code=414)
        return await call_next(request)


class RateLimiter:
    """Simple in-memory token bucket rate limiter."""

    def __init__(self, max_requests: int = 30, window_seconds: float = 60.0) -> None:
        self.max_requests = max_requests
        self.window = window_seconds
        self._buckets: dict[str, list[float]] = {}

    def acquire(self, key: str = "default") -> bool:
        now = time.monotonic()
        if key not in self._buckets:
            self._buckets[key] = []
        cutoff = now - self.window
        self._buckets[key] = [t for t in self._buckets[key] if t > cutoff]
        if len(self._buckets[key]) >= self.max_requests:
            return False
        self._buckets[key].append(now)
        return True


class APIKeyMiddleware(BaseHTTPMiddleware):
    """API key authentication for all /api/ endpoints.

    Set MINERVA_API_KEY env var to enable. If unset, all requests pass through.
    Clients pass key via X-API-Key header or ?api_key= query param.
    """

    _PUBLIC_PATHS = {"/health", "/", "/docs", "/openapi.json"}

    def __init__(self, app: Any, api_key: str | None = None) -> None:
        super().__init__(app)
        self.api_key = api_key or os.environ.get("MINERVA_API_KEY", "")
        if not self.api_key:
            logger.warning(
                "MINERVA_API_KEY not set — ALL API requests will be rejected. Set MINERVA_API_KEY to enable access."
            )

    async def dispatch(self, request: Any, call_next: Any) -> Any:
        # Allow public paths without auth
        if request.url.path in self._PUBLIC_PATHS:
            return await call_next(request)
        # Fail-closed: reject all when no API key configured
        if not self.api_key:
            from minerva.audit_store import log_operation as log_sqlite
            from minerva.shared.audit import audit

            ip = request.client.host if request.client else "unknown"
            audit.auth_failure(path=request.url.path, ip=ip, reason="no_key_configured")
            log_sqlite(
                actor="web", action="auth_failure", resource=request.url.path, result="denied", detail=f"ip={ip}"
            )
            return JSONResponse(
                {"error": "API key not configured. Set MINERVA_API_KEY to enable access."}, status_code=401
            )
        # Protect all API endpoints
        if request.url.path.startswith("/api/"):
            key = request.headers.get("X-API-Key") or request.query_params.get("api_key", "")
            if not key or key != self.api_key:
                from minerva.audit_store import log_operation as log_sqlite
                from minerva.shared.audit import audit

                ip = request.client.host if request.client else "unknown"
                audit.auth_failure(path=request.url.path, ip=ip, reason="invalid_key")
                log_sqlite(
                    actor="web", action="auth_failure", resource=request.url.path, result="denied", detail=f"ip={ip}"
                )
                return JSONResponse({"error": "Invalid or missing API key"}, status_code=401)
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply rate limiting to research endpoints."""

    _TRUSTED_PROXIES = {"127.0.0.1", "::1"}

    def __init__(self, app: Any, limiter: RateLimiter | None = None) -> None:
        super().__init__(app)
        self.limiter = limiter or RateLimiter()

    def _client_ip(self, request: Request) -> str:
        """Get real client IP, respecting trusted proxy headers."""
        client_host = request.client.host if request.client else "unknown"
        if client_host in self._TRUSTED_PROXIES:
            forwarded = request.headers.get("X-Real-IP") or request.headers.get("X-Forwarded-For", "")
            if forwarded:
                return forwarded.split(",")[0].strip()
        return client_host

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        if request.url.path.startswith("/api/research"):
            key = self._client_ip(request)
            if not self.limiter.acquire(key):
                from minerva.audit_store import log_operation as log_sqlite
                from minerva.shared.audit import audit

                audit.rate_limit_hit(ip=key, path=request.url.path)
                log_sqlite(
                    actor="web", action="rate_limit_hit", resource=request.url.path, result="denied", detail=f"ip={key}"
                )
                return JSONResponse(
                    {"error": "Rate limit exceeded. Max 30 requests/min.", "retry_after": 60},
                    status_code=429,
                )
        return await call_next(request)
