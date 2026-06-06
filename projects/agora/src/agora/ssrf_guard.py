"""SSRF防护 — 验证外部端点URL不指向内部/私有地址。"""

import ipaddress
from urllib.parse import urlparse

# 私有/内网地址范围
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),       # RFC 1918
    ipaddress.ip_network("172.16.0.0/12"),    # RFC 1918
    ipaddress.ip_network("192.168.0.0/16"),   # RFC 1918
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local (含云元数据)
    ipaddress.ip_network("127.0.0.0/8"),      # Loopback
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
    ipaddress.ip_network("0.0.0.0/8"),        # Current network (invalid target)
    ipaddress.ip_network("100.64.0.0/10"),    # CGNAT (RFC 6598)
    ipaddress.ip_network("192.0.0.0/24"),     # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),     # TEST-NET-1
    ipaddress.ip_network("198.18.0.0/15"),    # Benchmark testing
    ipaddress.ip_network("198.51.100.0/24"),  # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),   # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),      # Multicast
    ipaddress.ip_network("240.0.0.0/4"),      # Reserved
]


def _is_private_ip(host: str) -> bool:
    """检查IP地址是否为私有/内网地址。"""
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    for net in _PRIVATE_NETWORKS:
        if addr in net:
            return True
    return False


def _is_safe_hostname(host: str) -> bool:
    """检查主机名是否安全（非localhost等特殊名称）。"""
    lower = host.lower()
    # 阻止元数据服务和本地回环主机名
    blocked_hostnames = {
        "localhost", "127.0.0.1", "::1", "0.0.0.0",
        "metadata.google.internal",  # GCP metadata
        "169.254.169.254",           # AWS/cloud metadata IP
    }
    if lower in blocked_hostnames:
        return False
    # 阻止以 .local / .internal 结尾的内部主机名
    if lower.endswith(".local") or lower.endswith(".internal"):
        return False
    return True


def validate_external_url(url: str) -> None:
    """验证URL指向外部可访问地址（非内网/非私有）。

    Raises:
        ValueError: 如果URL指向内网/私有/保留地址。
    """
    if not url:
        raise ValueError("URL不能为空")

    parsed = urlparse(url)

    # 仅允许 http/https
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"不支持的协议: {parsed.scheme}，仅允许 http/https")

    host = parsed.hostname
    if not host:
        raise ValueError(f"无法从URL解析主机名: {url}")

    # 检查IP地址
    if _is_private_ip(host):
        raise ValueError(f"禁止访问内网地址: {host}")

    # 检查主机名安全
    if not _is_safe_hostname(host):
        raise ValueError(f"禁止访问保留/内部主机名: {host}")
