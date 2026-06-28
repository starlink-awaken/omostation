"""BOS URI StdioAdapter — JSON-RPC over stdio 协议"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from typing import Any

from .services import BosService, _with_uv_package

_log = logging.getLogger(__name__)

_STDIO_TIMEOUT_DEFAULT = 10.0


@dataclass
class StdioAdapter:
    """JSON-RPC over stdio 适配器 (P46 W2)."""

    timeout: float = _STDIO_TIMEOUT_DEFAULT

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
            request = json.dumps({"args": args, "kwargs": kwargs})
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


_adapter = StdioAdapter()


def get_stdio_adapter(timeout: float = _STDIO_TIMEOUT_DEFAULT) -> StdioAdapter:
    """返回 StdioAdapter 实例；非默认 timeout 时创建独立实例."""
    if timeout == _STDIO_TIMEOUT_DEFAULT:
        return _adapter
    return StdioAdapter(timeout=timeout)
