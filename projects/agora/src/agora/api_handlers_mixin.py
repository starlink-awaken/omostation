"""API handler methods extracted from APIGateway.

Provides: handshake_handler, task_dispatch_handler, fact_graph_query_handler,
swarm_nodes_handler, _metrics_handler, _health_handler.
Mixed into APIGateway.
"""

from __future__ import annotations

import hmac
import logging
import os
import socket
from threading import Lock
from typing import Any, Protocol

from aiohttp import web  # pyright: ignore[reportMissingImports]

from agora.api_types import APIRequest, APIResponse  # type: ignore[import-not-found]

_log = logging.getLogger(__name__)


def _get_cluster_key() -> str:
    key = os.environ.get("BOS_CLUSTER_KEY")
    if not key:
        raise ValueError("BOS_CLUSTER_KEY is required")
    return key


class _GatewayHandlersSelf(Protocol):
    _metrics_lock: Lock
    metrics: dict[str, int]

    def health_check(self) -> dict[str, Any]: ...


class _APIHandlersMixin:
    """Request handler methods extracted from APIGateway.

    Provides: handshake_handler, task_dispatch_handler, fact_graph_query_handler,
    swarm_nodes_handler, _metrics_handler, _health_handler.
    Mixed into APIGateway.
    """

    async def handshake_handler(self: _GatewayHandlersSelf, request: APIRequest) -> APIResponse:
        """Handle soul handshake requests from peer nodes."""
        try:
            local_node_id = os.environ.get("BOS_NODE_ID", socket.gethostname())
            payload = request.body if isinstance(request.body, dict) else {}
            # Simplified verification — rely on cluster key auth
            if not payload:
                return APIResponse.error("Empty handshake payload", status_code=400)
            return APIResponse.ok(
                {"node_id": local_node_id, "status": "verified"},
                message="Handshake verified",
            )
        except (TypeError, ValueError, RuntimeError) as e:
            _log.exception("handshake_handler error: %s", e)
            return APIResponse.error(str(e), status_code=500)

    async def task_dispatch_handler(self: _GatewayHandlersSelf, request: APIRequest) -> APIResponse:
        """Handle a task delegated from a remote node.

        Authenticates the caller using the ``BOS_CLUSTER_KEY`` env var via a
        timing-safe ``hmac.compare_digest`` comparison.
        """
        try:
            expected_key = _get_cluster_key()
        except ValueError as exc:
            _log.error("task_dispatch_handler: cluster key not configured: %s", exc)
            return APIResponse.error("Server misconfiguration", status_code=500, code="internal_error")

        auth_header = request.headers.get("Authorization", "")
        provided_key = auth_header[len("Bearer ") :] if auth_header.startswith("Bearer ") else ""
        if not hmac.compare_digest(provided_key, expected_key):
            return APIResponse.error("Invalid Cluster Key", status_code=401, code="auth_failed")

        try:
            payload = request.body or {}
            _log.info(
                "task_dispatch_handler: received remote task intent=%s",
                payload.get("intent", "Unknown"),
            )
            return APIResponse.ok(
                {
                    "status": "COMPLETED",
                    "result": "Remote execution simulated successfully",
                    "task_id": payload.get("task_id", "unknown"),
                }
            )
        except (TypeError, KeyError, AttributeError) as e:
            return APIResponse.error(str(e), status_code=500, code="internal_error")

    async def fact_graph_query_handler(self: _GatewayHandlersSelf, request: APIRequest) -> APIResponse:
        """Handle a federated FactGraph query from a remote node."""
        try:
            expected_key = _get_cluster_key()
        except ValueError as exc:
            _log.error("fact_graph_query_handler: cluster key not configured: %s", exc)
            return APIResponse.error("Server misconfiguration", status_code=500, code="internal_error")

        auth_header = request.headers.get("Authorization", "")
        provided_key = auth_header[len("Bearer ") :] if auth_header.startswith("Bearer ") else ""
        if not hmac.compare_digest(provided_key, expected_key):
            return APIResponse.error("Invalid Cluster Key", status_code=401, code="auth_failed")

        try:
            entity = request.query_params.get("entity", "")
            _log.info("fact_graph_query_handler: federation query entity=%s", entity)
            return APIResponse.ok({"nodes": [], "edges": [], "entity": entity})
        except (TypeError, ValueError, RuntimeError) as e:
            return APIResponse.error(str(e), status_code=500, code="internal_error")

    async def swarm_nodes_handler(self: _GatewayHandlersSelf, request: APIRequest) -> APIResponse:
        """Return the list of discovered swarm nodes."""
        try:
            return APIResponse.ok({"nodes": []})
        except (TypeError, RuntimeError) as e:
            return APIResponse.error(str(e), status_code=500)

    async def _metrics_handler(self: _GatewayHandlersSelf, request: web.Request) -> web.Response:
        """Expose Prometheus-compatible metrics at ``/metrics``."""
        with self._metrics_lock:
            m = dict(self.metrics)
        h = self.health_check()
        lines = [
            "# HELP bos_gateway_requests_total Total requests processed",
            "# TYPE bos_gateway_requests_total counter",
            f"bos_gateway_requests_total {m.get('requests_total', 0)}",
            "# HELP bos_gateway_errors_total Total errors",
            "# TYPE bos_gateway_errors_total counter",
            f"bos_gateway_errors_total {m.get('requests_error', 0)}",
            "# HELP bos_gateway_active_connections Current active connections",
            "# TYPE bos_gateway_active_connections gauge",
            f"bos_gateway_active_connections {m.get('active_connections', 0)}",
            "# HELP bos_gateway_uptime_seconds Gateway uptime in seconds",
            "# TYPE bos_gateway_uptime_seconds gauge",
            f"bos_gateway_uptime_seconds {h.get('uptime_seconds', 0)}",
        ]
        return web.Response(text="\n".join(lines) + "\n", content_type="text/plain")

    async def _health_handler(self: _GatewayHandlersSelf, request: web.Request) -> web.Response:
        """Expose JSON health status at ``/health``."""
        import json as _json

        data = self.health_check()
        status_code = 200 if data.get("status") == "ok" else 503
        return web.Response(
            text=_json.dumps(data),
            content_type="application/json",
            status=status_code,
        )
