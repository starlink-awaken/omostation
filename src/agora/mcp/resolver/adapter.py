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
                if self.proc is None or self.proc.stdout is None:
                    q.put(("exc", RuntimeError("Process not running")))
                    return
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

    pool 提供后, mcp_stdio 调用复用常驻子进程 (按 URI), 避免每次 Popen 起新进程;
    pool 为 None 时保持每次 Popen + 用完即关 (向后兼容)。
    """

    timeout: float = _STDIO_TIMEOUT_DEFAULT
    pool: Any | None = None
    _id: int = field(default=0, init=False)
    _sessions: dict[str, _McpStdioSession] = field(default_factory=dict, init=False)
    _session_locks: dict[str, threading.Lock] = field(default_factory=dict, init=False)
    _sessions_guard: threading.Lock = field(default_factory=threading.Lock, init=False)

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _lock_for(self, uri: str) -> threading.Lock:
        with self._sessions_guard:
            lock = self._session_locks.get(uri)
            if lock is None:
                lock = threading.Lock()
                self._session_locks[uri] = lock
            return lock

    def _discard_session(self, uri: str) -> None:
        """丢弃 URI 对应 session, 允许下次重建."""
        with self._sessions_guard:
            self._sessions.pop(uri, None)

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
        if self.pool is not None:
            return self._call_mcp_stdio_pooled(service, args, kwargs)
        return self._call_mcp_stdio_spawn(service, cmd, args, kwargs)

    def _call_mcp_stdio_spawn(
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

    def _call_mcp_stdio_pooled(
        self,
        service: BosService,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        """mcp_stdio 经 ProcessPool 复用常驻子进程 (按 URI)."""
        uri = service.uri
        lock = self._lock_for(uri)
        with lock:
            try:
                proc = self.pool.get_or_spawn(service)
                pid = proc.pid
                session = self._sessions.get(uri)
                if session is None or session.proc is not proc:
                    session = _McpStdioSession(proc, self.timeout)
                    init_resp = session.initialize()
                    if "error" in init_resp:
                        self.pool.shutdown(uri)
                        return {
                            "status": "error",
                            "error": init_resp["error"],
                            "pid": pid,
                            "alive_at_spawn": True,
                        }
                    session.initialized()
                    with self._sessions_guard:
                        self._sessions[uri] = session

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
            except subprocess.TimeoutExpired:
                self.pool.shutdown(uri)
                self._discard_session(uri)
                return {
                    "status": "error",
                    "error": "mcp_stdio_timeout",
                    "pid": None,
                    "alive_at_spawn": True,
                }
            except Exception as e:
                self.pool.shutdown(uri)
                self._discard_session(uri)
                return {
                    "status": "error",
                    "error": str(e),
                    "pid": None,
                    "alive_at_spawn": True,
                }

    def shutdown(self) -> None:
        """关闭并清理所有复用的子进程 (pool 模式)."""
        if self.pool is not None:
            with self._sessions_guard:
                self._sessions.clear()
            self.pool.shutdown()

    def call(self, service: BosService, *args: Any, **kwargs: Any) -> dict:
        """通过合适协议调用 BOS 服务并返回结果.

        F-04: 显式分派所有 transport, 不再让不支持的协议落入 `_call_stdio`
        用错误协议执行 (Popen([]) 等)。
        """
        if service.transport == "mcp_stdio":
            cmd = _with_uv_package(service)
            return self._call_mcp_stdio(service, cmd, args, kwargs)
        if service.transport == "http":
            return self._call_http(service, args, kwargs)
        if service.transport == "mcp_proxy":
            # 无 proxy_manager 上下文时显式降级, 而非 Popen([])
            return {
                "status": "error",
                "transport": "mcp_proxy",
                "error": (
                    "mcp_proxy transport requires ProxyManager context; "
                    f"call {service.uri} via proxy_manager.dispatch()"
                ),
            }
        if service.transport == "inline":
            # inline 为文档锚点或同进程 handler, 无 command 时不可 stdio 调用
            if not service.command:
                return {
                    "status": "error",
                    "transport": "inline",
                    "error": (
                        f"inline service {service.uri} has no command "
                        "(document anchor or in-process handler)"
                    ),
                }
            # 有 command 的 inline 走 stdio 协议
            cmd = _with_uv_package(service)
            return self._call_stdio(service, cmd, args, kwargs)
        cmd = _with_uv_package(service)
        return self._call_stdio(service, cmd, args, kwargs)

    def _call_http(
        self,
        service: BosService,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        """HTTP transport: 对 http_url 发起 GET (或带参数的 POST)。"""
        import urllib.request

        url = service.http_url or service.uri.replace("bos://", "http://", 1)
        try:
            method = "GET"
            payload: bytes | None = None
            data = args[0] if args else kwargs
            if isinstance(data, dict) and data:
                method = "POST"
                payload = json.dumps(data).encode()
            req = urllib.request.Request(
                url,
                data=payload,
                method=method,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode(errors="replace")
                try:
                    parsed = json.loads(body)
                except json.JSONDecodeError:
                    parsed = {"raw": body}
                return {"status": "ok", "result": parsed, "http_status": resp.status}
        except Exception as e:  # noqa: BLE001 — defensive fallback (align with file style)
            return {
                "status": "error",
                "transport": "http",
                "error": f"{type(e).__name__}: {e}",
                "url": url,
            }


_adapter = StdioAdapter()


def get_stdio_adapter(timeout: float = _STDIO_TIMEOUT_DEFAULT) -> StdioAdapter:
    """返回 StdioAdapter 实例；非默认 timeout 时创建独立实例.

    默认实例绑定全局 ProcessPool, 使 mcp_stdio 调用复用常驻子进程。
    """
    if timeout == _STDIO_TIMEOUT_DEFAULT:
        if _adapter.pool is None:
            from .pool import get_pool

            _adapter.pool = get_pool()
        return _adapter
    return StdioAdapter(timeout=timeout)
