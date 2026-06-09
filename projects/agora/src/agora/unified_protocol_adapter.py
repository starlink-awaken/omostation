"""Unified protocol adapter for MCP/HTTP/WebSocket/A2A protocols.

Extracted from SharedBrain D_Gateway.  Self-contained protocol routing
with auto-detection, version negotiation, and middleware chain.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from enum import Enum, auto
from typing import Any

logger = logging.getLogger(__name__)


class ProtocolType(Enum):
    """Supported protocol types."""

    MCP = auto()
    HTTP = auto()
    WEBSOCKET = auto()
    A2A = auto()


class ProtocolVersion:
    """Protocol version with semver support."""

    def __init__(self, major: int, minor: int, patch: int = 0) -> None:
        self.major = major
        self.minor = minor
        self.patch = patch

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def __ge__(self, other: ProtocolVersion) -> bool:
        if self.major != other.major:
            return self.major > other.major
        if self.minor != other.minor:
            return self.minor > other.minor
        return self.patch >= other.patch


class UnifiedProtocolAdapter:
    """Protocol unification layer for MCP/HTTP/WebSocket adapters.

    Features:
    1. Protocol auto-detection and routing
    2. Schema validation middleware
    3. Protocol version negotiation
    4. Unified request/response format
    """

    CURRENT_VERSION = ProtocolVersion(1, 0, 0)
    MIN_SUPPORTED_VERSION = ProtocolVersion(1, 0, 0)
    RUNTIME_COMPATIBILITY: dict[str, dict[str, str]] = {
        "mcp": {"min_version": "1.0.0", "status": "stable", "adapter": "native"},
        "a2a": {"min_version": "1.0.0", "status": "stable", "adapter": "native"},
        "langgraph": {"min_version": "0.2.0", "status": "validated", "adapter": "a2a"},
        "openai_agents_sdk": {
            "min_version": "0.0.14",
            "status": "validated",
            "adapter": "mcp",
        },
        "semantic_kernel": {
            "min_version": "1.18.0",
            "status": "validated",
            "adapter": "http",
        },
        "crewai": {"min_version": "0.79.0", "status": "experimental", "adapter": "a2a"},
        "haystack": {
            "min_version": "2.7.0",
            "status": "experimental",
            "adapter": "http",
        },
        "microsoft_agent_framework": {
            "min_version": "0.4.0",
            "status": "experimental",
            "adapter": "a2a",
        },
    }
    VERSION_STRATEGY = {
        "policy": "minimum-compatibility-floor",
        "fallback": "best-effort-minor-forward",
        "upgrade": "explicit-semver-gating",
    }

    def __init__(self) -> None:
        self._handlers: dict[ProtocolType, dict[str, Callable]] = {
            ProtocolType.MCP: {},
            ProtocolType.HTTP: {},
            ProtocolType.WEBSOCKET: {},
            ProtocolType.A2A: {},
        }
        self._schema_validators: dict[str, Callable] = {}
        self._middleware_chain: list[Callable] = []

    def register_handler(
        self,
        protocol: ProtocolType,
        endpoint: str,
        handler: Callable,
        version: ProtocolVersion | None = None,
    ) -> None:
        """Register a protocol handler."""
        key = f"{endpoint}:{version or self.CURRENT_VERSION}"
        self._handlers[protocol][key] = handler
        logger.info(
            "[ProtocolAdapter] Registered %s handler: %s", protocol.name, endpoint
        )

    def register_validator(self, schema_name: str, validator: Callable) -> None:
        """Register a schema validator."""
        self._schema_validators[schema_name] = validator

    def add_middleware(self, middleware: Callable) -> None:
        """Add middleware to the processing chain."""
        self._middleware_chain.append(middleware)

    def detect_protocol(self, request_data: dict[str, Any]) -> ProtocolType:
        """Auto-detect protocol type from request."""
        if (
            request_data.get("channel") == "a2a"
            or request_data.get("protocol") == "a2a"
        ):
            return ProtocolType.A2A
        if "target_agent_id" in request_data or "agent_id" in request_data:
            return ProtocolType.A2A
        if "jsonrpc" in request_data:
            return ProtocolType.MCP
        if "headers" in request_data and "method" in request_data:
            return ProtocolType.HTTP
        if "type" in request_data and request_data.get("type") == "websocket":
            return ProtocolType.WEBSOCKET

        # Default to HTTP
        return ProtocolType.HTTP

    async def route_request(
        self,
        request_data: dict[str, Any],
        protocol_hint: ProtocolType | None = None,
    ) -> dict[str, Any]:
        """Route request to appropriate handler."""
        protocol = protocol_hint or self.detect_protocol(request_data)

        # Run middleware
        context = {"protocol": protocol, "request": request_data}
        for middleware in self._middleware_chain:
            try:
                context = (
                    await middleware(context)
                    if inspect.iscoroutinefunction(middleware)
                    else middleware(context)
                )
            except (OSError, ValueError, RuntimeError, KeyError) as e:
                logger.error("[ProtocolAdapter] Middleware error: %s", str(e))
                return self._error_response(str(e), 500)

        # Get endpoint
        endpoint = self._extract_endpoint(request_data, protocol)
        version = self._extract_version(request_data)

        # Find handler
        handler = self._find_handler(protocol, endpoint, version)
        if not handler:
            return self._error_response(f"No handler for {endpoint}", 404)

        # Validate schema if available
        schema_name = request_data.get("schema")
        if schema_name and schema_name in self._schema_validators:
            validator = self._schema_validators[schema_name]
            is_valid = (
                await validator(request_data)
                if inspect.iscoroutinefunction(validator)
                else validator(request_data)
            )
            if not is_valid:
                return self._error_response("Schema validation failed", 400)

        # Execute handler
        try:
            if inspect.iscoroutinefunction(handler):
                result = await handler(request_data)
            else:
                result = handler(request_data)
            return self._success_response(result, protocol)
        except (OSError, ValueError, RuntimeError, KeyError) as e:
            logger.error("[ProtocolAdapter] Handler error: %s", str(e))
            return self._error_response(str(e), 500)

    def _extract_endpoint(
        self, request_data: dict[str, Any], protocol: ProtocolType
    ) -> str:
        """Extract endpoint from request."""
        if protocol == ProtocolType.MCP:
            return request_data.get("method", "")
        if protocol == ProtocolType.HTTP:
            return request_data.get("path", "/")
        if protocol == ProtocolType.A2A:
            return request_data.get("action", "message/send")
        return request_data.get("action", "")

    @staticmethod
    def _version_tuple(version: str) -> tuple[int, int, int]:
        parts = version.split(".")
        major = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
        minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        patch = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        return major, minor, patch

    def supported_protocols(self) -> list[str]:
        """Return stable protocol adapters exposed by this runtime."""
        return [protocol.name.lower() for protocol in self._handlers]

    def compatibility_matrix(self) -> dict[str, Any]:
        """Return runtime compatibility matrix and version strategy."""
        return {
            "protocols": self.supported_protocols(),
            "runtimes": dict(self.RUNTIME_COMPATIBILITY),
            "version_strategy": dict(self.VERSION_STRATEGY),
        }

    def negotiate_runtime(self, runtime: str, runtime_version: str) -> dict[str, Any]:
        """Negotiate runtime compatibility against the registered strategy."""
        key = runtime.strip().lower()
        if key not in self.RUNTIME_COMPATIBILITY:
            return {
                "runtime": key,
                "requested_version": runtime_version,
                "supported": False,
                "reason": "runtime_not_registered",
            }

        row = self.RUNTIME_COMPATIBILITY[key]
        min_version = row["min_version"]
        supported = self._version_tuple(runtime_version) >= self._version_tuple(
            min_version
        )
        return {
            "runtime": key,
            "requested_version": runtime_version,
            "min_version": min_version,
            "adapter": row["adapter"],
            "status": row["status"],
            "supported": supported,
            "reason": "ok" if supported else "version_below_minimum",
        }

    def _extract_version(self, request_data: dict[str, Any]) -> ProtocolVersion:
        """Extract protocol version from request."""
        version_str = request_data.get("version", "1.0.0")
        parts = version_str.split(".")
        return ProtocolVersion(
            major=int(parts[0]) if len(parts) > 0 else 1,
            minor=int(parts[1]) if len(parts) > 1 else 0,
            patch=int(parts[2]) if len(parts) > 2 else 0,
        )

    def _find_handler(
        self, protocol: ProtocolType, endpoint: str, version: ProtocolVersion
    ) -> Callable | None:
        """Find appropriate handler for protocol/endpoint/version."""
        handlers = self._handlers[protocol]

        # Try exact version match
        key = f"{endpoint}:{version}"
        if key in handlers:
            return handlers[key]

        # Try without version
        if endpoint in handlers:
            return handlers[endpoint]

        # Try compatible version
        for handler_key, handler in handlers.items():
            if handler_key.startswith(f"{endpoint}:"):
                return handler

        return None

    def _success_response(self, data: Any, protocol: ProtocolType) -> dict[str, Any]:
        """Build success response."""
        if protocol == ProtocolType.MCP:
            return {"jsonrpc": "2.0", "result": data, "id": 1}
        return {"success": True, "data": data, "version": str(self.CURRENT_VERSION)}

    def _error_response(self, message: str, code: int) -> dict[str, Any]:
        """Build error response."""
        return {
            "success": False,
            "error": {"message": message, "code": code},
            "version": str(self.CURRENT_VERSION),
        }
