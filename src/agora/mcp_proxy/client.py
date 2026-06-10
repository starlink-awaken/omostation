"""MCP Client — connect to downstream MCP services as an MCP client.

Supports two transports:
- stdio: spawn subprocess, communicate via stdin/stdout JSON-RPC
- HTTP: POST to MCP endpoint via httpx
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from abc import ABC, abstractmethod
from typing import Any

import httpx
import structlog

from agora.core.service_base import is_safe_url  # type: ignore[import-not-found]

logger = structlog.get_logger(__name__)


# ── MCP JSON-RPC helpers ──────────────────────────────────────────


def _make_request(
    method: str, params: dict | None = None, req_id: str | None = None
) -> str:
    """Build a JSON-RPC 2.0 request as JSON string (for stdio transport)."""
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": req_id or str(uuid.uuid4()),
            "method": method,
            "params": params or {},
        },
        ensure_ascii=False,
    )


def _make_request_dict(
    method: str, params: dict | None = None, req_id: str | None = None
) -> dict:
    """Build a JSON-RPC 2.0 request as dict (for HTTP transport via httpx json=)."""
    return {
        "jsonrpc": "2.0",
        "id": req_id or str(uuid.uuid4()),
        "method": method,
        "params": params or {},
    }


def _make_tool_call(tool_name: str, arguments: dict, req_id: str | None = None) -> str:
    return _make_request(
        "tools/call", {"name": tool_name, "arguments": arguments}, req_id
    )


def _make_tool_call_dict(
    tool_name: str, arguments: dict, req_id: str | None = None
) -> dict:
    return _make_request_dict(
        "tools/call", {"name": tool_name, "arguments": arguments}, req_id
    )


def _make_resource_read(uri: str, req_id: str | None = None) -> str:
    return _make_request("resources/read", {"uri": uri}, req_id)


def _make_resource_read_dict(uri: str, req_id: str | None = None) -> dict:
    return _make_request_dict("resources/read", {"uri": uri}, req_id)


_SENSITIVE_ENV_KEYS = frozenset(
    {
        "AGORA_API_KEY",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_ACCESS_KEY_ID",
        "DATABASE_URL",
        "DB_URL",
        "REDIS_URL",
        "REDIS_PASSWORD",
    }
)


def _filter_subprocess_env(custom_env: dict[str, str] | None) -> dict[str, str] | None:
    """Filter sensitive env vars from subprocess environment."""
    if custom_env:
        env = {**os.environ, **custom_env}
    else:
        env = os.environ.copy()
    for key in _SENSITIVE_ENV_KEYS:
        env.pop(key, None)
    return env


# ── Abstract base ────────────────────────────────────────────────


class MCPClient(ABC):
    """Base class for MCP clients that connect to downstream services."""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection and perform MCP initialize handshake."""

    @abstractmethod
    async def disconnect(self):
        """Close the connection."""

    @abstractmethod
    async def list_tools(self) -> list[dict]:
        """Call tools/list and return tool schemas."""

    @abstractmethod
    async def call_tool(self, name: str, arguments: dict) -> Any:
        """Call a tool on the downstream service."""

    @abstractmethod
    async def list_resources(self) -> list[dict]:
        """Call resources/list and return resource schemas."""

    @abstractmethod
    async def read_resource(self, uri: str) -> Any:
        """Call a resource on the downstream service."""

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *_args):
        await self.disconnect()


# ── Stdio transport ──────────────────────────────────────────────


