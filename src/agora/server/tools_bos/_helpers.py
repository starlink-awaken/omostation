"""tools_bos 共享状态与基础工具 (tools_bos 拆分)。

提供: _PROJECTS_DIR, logger, _AGORA_API_KEY, _bos_router 引用,
以及被 inbox/bdsk/routing/registration 共用的基础函数。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import structlog

from agora.mcp.bos_router import (  # type: ignore[import-not-found]
    bos_router as _bos_router,
)

# 根仓 projects/ 目录: .../projects/agora/src/agora/server/tools_bos/_helpers.py → ../../../../../..
_PROJECTS_DIR = Path(__file__).resolve().parents[5]

logger = structlog.get_logger(__name__)

_AGORA_API_KEY = os.environ.get("AGORA_API_KEY", "")


def _get_proxy_manager() -> Any | None:
    """获取全局 ProxyManager (来自 agora.server.dependencies)。"""
    try:
        from agora.server.dependencies import get_proxy_manager

        return get_proxy_manager()
    except Exception:  # defensive fallback
        return None


def _bos_domain_authorized(uri: str, operation: str = "read") -> tuple[bool, str]:
    """检查 BOS URI 的域级别权限，并执行 CR-RBAC-01 鉴权。"""
    from agora.server.tools_auth import agora_role_ctx, auth_permissive

    role = agora_role_ctx.get()

    # CR-RBAC-01 强制拦截
    if uri.startswith("bos://capability/evaluator") and role != "evaluator":
        if role != "admin":  # admin can bypass
            return (
                False,
                f"CR-RBAC-01 violation: Role '{role}' cannot access evaluator domain.",
            )

    if not _AGORA_API_KEY:
        if auth_permissive():
            return True, ""  # 显式 permissive (本地开发)
        return False, "AGORA_API_KEY not configured (auth required)"  # fail-closed

    domain = uri.split("/")[2] if uri.startswith("bos://") and "/" in uri else ""
    if not domain:
        return False, "Invalid URI format: Missing domain"

    # CR-DOMAIN-AUTH-01: 注册表驱动的域鉴权
    # 如果 bos_router 中存在该 domain 的任何路由，即视为合法域
    # (更精细的 read/write 权限由 L0 审计与 IAM 中间件后续接管)
    routes = _bos_router.list_all(prefix_filter=f"bos://{domain}/")
    if not routes:
        return False, f"Domain '{domain}' is not registered in BOSRouter"

    return True, ""


def _get_inbox_paths() -> tuple[Path, Path]:
    """获取本地 Inbox 与 @公共/_runtime 数据目录。"""
    doc_root = Path(
        os.environ.get("BOS_DOCUMENTS_ROOT", str(Path.home() / "Documents"))
    )
    runtime_dir = doc_root / "@公共" / "_runtime"
    inbox_dir = doc_root / "_inbox"
    return runtime_dir, inbox_dir


def _bos_uri_to_event_type(uri: str) -> str:
    """将 bos:// URI 转为事件类型标识 (bos:domain:pkg:action)。"""
    return uri.replace("bos://", "bos:", 1).replace("/", ":")


def _publish_bos_event(
    bus: Any,
    uri: str,
    status: str = "called",
    **extra: Any,
) -> None:
    """发布 BOS 事件到事件总线。"""
    try:
        event_type = _bos_uri_to_event_type(uri)
        payload = {"uri": uri, "status": status, **extra}
        bus.publish(event_type, payload)
    except Exception as exc:  # noqa: BLE001 — 事件发布失败不影响主流程
        logger.warning("bos_event_publish_failed", uri=uri, error=str(exc))
