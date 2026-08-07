"""Agora HTTP endpoint 解析 — 统一从 port-registry.yaml (SSOT) 读取。

遗留收敛: web/ 层多处硬编码 ``http://127.0.0.1:7422``。Agora 现以 SSE (:7431)
为唯一常驻服务 (P2-5 双进程统一), /v1/tools/call 在 SSE/HTTP 双模式注册。
默认值指向 SSE; 可用 ``AGORA_HTTP_ENDPOINT`` env 显式覆盖。
"""

from __future__ import annotations

import os
from pathlib import Path

from cockpit.compat import WORKSPACE_ROOT


def _read_agora_sse_port() -> int | None:
    """从主仓 protocols/port-registry.yaml 读取 agora-mcp-sse 端口."""
    try:
        import yaml

        reg = WORKSPACE_ROOT / "protocols" / "port-registry.yaml"
        data = yaml.safe_load(reg.read_text(encoding="utf-8"))
        ports = data.get("ports", data) if isinstance(data, dict) else {}
        if isinstance(ports, dict):
            for p, meta in ports.items():
                if isinstance(meta, dict) and meta.get("name") == "agora-mcp-sse":
                    return int(p)
    except (OSError, ValueError, TypeError):
        pass
    return None


def agora_http_endpoint() -> str:
    """Agora HTTP/SSE 入口端点.

    优先 ``AGORA_HTTP_ENDPOINT`` env; 否则从 port-registry 读 SSE 端口 (7431);
    SSOT 缺失时回退 7431。
    """
    env = os.environ.get("AGORA_HTTP_ENDPOINT", "").strip()
    if env:
        return env
    port = _read_agora_sse_port() or 7431
    return f"http://127.0.0.1:{port}"