class StdioMCPClient(MCPClient):
    """Connect to an MCP service via stdio subprocess.

    Spawns a subprocess and communicates using MCP JSON-RPC over
    the process's stdin/stdout.
    """

    def __init__(
        self,
        service_name: str,
        command: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        init_timeout: int = 10,
    ):
        super().__init__(service_name)
        self._command = command
        self._args = args or []
        self._cwd = cwd
        self._env = env
        self._init_timeout = init_timeout
        self._process: asyncio.subprocess.Process | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._pending: dict[str, asyncio.Future] = {}
        self._reader_task: asyncio.Task | None = None
        self._req_counter = 0

    def _next_id(self) -> str:
        self._req_counter += 1
        return f"agora-{self.service_name}-{self._req_counter}"

    async def connect(self) -> bool:
        if self._connected:
            return True

        try:
            self._process = await asyncio.create_subprocess_exec(
                self._command,
                *self._args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._cwd,
                env=_filter_subprocess_env(self._env),
                limit=2**20,  # 1MB buffer for large MCP responses
            )
        except FileNotFoundError:
            logger.error(
                "proxy_subprocess_not_found",
                service=self.service_name,
                command=self._command,
            )
            return False
        except Exception as e:
            logger.error(
                "proxy_subprocess_spawn_failed", service=self.service_name, error=str(e)
            )
            return False

        # Start reader loop for processing stdout responses
        self._reader_task = asyncio.create_task(self._read_loop())
        self._writer = self._process.stdin

        # Start stderr drainer to prevent pipe buffer deadlock
        self._stderr_task = asyncio.create_task(self._drain_stderr())

        # Perform MCP initialize handshake
        try:
            result = await self._mcp_initialize()
            if result:
                self._connected = True
                logger.info(
                    "proxy_connected", service=self.service_name, transport="stdio"
                )
                return True
        except Exception as e:
            logger.error(
                "proxy_initialize_failed", service=self.service_name, error=str(e)
            )
            await self.disconnect()
            return False

        return False

    async def disconnect(self):
        self._connected = False
        if self._reader_task:
            self._reader_task.cancel()
            self._reader_task = None
        if self._stderr_task:
            self._stderr_task.cancel()
            self._stderr_task = None
        if self._writer:
            self._writer.close()
        if self._process and self._process.returncode is None:
            self._process.kill()
            await self._process.wait()
        self._process = None
        self._reader = None
        self._writer = None
        for _req_id, fut in self._pending.items():
            if not fut.done():
                fut.set_exception(RuntimeError("Client disconnected"))
        self._pending.clear()

    async def _drain_stderr(self):
        """Drain stderr to prevent pipe buffer deadlock."""
        try:
            while self._process and self._process.stderr:
                line = await self._process.stderr.readline()
                if not line:
                    break
        except (asyncio.CancelledError, Exception):
            pass

    async def _mcp_initialize(self) -> bool:
        """Send initialize request and wait for response, then send initialized notification."""
        req_id = self._next_id()
        fut = asyncio.get_event_loop().create_future()
        self._pending[req_id] = fut

        request = _make_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "agora-proxy", "version": "1.0.0"},
            },
            req_id,
        )
        await self._send(request)

        try:
            response = await asyncio.wait_for(fut, timeout=self._init_timeout)
            if response is None:
                return False
            # Send notifications/initialized to satisfy servers that
            # consume this notification before entering the message loop
            await self._send(
                json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
            )
            return True
        except TimeoutError:
            logger.error("proxy_initialize_timeout", service=self.service_name)
            return False

    async def list_tools(self) -> list[dict]:
        req_id = self._next_id()
        fut = asyncio.get_event_loop().create_future()
        self._pending[req_id] = fut

        await self._send(_make_request("tools/list", req_id=req_id))

        try:
            response = await asyncio.wait_for(fut, timeout=30)
            if response and "result" in response:
                return response["result"].get("tools", [])
            return []
        except TimeoutError:
            logger.error("proxy_list_tools_timeout", service=self.service_name)
            return []

    async def call_tool(self, name: str, arguments: dict) -> Any:
        req_id = self._next_id()
        fut = asyncio.get_event_loop().create_future()
        self._pending[req_id] = fut

        await self._send(_make_tool_call(name, arguments, req_id))

        try:
            response = await asyncio.wait_for(fut, timeout=120)
            if response and "result" in response:
                return response["result"]
            if response and "error" in response:
                return {
                    "status": "error",
                    "error": response["error"].get("message", "Unknown error"),
                }
            return {"status": "error", "error": "Empty response"}
        except TimeoutError:
            return {"status": "error", "error": "Tool call timed out"}

    async def list_resources(self) -> list[dict]:
        req_id = self._next_id()
        fut = asyncio.get_event_loop().create_future()
        self._pending[req_id] = fut

        await self._send(_make_request("resources/list", req_id=req_id))

        try:
            response = await asyncio.wait_for(fut, timeout=30)
            if response and "result" in response:
                return response["result"].get("resources", [])
            return []
        except TimeoutError:
            logger.error("proxy_list_resources_timeout", service=self.service_name)
            return []

    async def read_resource(self, uri: str) -> Any:
        req_id = self._next_id()
        fut = asyncio.get_event_loop().create_future()
        self._pending[req_id] = fut

        await self._send(_make_resource_read(uri, req_id))

        try:
            response = await asyncio.wait_for(fut, timeout=120)
            if response and "result" in response:
                return response["result"]
            if response and "error" in response:
                return {
                    "status": "error",
                    "error": response["error"].get("message", "Unknown error"),
                }
            return {"status": "error", "error": "Empty response"}
        except TimeoutError:
            return {"status": "error", "error": "Resource read timed out"}

    async def _send(self, data: str):
        if self._writer and not self._writer.is_closing():
            self._writer.write((data + "\n").encode("utf-8"))
            await self._writer.drain()

    async def _read_loop(self):
        """Continuously read stdout lines and resolve pending futures."""
        try:
            while self._process and self._process.stdout:
                line = await self._process.stdout.readline()
                if not line:
                    break
                line = line.decode("utf-8").strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue

                req_id = msg.get("id")
                if req_id and req_id in self._pending:
                    fut = self._pending.pop(req_id)
                    if not fut.done():
                        fut.set_result(msg)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(
                "proxy_read_loop_error", service=self.service_name, error=str(e)
            )
        finally:
            for _req_id, fut in self._pending.items():
                if not fut.done():
                    fut.set_exception(RuntimeError("Subprocess disconnected"))
            self._pending.clear()


# ── HTTP/SSE transport ────────────────────────────────────────────


