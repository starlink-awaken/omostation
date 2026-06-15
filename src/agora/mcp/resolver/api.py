"""BOS URI 解析器 — 公共 API"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .services import POC_SERVICES, BosService
from .adapter import get_stdio_adapter

_log = logging.getLogger(__name__)

_WS = str(Path.home() / "Workspace")


def normalize_bos_uri(uri: str) -> str:
    """Map legacy BOS URIs onto their canonical compatibility URI."""
    from agora.legacy_compat import CANONICAL_PERSONA_BRIDGE_URI_PREFIX, LEGACY_PERSONA_BRIDGE_URI_PREFIX

    _LEGACY_BOS_URI_ALIASES = {
        f"{LEGACY_PERSONA_BRIDGE_URI_PREFIX}recall-entity": f"{CANONICAL_PERSONA_BRIDGE_URI_PREFIX}recall-entity",
        f"{LEGACY_PERSONA_BRIDGE_URI_PREFIX}recall": f"{CANONICAL_PERSONA_BRIDGE_URI_PREFIX}recall",
        f"{LEGACY_PERSONA_BRIDGE_URI_PREFIX}sync": f"{CANONICAL_PERSONA_BRIDGE_URI_PREFIX}sync",
    }
    return _LEGACY_BOS_URI_ALIASES.get(uri, uri)


def parse_bos_uri(uri: str) -> dict[str, str]:
    """Parse a BOS URI into its components."""
    import re
    pattern = re.compile(
        r"^bos://(?P<domain>memory|governance|omo|analysis|persona|capability|forge|meta|ecos|agora)"
        r"/(?P<package>[a-z][a-z0-9-]+)/(?P<action>[a-z][a-z0-9-]+)$"
    )
    m = pattern.match(uri)
    if not m:
        return {}
    return m.groupdict()


def list_services() -> list[dict]:
    """列出所有已注册的 BOS 服务."""
    return [
        {
            "uri": s.uri,
            "domain": s.domain,
            "package": s.package,
            "action": s.action,
            "transport": s.transport,
            "description": s.description,
            "alive": True,
        }
        for s in POC_SERVICES
    ]


def get_service(uri: str) -> BosService | None:
    """通过 URI 查找 BOS 服务."""
    norm = normalize_bos_uri(uri)
    for s in POC_SERVICES:
        if s.uri == norm:
            return s
    return None


def list_domains() -> dict[str, list[str]]:
    """列出所有域及其 URI."""
    domains: dict[str, list[str]] = {}
    for s in POC_SERVICES:
        domains.setdefault(s.domain, []).append(s.uri)
    return domains


def invoke_stdio(uri: str, *args: Any, **kwargs: Any) -> dict:
    """通过 stdio 调用 BOS 服务 (兼容旧接口)."""
    service = get_service(uri)
    if not service:
        return {"status": "error", "error": f"unknown_bos_uri: {uri}"}
    adapter = get_stdio_adapter()
    return adapter.call(service, *args, **kwargs)


def protocol_self_check() -> dict:
    """自检: 验证所有服务定义."""
    from collections import Counter
    domains = Counter(s.domain for s in POC_SERVICES)
    return {
        "status": "ok",
        "total": len(POC_SERVICES),
        "domains": dict(domains),
        "by_transport": dict(Counter(s.transport for s in POC_SERVICES)),
    }


async def resolve_bos_uri(uri: str, *args: Any, **kwargs: Any) -> dict:
    """异步 BOS URI 解析 — 兼容旧接口."""
    service = get_service(uri)
    if not service:
        return {"status": "error", "error": f"unknown_bos_uri: {uri}"}

    result: dict
    if service.transport == "internal":
        # internal transport: 同进程 importlib
        try:
            import importlib
            mod = importlib.import_module(service.module_path)
            func = getattr(mod, service.func_name)
            raw = func(*args, **kwargs)
            result = {"status": "ok", "result": raw}
        except Exception as e:
            result = {"status": "error", "error": str(e)}
    else:
        result = invoke_stdio(uri, *args, **kwargs)

    result["uri"] = uri
    result["transport"] = service.transport
    return result
