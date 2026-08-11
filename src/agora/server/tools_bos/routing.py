"""BOS 路由辅助 (tools_bos 拆分: routing 域)。

_resolve_with_router: BOSRouter → ProxyManager → POC_SERVICES 路由链。
"""

from __future__ import annotations

from typing import Any

import structlog

from agora.mcp.bos_resolver import (  # type: ignore[import-not-found]
    resolve_bos_uri as _resolve_bos_uri,
)

from ._helpers import _bos_router

_log = structlog.get_logger(__name__)


async def _resolve_with_router(
    uri: str,
    proxy_manager: Any | None = None,
    decision_hash: str = "",
    **kwargs: Any,
) -> tuple[dict, str]:
    """路由解析链: BOSRouter → ProxyManager → POC_SERVICES.

    Args:
        uri: BOS URI
        proxy_manager: ProxyManager 实例 (来自 mcp.py)
        decision_hash: PEP decision hash for provider re-match (BET-Y1Q2-T1-06)
        **kwargs: 传给下游服务的参数

    Returns:
        (result_dict, source_name) 其中 source_name 标明来源
    """
    from agora.mcp.policy_enforcement import PolicyRequest, get_pep

    _pep = get_pep()

    # Rule 6: re-match decision context adjacent to provider dispatch
    def _check_rematch() -> bool:
        if not decision_hash:
            return True  # no PEP in play (backward compat)
        req = PolicyRequest(uri=uri, operation="read")
        if not _pep.rematch_decision(decision_hash, req):
            _log.warning("pep_rematch_failed", uri=uri, hash=decision_hash)
            return False
        return True

    # Step 1: BOSRouter 查找
    route = _bos_router.resolve(uri)
    if route is not None:
        adapter = route.get("adapter", "")
        if adapter == "poc":
            if not _check_rematch():
                return {"status": "error", "error": "PEP decision rematch failed"}, "pep_denied"
            result = await _resolve_bos_uri(uri, proxy_manager=proxy_manager, **kwargs)
            if isinstance(result, dict) and result.get("status") == "error":
                # 区分: unimplemented/unknown (元数据) vs 真实执行错误
                err = str(result.get("error", ""))
                if "unimplemented_bos_service" in err or "unknown_bos_uri" in err:
                    config = route.get("config", {})
                    return {
                        "uri": uri,
                        "status": "info",
                        "source": "bos_router_metadata",
                        "note": "Route registered but no executable backend (metadata only)",
                        "adapter": adapter,
                        "config": config,
                    }, "bos_router_metadata"
                # 真实执行错误 → 透传 error, 不掩盖
                return result, "bos_router_poc_error"
            return result, "bos_router_poc"
        elif adapter == "proxy" and proxy_manager is not None:
            if not _check_rematch():
                return {"status": "error", "error": "PEP decision rematch failed"}, "pep_denied"
            try:
                result = await proxy_manager.read_resource(uri)
                if isinstance(result, dict) and "contents" in result:
                    return result["contents"], "bos_router_proxy"
            except Exception:  # defensive fallback
                pass
        elif adapter in ("http", "internal"):
            if not _check_rematch():
                return {"status": "error", "error": "PEP decision rematch failed"}, "pep_denied"
            result = await _resolve_bos_uri(uri, proxy_manager=proxy_manager, **kwargs)
            if isinstance(result, dict) and result.get("status") != "error":
                return result, "bos_router_fallback"
            err = str((result or {}).get("error", ""))
            if "unimplemented_bos_service" in err or "unknown_bos_uri" in err:
                return {
                    "uri": uri,
                    "status": "info",
                    "source": "bos_router_metadata",
                    "note": f"Route registered (adapter={adapter}) but no executable backend",
                    "adapter": adapter,
                    "config": route.get("config", {}),
                }, "bos_router_metadata"
            # 真实执行错误 → 透传, 不掩盖
            return result, f"bos_router_{adapter}_error"

    # Step 2: POC_SERVICES 直查（兼容旧版）
    if not _check_rematch():
        return {"status": "error", "error": "PEP decision rematch failed"}, "pep_denied"
    result = await _resolve_bos_uri(uri, proxy_manager=proxy_manager, **kwargs)
    return result, "poc_services"


# ── 事件发布 ──────────────────────────────────────────────────────────────
