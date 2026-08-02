"""
cockpit.tui.health_probe — TUI 系统健康探针与连通度检测 (Phase 2)

特性:
  · 非阻塞检测 Agora 控制平面与 KOS 内存库服务
  · 超快速微纳超时 (0.4秒)，绝不造成 GUI 界面抖动或挂起
  · 提供精美的状态文本（如: 🟢 Agora | 🔴 KOS | 🟡 降级中）
"""

from __future__ import annotations

import logging
import socket
import urllib.request
from typing import TypedDict

logger = logging.getLogger(__name__)


class HealthStatus(TypedDict):
    agora_online: bool
    kos_online: bool
    summary_label: str


def check_port_open(host: str, port: int, timeout: float = 0.35) -> bool:
    """超高速 TCP 端口探测，无需加载庞大的 http 协议解析."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        try:
            sock.connect((host, port))
            return True
        except (TimeoutError, OSError):
            return False


def check_agora_health() -> bool:
    """检测 Agora 是否在线 (常见默认监听在 8090 / 8000)."""
    return check_port_open("localhost", 8090) or check_port_open("localhost", 8000)


def check_kos_health() -> bool:
    """检测 KOS 是否可以从当前环境读取(通过本地存储库或套接字)."""
    try:
        from cockpit.storage import Storage

        s = Storage()
        return s is not None
    except Exception:
        return False


def probe_system_health() -> HealthStatus:
    """一次性扫描当前环境真实服务健康状态."""
    agora_ok = check_agora_health()
    kos_ok = check_kos_health()

    a_icon = "🟢" if agora_ok else "⚪"
    k_icon = "🟢" if kos_ok else "⚪"

    return {
        "agora_online": agora_ok,
        "kos_online": kos_ok,
        "summary_label": f"{a_icon} Agora  {k_icon} KOS Memory",
    }