class HttpMCPClient(MCPClient):
    """Connect to an MCP service via HTTP POST.

    The downstream service must expose an MCP-compatible HTTP endpoint
    (e.g., FastMCP with SSE transport).
    """

    def __init__(self, service_name: str, endpoint: str):
        super().__init__(service_name)
        self._endpoint = endpoint.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def connect(self) -> bool:
        if self._connected:
            return True

        self._client = httpx.AsyncClient(
            timeout=30,
            limits=httpx.Limits(max_keepalive_connections=0, max_connections=10),
        )

        # Try MCP initialize handshake first
        connected = False
        try:
            resp = await self._client.post(
                self._endpoint,
                json={
                    "jsonrpc": "2.0",
                    "id": "init",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "agora-proxy", "version": "1.0.0"},
                    },
                },
                timeout=10,
                headers={"Connection": "close"},
            )
            if resp.status_code == 200:
                data = resp.json()
                if "result" in data:
                    connected = True
        except Exception:
            pass

        # Fallback: try tools/list directly (some MCP servers skip initialize)
        if not connected:
            try:
                resp = await self._client.post(
                    self._endpoint,
                    json=_make_request("tools/list"),
                    timeout=10,
                )
                if resp.status_code == 200:
                    connected = True
            except Exception:
                pass

        if connected:
            self._connected = True
            logger.info(
                "proxy_connected",
                service=self.service_name,
                transport="http",
                endpoint=self._endpoint,
            )
            return True

        logger.warning(
            "proxy_http_probe_failed",
            service=self.service_name,
            endpoint=self._endpoint,
        )
        return False

    async def disconnect(self):
        self._connected = False
        if self._client:
            await self._client.aclose()
            self._client = None

    async def list_tools(self) -> list[dict]:
        if not self._client:
            return []

        try:
            resp = await self._client.post(
                self._endpoint,
                json=_make_request_dict("tools/list"),
                timeout=30,
                headers={"Connection": "close"},
            )
            data = resp.json()
            return data.get("result", {}).get("tools", [])
        except Exception as e:
            logger.error(
                "proxy_http_list_tools_failed", service=self.service_name, error=str(e)
            )
            return []

    async def call_tool(self, name: str, arguments: dict) -> Any:
        if not self._client:
            return {"status": "error", "error": "Not connected"}

        try:
            resp = await self._client.post(
                self._endpoint,
                json=_make_tool_call_dict(name, arguments),
                timeout=120,
                headers={"Connection": "close"},
            )
            data = resp.json()
            if "result" in data:
                return data["result"]
            if "error" in data:
                return {
                    "status": "error",
                    "error": data["error"].get("message", "Unknown error"),
                }
            return data
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def list_resources(self) -> list[dict]:
        if not self._client:
            return []
        try:
            resp = await self._client.post(
                self._endpoint,
                json=_make_request_dict("resources/list"),
                timeout=30,
                headers={"Connection": "close"},
            )
            data = resp.json()
            return data.get("result", {}).get("resources", [])
        except Exception as e:
            logger.error(
                "proxy_http_list_resources_failed",
                service=self.service_name,
                error=str(e),
            )
            return []

    async def read_resource(self, uri: str) -> Any:
        if not self._client:
            return {"status": "error", "error": "Not connected"}
        try:
            resp = await self._client.post(
                self._endpoint,
                json=_make_resource_read_dict(uri),
                timeout=120,
                headers={"Connection": "close"},
            )
            data = resp.json()
            if "result" in data:
                return data["result"]
            if "error" in data:
                return {
                    "status": "error",
                    "error": data["error"].get("message", "Unknown error"),
                }
            return data
        except Exception as e:
            return {"status": "error", "error": str(e)}


# ── Factory ────────────────────────────────────────────────────────


def create_client(
    service_name: str,
    endpoint: str,
    command: str = "",
    args: list[str] | None = None,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    init_timeout: int = 10,
) -> MCPClient:
    """Factory: create the right client for a service based on its endpoint.

    Args:
        service_name: Name of the downstream service.
        endpoint: MCP endpoint URL or 'stdio' for stdio transport.
        command: Command for stdio transport (e.g. 'python3').
        args: Arguments for stdio transport.
        cwd: Working directory for the subprocess (stdio only).
        env: Environment variables for the subprocess (stdio only).
        init_timeout: Timeout in seconds for the initialize handshake (default 10).
    """
    if endpoint.startswith("http"):
        if not is_safe_url(endpoint):
            raise ValueError(f"Unsafe endpoint URL for {service_name}: {endpoint}")
        return HttpMCPClient(service_name, endpoint)
    elif endpoint == "stdio" or (not endpoint and command):
        # Treat empty endpoint + command as stdio transport
        return StdioMCPClient(
            service_name,
            command,
            args or [],
            cwd=cwd,
            env=env,
            init_timeout=init_timeout,
        )
    else:
        logger.warning(
            "proxy_unknown_transport", service=service_name, endpoint=endpoint
        )
        raise ValueError(
            f"Cannot create client for {service_name}: endpoint={endpoint!r}, command={command!r}"
        )
