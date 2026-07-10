"""BOS URI StdioAdapter — JSON-RPC over stdio 协议."""

from __future__ import annotations

import json
import logging
import queue
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Any

from .services import BosService, _with_uv_package

_log = logging.getLogger(__name__)

_STDIO_TIMEOUT_DEFAULT = 10.0


class _McpStdioSession:
    """最小 MCP stdio client session.

    实现 initialize / initialized / tools/call 三步握手。
    目前按行读取 JSON-RPC 消息 (MCP stdio 标准传输格式)。
    """

    def __init__(self, proc: subprocess.Popen, timeout: float) -> None:
        self.proc = proc
        self.timeout = timeout
        self._id = 0

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _send(self, msg: dict[str, Any]) -> None:
        line = json.dumps(msg)
        if self.proc.stdin is None:
            raise RuntimeError("mcp_stdio stdin not available")
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()

    def _recv(self) -> dict[str, Any]:
        """读取一行 JSON-RPC 响应，带跨平台超时。"""
        if self.proc.stdout is None:
            raise RuntimeError("mcp_stdio stdout not available")

        q: queue.Queue[tuple[str, Any]] = queue.Queue()

        def _read() -> None:
            try:
                line = self.proc.stdout.readline()
                q.put(("line", line))
            except Exception as exc:
                q.put(("exc", exc))

        t = threading.Thread(target=_read, daemon=True)
        t.start()
        try:
            kind, value = q.get(timeout=self.timeout)
        except queue.Empty as exc:
            raise subprocess.TimeoutExpired(self.proc.args, self.timeout) from exc

        if kind == "exc":
            raise value
        line = value
        if not line:
            raise RuntimeError("mcp_stdio server closed stdout before response")
        try:
            return json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"invalid JSON-RPC from mcp_stdio: {line[:200]}"
            ) from exc

    def initialize(self) -> dict[str, Any]:
        self._send(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "agora-bos-resolver", "version": "1.0"},
                },
            }
        )
        return self._recv()

    def initialized(self) -> None:
        self._send(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
        )

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self._send(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        return self._recv()

    def close(self) -> None:
        if self.proc.stdin is not None:
            self.proc.stdin.close()
        # MCP server 通常等 stdin EOF 才退出，所以这里主动 terminate。
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=2.0)


@dataclass
class StdioAdapter:
    """JSON-RPC over stdio 适配器 (P46 W2).

    对 transport='stdio' 保持向后兼容的 {"args":..., "kwargs":...} 自定义 JSON;
    对 transport='mcp_stdio' 走完整 MCP initialize / initialized / tools/call session。
    """

    timeout: float = _STDIO_TIMEOUT_DEFAULT
    _id: int = field(default=0, init=False)

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _build_stdio_request(
        self, args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> dict[str, Any]:
        return {"args": args, "kwargs": kwargs}

    def _call_stdio(
        self,
        service: BosService,
        cmd: list[str],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        proc: subprocess.Popen | None = None
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            pid = proc.pid
            request = json.dumps(self._build_stdio_request(args, kwargs))
            stdout, stderr = proc.communicate(input=request, timeout=self.timeout)
            if proc.returncode != 0:
                return {
                    "status": "error",
                    "error": stderr or f"exit code {proc.returncode}",
                    "pid": pid,
                    "alive_at_spawn": True,
                }
            try:
                result = json.loads(stdout)
            except json.JSONDecodeError:
                result = {"raw": stdout}
            return {
                "status": "ok",
                "result": result,
                "pid": pid,
                "alive_at_spawn": True,
            }
        except subprocess.TimeoutExpired:
            if proc:
                proc.kill()
            return {
                "status": "error",
                "error": "timeout",
                "pid": proc.pid if proc else None,
                "alive_at_spawn": True,
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "pid": proc.pid if proc else None,
                "alive_at_spawn": True,
            }

    def _call_mcp_stdio(
        self,
        service: BosService,
        cmd: list[str],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        proc: subprocess.Popen | None = None
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            pid = proc.pid
            session = _McpStdioSession(proc, self.timeout)

            try:
                init_resp = session.initialize()
                if "error" in init_resp:
                    return {
                        "status": "error",
                        "error": init_resp["error"],
                        "pid": pid,
                        "alive_at_spawn": True,
                    }

                session.initialized()

                tool_resp = session.call_tool(
                    f"{service.package}/{service.action}",
                    {"args": args, "kwargs": kwargs},
                )

                if "error" in tool_resp:
                    return {
                        "status": "error",
                        "error": tool_resp["error"],
                        "pid": pid,
                        "alive_at_spawn": True,
                    }
                return {
                    "status": "ok",
                    "result": tool_resp.get("result"),
                    "pid": pid,
                    "alive_at_spawn": True,
                }
            finally:
                session.close()
        except subprocess.TimeoutExpired:
            if proc:
                proc.kill()
            return {
                "status": "error",
                "error": "mcp_stdio_timeout",
                "pid": proc.pid if proc else None,
                "alive_at_spawn": True,
            }
        except Exception as e:
            if proc and proc.poll() is None:
                proc.kill()
                proc.wait(timeout=2.0)
            return {
                "status": "error",
                "error": str(e),
                "pid": proc.pid if proc else None,
                "alive_at_spawn": True,
            }

    def call(self, service: BosService, *args: Any, **kwargs: Any) -> dict:
        """通过 stdio 调用 BOS 服务并返回结果."""
        cmd = _with_uv_package(service)
        if service.transport == "mcp_stdio":
            return self._call_mcp_stdio(service, cmd, args, kwargs)
        return self._call_stdio(service, cmd, args, kwargs)


_adapter = StdioAdapter()


def get_stdio_adapter(timeout: float = _STDIO_TIMEOUT_DEFAULT) -> StdioAdapter:
    """返回 StdioAdapter 实例；非默认 timeout 时创建独立实例."""
    if timeout == _STDIO_TIMEOUT_DEFAULT:
        return _adapter
    return StdioAdapter(timeout=timeout)
