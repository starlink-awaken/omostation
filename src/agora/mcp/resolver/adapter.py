"""BOS URI StdioAdapter — JSON-RPC over stdio 协议."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Any

from .services import BosService, _with_uv_package

_log = logging.getLogger(__name__)

_STDIO_TIMEOUT_DEFAULT = 10.0


@dataclass
class StdioAdapter:
    """JSON-RPC over stdio 适配器 (P46 W2).

    对 transport='stdio' 保持向后兼容的 {"args":..., "kwargs":...} 自定义 JSON;
    对 transport='mcp_stdio' 发送标准 JSON-RPC 2.0 请求 (tools/call)。
    """

    timeout: float = _STDIO_TIMEOUT_DEFAULT
    _id: int = field(default=0, init=False)

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _build_request(
        self, service: BosService, args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> dict[str, Any]:
        if service.transport == "mcp_stdio":
            return {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": f"{service.package}/{service.action}",
                    "arguments": {"args": args, "kwargs": kwargs},
                },
                "id": self._next_id(),
            }
        return {"args": args, "kwargs": kwargs}

    def _parse_response(self, service: BosService, raw: str) -> dict[str, Any]:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return {"status": "ok", "result": {"raw": raw}}

        if service.transport == "mcp_stdio" and isinstance(payload, dict):
            if "error" in payload:
                return {"status": "error", "error": payload["error"]}
            if "result" in payload:
                return {"status": "ok", "result": payload["result"]}
        return {"status": "ok", "result": payload}

    def call(self, service: BosService, *args: Any, **kwargs: Any) -> dict:
        """通过 stdio 调用 BOS 服务并返回结果."""
        cmd = _with_uv_package(service)
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
            request = json.dumps(self._build_request(service, args, kwargs))
            stdout, stderr = proc.communicate(input=request, timeout=self.timeout)
            if proc.returncode != 0:
                return {
                    "status": "error",
                    "error": stderr or f"exit code {proc.returncode}",
                    "pid": pid,
                    "alive_at_spawn": True,
                }
            result = self._parse_response(service, stdout)
            result["pid"] = pid
            result["alive_at_spawn"] = True
            return result
        except subprocess.TimeoutExpired:
            if proc:
                proc.kill()
            return {
                "status": "error",
                "error": "timeout",
                "pid": proc.pid if proc else None,
                "alive_at_spawn": True,
            }
        except Exception as e:  # noqa: BLE001  # defensive fallback
            return {
                "status": "error",
                "error": str(e),
                "pid": proc.pid if proc else None,
                "alive_at_spawn": True,
            }


_adapter = StdioAdapter()


def get_stdio_adapter(timeout: float = _STDIO_TIMEOUT_DEFAULT) -> StdioAdapter:
    """返回 StdioAdapter 实例；非默认 timeout 时创建独立实例."""
    if timeout == _STDIO_TIMEOUT_DEFAULT:
        return _adapter
    return StdioAdapter(timeout=timeout)
