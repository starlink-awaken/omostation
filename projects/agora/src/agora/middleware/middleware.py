"""Middleware modules for agentmesh gateway migration.

Provides API key authentication and request logging middleware.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from agora.types import AgentMessage  # type: ignore[import-not-found]


class APIKeyAuthMiddleware:
    """API key authentication middleware.

    Checks X-API-Key header against the configured API_KEY.
    Skips auth for health check endpoints.
    """

    def __init__(self, api_key: str | None = None, skip_paths: set[str] | None = None) -> None:
        self._api_key = api_key or os.environ.get("API_KEY", "")
        self._skip_paths = skip_paths or {"/health", "/healthz"}
        env_skip = os.environ.get("API_KEY_SKIP_PATHS", "")
        if env_skip:
            self._skip_paths.update(p.strip() for p in env_skip.split(",") if p.strip())

    @property
    def is_configured(self) -> bool:
        """Whether an API key is set."""
        return bool(self._api_key)

    def authenticate(self, request_path: str, headers: dict[str, str]) -> str | None:
        """Authenticate a request.

        Returns None if authorized, or an error message string if denied.
        """
        if not self._api_key:
            return "Service not configured: missing API_KEY"
        if request_path in self._skip_paths:
            return None
        provided = headers.get("x-api-key") or headers.get("X-Api-Key") or ""
        if provided != self._api_key:
            return "Unauthorized: missing or invalid API key"
        return None


class LoggingMiddleware:
    """Request/response logging middleware."""

    def __init__(self, logger: Any | None = None) -> None:
        self._logger = logger or logging.getLogger(__name__)

    async def on_request(self, message: AgentMessage) -> AgentMessage:
        """Log incoming request."""
        self._logger.info(
            "Request: source=%s target=%s type=%s",
            message.source,
            message.target,
            message.type,
        )
        return message

    async def on_response(self, message: AgentMessage) -> AgentMessage:
        """Log outgoing response."""
        status = "ok" if message.error is None else f"error:{message.error.code}"
        self._logger.info(
            "Response: source=%s target=%s status=%s",
            message.source,
            message.target,
            status,
        )
        return message

try:
    from fastmcp.server.middleware import Middleware
    
    class FastMCPAuditMiddleware(Middleware):
        """Audit middleware for FastMCP tool calls."""
        
        def __init__(self, logger: Any | None = None) -> None:
            import structlog
            self._logger = logger or structlog.get_logger("agora.audit")

        async def _apply_shield_and_cleanup(self, result: Any, target_name: str) -> Any:
            has_contents = hasattr(result, "contents")
            has_content = hasattr(result, "content")
            if not has_contents and not has_content:
                return result
                
            items = getattr(result, "contents", None) if has_contents else getattr(result, "content", None)
            if not isinstance(items, list):
                return result
                
            MAX_LEN = 10000
            for item in items:
                if hasattr(item, "text") and item.text and len(item.text) > MAX_LEN:
                    self._logger.warning("mcp_payload_truncated", target=target_name, length=len(item.text))
                    import uuid
                    import os
                    import json
                    import time
                    import random
                    
                    cache_id = str(uuid.uuid4())
                    cache_dir = os.path.expanduser("~/Workspace/LADS/agora_cache")
                    os.makedirs(cache_dir, exist_ok=True)
                    
                    # Probabilistic TTL cleanup (5% chance to run)
                    if random.random() < 0.05:
                        try:
                            now = time.time()
                            for fname in os.listdir(cache_dir):
                                fpath = os.path.join(cache_dir, fname)
                                if os.path.isfile(fpath) and (now - os.path.getmtime(fpath) > 86400):
                                    os.remove(fpath)
                        except Exception as ce:
                            self._logger.warning("mcp_cache_cleanup_error", error=str(ce))
                    
                    cache_path = os.path.join(cache_dir, f"{cache_id}.json")
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump({"target": target_name, "full_text": item.text}, f)
                        
                    truncated_text = item.text[:MAX_LEN] + f"\n\n...[TRUNCATED: Payload exceeded {MAX_LEN} chars. To read the rest, use read_resource('bos://agora/cache/{cache_id}?page=2')]..."
                    item.text = truncated_text
                    
            return result

        async def on_call_tool(self, context: Any, call_next: Any) -> Any:
            from structlog.contextvars import bind_contextvars
            # Extract Trace ID from MCP metadata
            meta = getattr(context.request, "meta", {}) or {}
            agent_id = meta.get("x-agent-id", "anonymous")
            conv_id = meta.get("x-conversation-id", "none")
            bind_contextvars(agent_id=agent_id, conversation_id=conv_id)
            
            try:
                # FastMCP context.request is CallToolRequestParams which has 'name' and 'arguments'
                tool_name = context.request.name
                args = context.request.arguments
                self._logger.info("mcp_tool_call", tool=tool_name, arguments=args)
                result = await call_next(context)
                
                # Context Window Shield
                result = await self._apply_shield_and_cleanup(result, f"tool:{tool_name}")
                
                self._logger.info("mcp_tool_success", tool=tool_name)
                return result
            except Exception as e:
                # fallback if context doesn't have request.name
                tool_name = getattr(getattr(context, "request", None), "name", "unknown")
                self._logger.error("mcp_tool_error", tool=tool_name, error=str(e))
                raise

        async def on_read_resource(self, context: Any, call_next: Any) -> Any:
            from structlog.contextvars import bind_contextvars
            # Extract Trace ID from MCP metadata
            meta = getattr(context.request, "meta", {}) or {}
            agent_id = meta.get("x-agent-id", "anonymous")
            conv_id = meta.get("x-conversation-id", "none")
            bind_contextvars(agent_id=agent_id, conversation_id=conv_id)
            
            uri = getattr(context.request, "uri", "unknown")
            self._logger.info("mcp_read_resource", uri=uri)
            try:
                result = await call_next(context)
                
                # Context Window Shield
                result = await self._apply_shield_and_cleanup(result, f"uri:{uri}")
                
                return result
            except Exception as e:
                self._logger.error("mcp_read_error", uri=uri, error=str(e))
                raise
except ImportError:
    pass

