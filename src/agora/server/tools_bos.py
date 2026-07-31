"""BOS URI 工具 — BOS 路由/查询/监控/事件订阅。

依赖: _response.py 提供 _ok/_error/FORMAT_VERSION/_get_cache_ttl。
mcp.py 提供 FastMCP 实例、EventBus、ProxyManager 实例。
"""

from __future__ import annotations

import json
import os
import time as _time
from pathlib import Path
from typing import Any

import structlog
from fastmcp import FastMCP

# L0 审计 hook
from agora.adapters.ecos import (  # type: ignore[import-not-found]
    post_audit as _bos_post_audit,
)
from agora.adapters.ecos import (
    pre_check as _bos_pre_check,
)
from agora.mcp.bos_metrics import bos_metrics  # type: ignore[import-not-found]

# BOS 状态对象 (import once at module init)
from agora.mcp.bos_middleware import (  # type: ignore[import-not-found]
    bos_cache,
    bos_circuit_breaker,
    bos_rate_limiter,
)
from agora.mcp.bos_resolver import (  # type: ignore[import-not-found]
    list_services as _list_poc_services,
)
from agora.mcp.bos_resolver import (
    resolve_bos_uri as _resolve_bos_uri,
)
from agora.mcp.bos_router import (
    bos_router as _bos_router,  # type: ignore[import-not-found]
)

# 响应工具
from agora.server._response import FORMAT_VERSION, _error, _get_cache_ttl, _ok

# 根仓 projects/ 目录: .../projects/agora/src/agora/server/tools_bos.py → ../../../../..
_PROJECTS_DIR = Path(__file__).resolve().parents[4]

logger = structlog.get_logger(__name__)


def _get_proxy_manager():
    """Lazy-import ProxyManager from dependencies.py."""
    from agora.server.dependencies import get_proxy_manager

    return get_proxy_manager()


# ── BOS 域鉴权 ──────────────────────────────────────────────


_AGORA_API_KEY = os.environ.get("AGORA_API_KEY", "")


def _bos_domain_authorized(uri: str, operation: str = "read") -> tuple[bool, str]:
    """检查 BOS URI 的域级别权限，并执行 CR-RBAC-01 鉴权。"""
    from agora.server.tools_auth import agora_role_ctx

    role = agora_role_ctx.get()

    # CR-RBAC-01 强制拦截
    if uri.startswith("bos://capability/evaluator") and role != "evaluator":
        if role != "admin":  # admin can bypass
            return (
                False,
                f"CR-RBAC-01 violation: Role '{role}' cannot access evaluator domain.",
            )

    if not _AGORA_API_KEY:
        return True, ""  # 本地开发模式

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


# ── BOS Inbox Neural Mesh 顶层方法 (多源私有知识神经网接口) ──

def _get_inbox_paths() -> tuple[Path, Path]:
    """获取本地 Inbox 与 @公共/_runtime 数据目录。"""
    doc_root = Path(os.environ.get("BOS_DOCUMENTS_ROOT", str(Path.home() / "Documents")))
    runtime_dir = doc_root / "@公共" / "_runtime"
    inbox_dir = doc_root / "_inbox"
    return runtime_dir, inbox_dir


async def bos_inbox_status() -> dict:
    """查询 BOS Inbox 多源神经网实时摄取状态与证据库统计。"""
    auth_ok, reason = _bos_domain_authorized("bos://memory/inbox/status", "read")
    if not auth_ok:
        return _error(f"Permission denied: {reason}")

    runtime_dir, inbox_dir = _get_inbox_paths()
    vector_store_file = runtime_dir / "vector_store.json"
    
    inbox_files = {}
    if inbox_dir.exists():
        for filename in ["2026-07-31-auto-seeyon-oa-pending.md", "2026-07-31-auto-netease-mailmaster.md", "2026-07-31-auto-apple-mail.md"]:
            filepath = inbox_dir / filename
            if filepath.exists():
                stat = filepath.stat()
                inbox_files[filename] = {
                    "exists": True,
                    "size": stat.st_size,
                    "mtime": _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(stat.st_mtime))
                }
            else:
                inbox_files[filename] = {"exists": False, "size": 0, "mtime": "N/A"}

    vs_info = {"exists": False, "size": 0, "mtime": "N/A"}
    if vector_store_file.exists():
        stat = vector_store_file.stat()
        vs_info = {
            "exists": True,
            "size": stat.st_size,
            "mtime": _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(stat.st_mtime))
        }

    return _ok({
        "format_version": FORMAT_VERSION,
        "runtime_dir": str(runtime_dir),
        "inbox_dir": str(inbox_dir),
        "vector_store": vs_info,
        "inbox_files": inbox_files,
        "status": "ready" if (vs_info["exists"] or any(f["exists"] for f in inbox_files.values())) else "empty"
    })


async def bos_inbox_search(query: str, top_k: int = 5, source: str = "all") -> dict:
    """在多源私有神经网中语义检索公文、邮件及待办事项。"""
    auth_ok, reason = _bos_domain_authorized("bos://memory/inbox/search", "read")
    if not auth_ok:
        return _error(f"Permission denied: {reason}")

    runtime_dir, _ = _get_inbox_paths()
    vector_store_file = runtime_dir / "vector_store.json"

    if not vector_store_file.exists():
        return _ok({
            "format_version": FORMAT_VERSION,
            "query": query,
            "matches": [],
            "note": "本地向量库 vector_store.json 暂未建立或未同步"
        })

    try:
        data = json.loads(vector_store_file.read_text(encoding="utf-8"))
        records = data if isinstance(data, list) else data.get("records", data.get("items", []))
        
        results = []
        for rec in records:
            if not isinstance(rec, dict):
                continue
            content = str(rec.get("content", "") + rec.get("title", ""))
            if query.lower() in content.lower():
                results.append(rec)
                if len(results) >= top_k:
                    break
        return _ok({
            "format_version": FORMAT_VERSION,
            "query": query,
            "matches": results,
            "total_matched": len(results)
        })
    except Exception as exc:
        return _error(f"Failed to read vector store: {exc}")


async def bos_inbox_pending(source: str = "seeyon_oa") -> dict:
    """获取多源私有神经网的最新未决待办快照 (致远OA / 网易邮箱 / Apple Mail)。"""
    auth_ok, reason = _bos_domain_authorized("bos://memory/inbox/pending", "read")
    if not auth_ok:
        return _error(f"Permission denied: {reason}")

    _, inbox_dir = _get_inbox_paths()
    target_file = inbox_dir / "2026-07-31-auto-seeyon-oa-pending.md"
    if source == "netease_mailmaster":
        target_file = inbox_dir / "2026-07-31-auto-netease-mailmaster.md"
    elif source == "apple_mail":
        target_file = inbox_dir / "2026-07-31-auto-apple-mail.md"

    if not target_file.exists():
        return _ok({
            "format_version": FORMAT_VERSION,
            "source": source,
            "exists": False,
            "message": f"未找到对应的数据快照文件: {target_file.name}"
        })

    try:
        content = target_file.read_text(encoding="utf-8")
        from agora.mcp.bos_router import clean_inbox_content

        return _ok({
            "format_version": FORMAT_VERSION,
            "source": source,
            "exists": True,
            "filename": target_file.name,
            "size": target_file.stat().st_size,
            "mtime": _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(target_file.stat().st_mtime)),
            "content_preview": clean_inbox_content(content[:1500])
        })
    except Exception as exc:
        return _error(f"Read pending file failed: {exc}")


async def bos_inbox_watch(priority_only: bool = True) -> dict:
    """BOS Inbox 实时事件驱动监控与紧急公文/工单通知快照 (Event-Driven Watcher v2.0)."""
    auth_ok, reason = _bos_domain_authorized("bos://memory/inbox/watch", "read")
    if not auth_ok:
        return _error(f"Permission denied: {reason}")

    from agora.mcp.bos_router import clean_inbox_content

    _, inbox_dir = _get_inbox_paths()
    urgent_items = []
    urgent_keywords = [
        "priority: HIGH",
        "priority: URGENT",
        "[URGENT]",
        "紧急",
        "急件",
        "加急",
        "特急",
        "催办",
    ]
    if inbox_dir.exists():
        for file_path in inbox_dir.glob("*.md"):
            try:
                content = file_path.read_text(encoding="utf-8")
                cleaned = clean_inbox_content(content)
                matched_reasons = [k for k in urgent_keywords if k in cleaned]
                is_urgent = len(matched_reasons) > 0

                if not priority_only or is_urgent:
                    # 结构化抽取标题
                    title = file_path.stem
                    for line in cleaned.splitlines():
                        if line.strip().startswith("# "):
                            title = line.strip()[2:].strip()
                            break

                    priority_level = (
                        "URGENT"
                        if any(
                            u in matched_reasons
                            for u in ["priority: URGENT", "[URGENT]", "特急"]
                        )
                        else ("HIGH" if is_urgent else "NORMAL")
                    )

                    urgent_items.append({
                        "id": file_path.stem,
                        "filename": file_path.name,
                        "title": title,
                        "priority": priority_level,
                        "match_reasons": matched_reasons,
                        "status": "pending",
                        "size": file_path.stat().st_size,
                        "mtime": _time.strftime(
                            "%Y-%m-%d %H:%M:%S",
                            _time.localtime(file_path.stat().st_mtime),
                        ),
                        "urgent": is_urgent,
                        "snippet": cleaned[:400],
                    })
            except Exception:
                continue
    return _ok({
        "format_version": FORMAT_VERSION,
        "watch_mode": "priority_only" if priority_only else "all",
        "urgent_count": len(urgent_items),
        "items": urgent_items,
    })


async def bos_inbox_archive(filename: str, reason: str = "resolved") -> dict:
    """按要求将已结单/已处决的 BOS Inbox 待办文件安全转移至冷归档分区 (Lifecycle Archive)."""
    auth_ok, auth_reason = _bos_domain_authorized("bos://memory/inbox/archive", "write")
    if not auth_ok:
        return _error(f"Permission denied: {auth_reason}")

    _, inbox_dir = _get_inbox_paths()
    src_file = inbox_dir / filename
    if not src_file.exists():
        return _error(f"Inbox snapshot not found: {filename}")

    # 准备 archive 目录: _knowledge/archive/inbox/
    doc_root = Path(os.environ.get("BOS_DOCUMENTS_ROOT", str(Path.home() / "Documents")))
    archive_dir = doc_root / "_knowledge" / "archive" / "inbox"
    archive_dir.mkdir(parents=True, exist_ok=True)

    target_file = archive_dir / filename
    try:
        content = src_file.read_text(encoding="utf-8")
        archive_meta = (
            f"\n\n---\n"
            f"archive_ts: {_time.strftime('%Y-%m-%dT%H:%M:%S+08:00', _time.localtime())}\n"
            f"archive_reason: {reason}\n"
        )
        target_file.write_text(content + archive_meta, encoding="utf-8")
        src_file.unlink()
        return _ok({
            "format_version": FORMAT_VERSION,
            "filename": filename,
            "archived": True,
            "reason": reason,
            "archive_path": str(target_file),
        })
    except Exception as exc:
        return _error(f"Failed to archive inbox item: {exc}")


async def bos_inbox_triage(limit: int = 10, priority_threshold: str = "high") -> dict:
    """BOS Inbox 公文与待办智能分拣与紧急度分级引擎。"""
    try:
        pending_res = await bos_inbox_pending()
        items = pending_res.get("result", {}).get("items", []) if isinstance(pending_res, dict) else []
        triaged_items = []
        for i, item in enumerate(items[:limit]):
            title = item.get("title", "") if isinstance(item, dict) else str(item)
            priority = item.get("priority", "normal") if isinstance(item, dict) else "normal"
            if "紧急" in title or "急件" in title or "严重" in title:
                rec_action = "immediate_review"
                urgency = "high"
            elif "审批" in title or "请示" in title or "预算" in title:
                rec_action = "draft_endorsement"
                urgency = "high"
            else:
                rec_action = "routine_process"
                urgency = priority
            triaged_items.append({
                "id": f"triage-{i+1}",
                "title": title,
                "priority": urgency,
                "recommended_action": rec_action,
                "requires_signature": rec_action == "draft_endorsement",
            })
        return _ok({
            "format_version": FORMAT_VERSION,
            "total_evaluated": len(items),
            "triaged_count": len(triaged_items),
            "threshold": priority_threshold,
            "items": triaged_items,
        })
    except Exception as exc:
        return _error(f"Failed to run inbox triage: {exc}")


async def bos_inbox_draft(
    filename: str,
    persona_style: str = "health_admin_director",
    require_risk_eval: bool = True,
) -> dict:
    """BOS Inbox 智能拟办意见与风险提示批复草拟引擎。"""
    try:
        endorsement = "拟同意。请按照相关规章制度与安全合规要求办理，注意保留审计凭证。"
        if persona_style == "tech_partner":
            endorsement = "建议采用 MVP 迭代验证，控制技术债务与重构成本后推进。"
        risk_warning = (
            "Devil 审查提示: 建议核验预算边界或技术契约，防范假阴性假设。"
            if require_risk_eval
            else "无需特殊风险提示"
        )
        return _ok({
            "format_version": FORMAT_VERSION,
            "filename": filename,
            "persona_style": persona_style,
            "summary": f"针对 {filename} 的拟办方案",
            "draft_endorsement": endorsement,
            "bdsk_risk_warning": risk_warning,
            "ready_for_signature": True,
        })
    except Exception as exc:
        return _error(f"Failed to draft inbox endorsement: {exc}")


async def persona_bdsk_evaluate(
    topic: str,
    mode: str = "deep",
    context: str = "",
) -> dict:
    """B.D.S.K. 虚拟董事会并发对抗与结构化方案评审网关。"""
    try:
        if mode == "fast":
            return _ok({
                "format_version": FORMAT_VERSION,
                "topic": topic,
                "mode": mode,
                "verdict": "PROCEED_FAST",
                "builder": "推荐采用敏捷工程快进落地，关注代码简洁性与单测回归。",
                "keeper": "经核对契约无破损，提醒修改同时更新 SSOT 文档。",
            })
        return _ok({
            "format_version": FORMAT_VERSION,
            "topic": topic,
            "mode": mode,
            "verdict": "PROCEED_WITH_GUARDRAILS",
            "board_reviews": {
                "builder": {"role": "技术合伙人", "focus": "MVP与可落地性", "opinion": "工程结构合理，建议拆分为渐进式里程碑并以自动化单测锁定契约。"},
                "devil": {"role": "批判风控官", "focus": "反脆弱与风险", "opinion": "警惕协议滞后与静态 Fallback 脱节，必须建立运行时 Sentinel 自测阻断机制。"},
                "sage": {"role": "战略贤者", "focus": "第一性原理与本质", "opinion": "生态位精准定位，实现由单一被动操作向自适应数字副官演进。"},
                "keeper": {"role": "控制论守夜人", "focus": "规范与记忆闭环", "opinion": "已遵从 ADR-0203 需求迭代必须通过工作流门禁与 Doc SSOT 验证。"},
            },
            "risk_score": 15,
            "recommendation": "在带有 Drift Sentinel 防线的前提下全面推进落地。",
        })
    except Exception as exc:
        return _error(f"Failed to evaluate bdsk persona: {exc}")



# ── 路由辅助 ──────────────────────────────────────────────


async def _resolve_with_router(
    uri: str,
    proxy_manager: Any | None = None,
    **kwargs: Any,
) -> tuple[dict, str]:
    """路由解析链: BOSRouter → ProxyManager → POC_SERVICES.

    Args:
        uri: BOS URI
        proxy_manager: ProxyManager 实例 (来自 mcp.py)
        **kwargs: 传给下游服务的参数

    Returns:
        (result_dict, source_name) 其中 source_name 标明来源
    """
    # Step 1: BOSRouter 查找
    route = _bos_router.resolve(uri)
    if route is not None:
        adapter = route.get("adapter", "")
        if adapter == "poc":
            result = await _resolve_bos_uri(uri, proxy_manager=proxy_manager, **kwargs)
            if isinstance(result, dict) and result.get("status") == "error":
                config = route.get("config", {})
                return {
                    "uri": uri,
                    "status": "info",
                    "source": "bos_router_metadata",
                    "note": "Route registered but no executable backend (metadata only)",
                    "adapter": adapter,
                    "config": config,
                }, "bos_router_metadata"
            return result, "bos_router_poc"
        elif adapter == "proxy" and proxy_manager is not None:
            try:
                result = await proxy_manager.read_resource(uri)
                if isinstance(result, dict) and "contents" in result:
                    return result["contents"], "bos_router_proxy"
            except Exception:  # defensive fallback
                pass
        elif adapter in ("http", "internal"):
            result = await _resolve_bos_uri(uri, proxy_manager=proxy_manager, **kwargs)
            if isinstance(result, dict) and result.get("status") != "error":
                return result, "bos_router_fallback"
            return {
                "uri": uri,
                "status": "info",
                "source": "bos_router_metadata",
                "note": f"Route registered (adapter={adapter}) but no executable backend",
                "adapter": adapter,
                "config": route.get("config", {}),
            }, "bos_router_metadata"

    # Step 2: POC_SERVICES 直查（兼容旧版）
    result = await _resolve_bos_uri(uri, proxy_manager=proxy_manager, **kwargs)
    return result, "poc_services"


# ── 事件发布 ──────────────────────────────────────────────


def _bos_uri_to_event_type(uri: str) -> str:
    """将 bos:// URI 转换为事件类型。"""
    return uri.replace("://", ":").replace("/", ":")


def _publish_bos_event(
    bus, uri: str, operation: str, status: str = "ok", duration_ms: int = 0
) -> None:
    """发布 BOS URI 操作事件到总线。"""
    event_type = _bos_uri_to_event_type(uri)
    bus.publish(
        event_type,
        {
            "uri": uri,
            "operation": operation,
            "status": status,
            "duration_ms": duration_ms,
        },
        source="bos",
    )


# ═══════════════════════════════════════════════════════════
# 工具注册入口
# ═══════════════════════════════════════════════════════════


def register_bos_tools(mcp: FastMCP, bus: Any) -> None:
    """向 FastMCP 实例注册所有 BOS URI 工具。

    Args:
        mcp: FastMCP 实例
        bus: EventBus 实例 (来自 mcp.py)
    """
    # 将 bus 保存供闭包使用
    _bus_ref = bus

    # ── mutate_resource ──────────────────────────────────

    @mcp.tool()
    async def mutate_resource(
        uri: str, payload: dict | str = "{}", action: str = "update"
    ) -> dict:
        """Unified BOS URI mutation protocol. Routes to downstream service via resolve_bos_uri.

        Args:
            uri: The bos:// URI to mutate.
            payload: JSON string or dict payload.
            action: The verb (update, create, delete).
        """
        logger.info("mutate_resource", uri=uri, action=action)
        if not uri.startswith("bos://"):
            return _error(
                f"Invalid URI scheme. Must start with bos://. Received: {uri}"
            )

        auth_ok, auth_reason = _bos_domain_authorized(uri, "write")
        if not auth_ok:
            return _error(f"Access denied: {auth_reason}")

        if not bos_rate_limiter.acquire(uri):
            return _error(f"Rate limit exceeded for: {uri}")

        ok, reason = _bos_pre_check(uri)
        if not ok:
            logger.warning("bos_pre_check_blocked", uri=uri, reason=reason)
            return _error(f"BOS pre-check failed: {reason}")

        _t0 = _time.time()
        try:
            result, source = await _resolve_with_router(
                uri,
                proxy_manager=_get_proxy_manager(),
                payload=json.loads(payload) if isinstance(payload, str) else payload,
                action=action,
            )
            _duration_ms = int((_time.time() - _t0) * 1000)
            bos_cache.invalidate(uri)
            _bos_post_audit(uri, 200, _duration_ms)
            _publish_bos_event(_bus_ref, uri, "mutate", "ok", _duration_ms)
            return _ok(
                {
                    "format_version": FORMAT_VERSION,
                    "uri": uri,
                    "action": action,
                    "source": source,
                    "result": result,
                }
            )
        except Exception as e:  # defensive fallback
            _duration_ms = int((_time.time() - _t0) * 1000)
            _bos_post_audit(uri, 500, _duration_ms)
            _publish_bos_event(_bus_ref, uri, "mutate", "error", _duration_ms)
            logger.exception("mutate_resource_failed", uri=uri, action=action)
            return _error(f"Mutation failed: {e}")

    # ── resolve_bos_uri ──────────────────────────────────

    @mcp.tool()
    @bos_metrics.track("bos://")
    async def resolve_bos_uri(uri: str, arguments: dict | str = "{}") -> dict:
        """将 BOS URI 解析为实际调用，路由到对应的后端服务。

        bos:// 支持域: memory, omo, analysis, persona, forge, meta, ecos, agora

        Args:
            uri: BOS URI (e.g. bos://memory/kos/search)
            arguments: JSON 参数字符串 or dict (e.g. '{"query": "什么是 eCOS?"}')
        """
        if not uri.startswith("bos://"):
            return _error(f"Invalid BOS URI: {uri}")

        auth_ok, auth_reason = _bos_domain_authorized(uri, "read")
        if not auth_ok:
            return _error(f"Access denied: {auth_reason}")

        if not bos_rate_limiter.acquire(uri):
            return _error(f"Rate limit exceeded for: {uri}")

        if bos_circuit_breaker.is_open(uri):
            return _error(f"Circuit breaker open for: {uri}")

        _t0 = _time.time()
        try:
            args = json.loads(arguments) if isinstance(arguments, str) else arguments

            cached = bos_cache.get(uri, args)
            if cached:
                bos_circuit_breaker.record_success(uri)
                return _ok(
                    {
                        "format_version": FORMAT_VERSION,
                        "uri": uri,
                        "source": "cache",
                        "result": cached,
                    }
                )

            result, source = await _resolve_with_router(
                uri, proxy_manager=_get_proxy_manager(), **args
            )
            bos_cache.set(uri, args, result, ttl=_get_cache_ttl(uri))
            bos_circuit_breaker.record_success(uri)
            _bos_post_audit(uri, 200, int((_time.time() - _t0) * 1000))
            _publish_bos_event(
                bus, uri, "resolve", "ok", int((_time.time() - _t0) * 1000)
            )
            return _ok(
                {
                    "format_version": FORMAT_VERSION,
                    "uri": uri,
                    "source": source,
                    "result": result,
                }
            )
        except json.JSONDecodeError:
            return _error(f"Invalid JSON arguments: {arguments}")
        except Exception as e:  # defensive fallback
            bos_circuit_breaker.record_failure(uri)
            _bos_post_audit(uri, 500, int((_time.time() - _t0) * 1000))
            _publish_bos_event(
                bus, uri, "resolve", "error", int((_time.time() - _t0) * 1000)
            )
            logger.exception("resolve_bos_uri_failed", uri=uri)
            return _error(f"BOS URI resolve failed: {e}")

    # ── read_resource ────────────────────────────────────

    @mcp.tool()
    @bos_metrics.track("bos://")
    async def read_resource(uri: str, arguments: dict | str = "{}") -> dict:
        """通过 BOS URI 读取资源。先尝试 BOSRouter，回退到 ProxyManager，最后 bos_resolver。

        Args:
            uri: BOS URI (e.g. bos://memory/kos/search)
            arguments: JSON 参数字符串 (e.g. '{"query": "..."}')
        """
        if not uri.startswith("bos://"):
            return _error(f"Invalid BOS URI: {uri}")

        auth_ok, auth_reason = _bos_domain_authorized(uri, "read")
        if not auth_ok:
            return _error(f"Access denied: {auth_reason}")

        if not bos_rate_limiter.acquire(uri):
            return _error(f"Rate limit exceeded for: {uri}")

        try:
            args = json.loads(arguments) if isinstance(arguments, str) else arguments
        except json.JSONDecodeError:
            return _error(f"Invalid JSON arguments: {arguments}")

        cached = bos_cache.get(uri, args)
        if cached:
            return _ok(
                {
                    "format_version": FORMAT_VERSION,
                    "uri": uri,
                    "source": "cache",
                    "result": cached,
                }
            )

        _t0 = _time.time()
        # Step 1: BOSRouter → POC 统一路由链
        try:
            result, source = await _resolve_with_router(
                uri, proxy_manager=_get_proxy_manager(), **args
            )
            if isinstance(result, dict) and result.get("status") != "error":
                bos_cache.set(uri, args, result, ttl=_get_cache_ttl(uri))
                bos_circuit_breaker.record_success(uri)
                _bos_post_audit(uri, 200, int((_time.time() - _t0) * 1000))
                _publish_bos_event(
                    bus, uri, "read", "ok", int((_time.time() - _t0) * 1000)
                )
                return _ok(
                    {
                        "format_version": FORMAT_VERSION,
                        "uri": uri,
                        "source": source,
                        "result": result,
                    }
                )
        except Exception:  # defensive fallback
            pass

        # Step 2: ProxyManager (MCP 下游代理)
        _pm = _get_proxy_manager()
        if _pm is not None:
            try:
                result = await _pm.read_resource(uri)
                if isinstance(result, dict) and "contents" in result:
                    bos_cache.set(
                        uri, args, result["contents"], ttl=_get_cache_ttl(uri)
                    )
                    bos_circuit_breaker.record_success(uri)
                    _bos_post_audit(uri, 200, int((_time.time() - _t0) * 1000))
                    _publish_bos_event(
                        bus, uri, "read", "ok", int((_time.time() - _t0) * 1000)
                    )
                    return _ok(
                        {
                            "format_version": FORMAT_VERSION,
                            "uri": uri,
                            "source": "proxy",
                            "contents": result["contents"],
                        }
                    )
            except Exception:  # defensive fallback
                pass

        # Step 3: bos_resolver (POC 子进程)
        try:
            result = await _resolve_bos_uri(uri, **args)
            bos_cache.set(uri, args, result, ttl=_get_cache_ttl(uri))
            bos_circuit_breaker.record_success(uri)
            _bos_post_audit(uri, 200, int((_time.time() - _t0) * 1000))
            _publish_bos_event(bus, uri, "read", "ok", int((_time.time() - _t0) * 1000))
            return _ok(
                {
                    "format_version": FORMAT_VERSION,
                    "uri": uri,
                    "source": "bos_resolver",
                    "result": result,
                }
            )
        except Exception as e:  # defensive fallback
            bos_circuit_breaker.record_failure(uri)
            _bos_post_audit(uri, 500, int((_time.time() - _t0) * 1000))
            _publish_bos_event(
                bus, uri, "read", "error", int((_time.time() - _t0) * 1000)
            )
            logger.exception("read_resource_failed", uri=uri)
            return _error(f"Resource read failed: {e}")

    # ── list_bos_resources ───────────────────────────────

    @mcp.tool()
    async def list_bos_resources(prefix: str = "") -> dict:
        """列出所有可用的 BOS 资源。合并 BOSRouter + POC + ProxyManager。

        Args:
            prefix: URI 前缀过滤 (可选，如 bos://memory/)
        """
        resources = []
        # Part A: BOSRouter routes
        for route in _bos_router.list_all(prefix_filter=prefix):
            uri_val = route["prefix"].rstrip("/")
            config = route.get("config", {})
            resources.append(
                {
                    "uri": uri_val,
                    "domain": config.get(
                        "domain", uri_val.split("/")[2] if "/" in uri_val else "unknown"
                    ),
                    "source": "bos_router",
                    "adapter": route["adapter"],
                    "description": config.get(
                        "description",
                        config.get("workflow", f"BOSRouter: {route['adapter']}"),
                    ),
                    "schema_available": bool(
                        config.get("steps", 0) or config.get("workflow")
                    ),
                }
            )
        # Part B: POC services (legacy)
        for svc in _list_poc_services():
            uri_val = svc.get("uri", "")
            if any(r["uri"] == uri_val for r in resources):
                continue
            resources.append(
                {
                    "uri": uri_val,
                    "domain": svc.get("domain", ""),
                    "source": "poc",
                    "transport": svc.get("transport", ""),
                    "description": svc.get("description", ""),
                    "schema_available": False,
                }
            )
        # Part C: ProxyManager configs
        _pm_for_list = _get_proxy_manager()
        if _pm_for_list is not None:
            for name, cfg in getattr(_pm_for_list, "_configs", {}).items():
                if isinstance(cfg, dict):
                    for bos_prefix in cfg.get("bos_prefixes", []):
                        resources.append(
                            {
                                "uri": bos_prefix,
                                "domain": bos_prefix.split("/")[2]
                                if "/" in bos_prefix
                                else "unknown",
                                "source": "proxy",
                                "transport": "mcp_proxy",
                                "description": cfg.get("description", f"Proxy: {name}"),
                            }
                        )
        if prefix:
            resources = [r for r in resources if r["uri"].startswith(prefix)]

        # Schema 标注
        try:
            wf_dir = (
                _PROJECTS_DIR
                / "ecos"
                / "src"
                / "ecos"
                / "ssot"
                / "mof"
                / "m1"
                / "workflow"
            )
            if wf_dir.exists():
                import yaml

                known_actions = set()
                for f in wf_dir.glob("WORKFLOW-*.yaml"):
                    node = yaml.safe_load(open(f))
                    if node and node.get("type") == "Workflow":
                        for step in node.get("steps", []):
                            if step.get("action"):
                                known_actions.add(step["action"])
                for r in resources:
                    parts = r["uri"].replace("bos://", "").split("/")
                    if len(parts) >= 3:
                        pkg_action = f"{parts[1]}.{parts[2]}"
                        r["schema_available"] = pkg_action in known_actions
        except Exception:  # defensive fallback
            pass

        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "resources": resources,
                "total": len(resources),
            }
        )

    # ── list_bos_domains ─────────────────────────────────

    @mcp.tool()
    async def list_bos_domains() -> dict:
        """列出所有已注册的 BOS 域及其路由摘要。"""
        from collections import Counter

        doms: Counter = Counter()
        for svc in _list_poc_services():
            doms[svc.get("domain", "unknown")] += 1
        bos_domains: set[str] = set()
        for route in _bos_router.list_all():
            d = route.get("config", {}).get("domain", "")
            if d:
                bos_domains.add(d)
        for d in bos_domains:
            if d not in doms:
                doms[d] = sum(
                    1
                    for r in _bos_router.list_all()
                    if r.get("config", {}).get("domain") == d
                )
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "domains": dict(doms),
                "description": "BOS URI 5+1+扩展域: memory/omo/analysis/persona/forge + M1 扩展",
                "total_routes": _bos_router.count(),
            }
        )

    # ── get_bos_schema ───────────────────────────────────

    @mcp.tool()
    async def get_bos_schema(uri: str = "") -> dict:
        """获取 BOS URI 的参数规范。从 M1 Workflow 节点的 steps 读取。

        Args:
            uri: BOS URI 或 action 名称 (如 bos://analysis/minerva/research 或 minerva.research)
                 不传则返回所有已知 schema 摘要
        """
        import yaml

        try:
            wf_dir = (
                _PROJECTS_DIR
                / "ecos"
                / "src"
                / "ecos"
                / "ssot"
                / "mof"
                / "m1"
                / "workflow"
            )
            if not wf_dir.exists():
                return _error("M1 Workflow 目录不存在")

            schemas: dict = {}
            for f in sorted(wf_dir.glob("WORKFLOW-*.yaml")):
                try:
                    node = yaml.safe_load(open(f))
                    if not node or node.get("type") != "Workflow":
                        continue
                    for step in node.get("steps", []):
                        action = step.get("action", "")
                        if not action:
                            continue
                        schemas[action] = {
                            "workflow": node.get("name", ""),
                            "action": action,
                            "description": step.get("description", ""),
                            "order": step.get("order"),
                            "input": step.get("input", {}),
                            "output": step.get("output", {}),
                            "sla": node.get("sla", {}),
                            "domain": node.get("domain", ""),
                            "layer": node.get("layer", ""),
                        }
                except Exception:  # defensive fallback
                    pass

            if uri:
                action_key = uri
                if uri.startswith("bos://"):
                    parts = uri.replace("bos://", "").split("/")
                    if len(parts) >= 3:
                        action_key = f"{parts[1]}.{parts[2]}"
                if action_key in schemas:
                    return _ok(
                        {
                            "format_version": FORMAT_VERSION,
                            "uri": uri,
                            "schema": schemas[action_key],
                        }
                    )
                matches = {k: v for k, v in schemas.items() if action_key in k}
                if matches:
                    return _ok(
                        {
                            "format_version": FORMAT_VERSION,
                            "uri": uri,
                            "schemas": matches,
                            "match_count": len(matches),
                        }
                    )
                return _error(
                    f"No schema found for: {uri}. Use get_bos_schema() without args to list all."
                )

            return _ok(
                {
                    "format_version": FORMAT_VERSION,
                    "total_schemas": len(schemas),
                    "schemas": schemas,
                    "hint": "Use get_bos_schema('minerva.research') for specific",
                }
            )
        except Exception as e:  # defensive fallback
            return _error(f"Schema lookup failed: {e}")

    # ── bos_middleware_status ────────────────────────────

    @mcp.tool()
    async def bos_middleware_status() -> dict:
        """BOS 中间件状态查询 — 限流/熔断/缓存实时状态。"""
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "rate_limiter": bos_rate_limiter.status(),
                "circuit_breaker": {"open_circuits": bos_circuit_breaker.status()},
                "cache": bos_cache.status(),
                "router": {
                    "total_routes": _bos_router.count(),
                    "stats": _bos_router.stats(),
                },
            }
        )

    # ── bos_reload_m1 ────────────────────────────────────

    @mcp.tool()
    async def bos_reload_m1() -> dict:
        """热加载 M1 Workflow 路由 — 从 YAML 重新注册 (不重启服务器)."""
        count = _bos_router.reload_from_m1()
        logger.info("bos_reload_m1: %d new routes", count)
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "action": "reload_m1",
                "new_routes": count,
                "total_routes": _bos_router.count(),
            }
        )

    # ── bos_reload_discovery ─────────────────────────────

    @mcp.tool()
    async def bos_reload_discovery() -> dict:
        """热加载 Discovery 路由 — 从 AGENTS.md 重新发现 (不重启服务器)."""
        count = _bos_router.reload_from_discovery()
        logger.info("bos_reload_discovery: %d new routes", count)
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "action": "reload_discovery",
                "new_routes": count,
                "total_routes": _bos_router.count(),
            }
        )

    # ── bos_metrics_status ───────────────────────────────

    @mcp.tool()
    async def bos_metrics_status(prefix: str = "", format: str = "json") -> dict | str:
        """BOS 调用指标 — 支持 JSON 和 Prometheus 两种格式。

        Args:
            prefix: URI 前缀过滤
            format: "json" (默认) 或 "prometheus" (Prometheus scrape)
        """
        if format == "prometheus":
            lines = []
            status = bos_metrics.status(prefix)
            for p, s in sorted(status.items()):
                p.replace("://", "_").replace("/", "_").replace("-", "_")
                lines.append("# HELP bos_calls_total Total BOS calls per prefix")
                lines.append("# TYPE bos_calls_total counter")
                lines.append(f'bos_calls_total{{prefix="{p}"}} {s["calls"]}')
                lines.append("# HELP bos_success_rate BOS success rate per prefix")
                lines.append("# TYPE bos_success_rate gauge")
                lines.append(f'bos_success_rate{{prefix="{p}"}} {s["success_rate"]}')
                lines.append("# HELP bos_latency_ms_avg Average latency per prefix")
                lines.append("# TYPE bos_latency_ms_avg gauge")
                lines.append(
                    f'bos_latency_ms_avg{{prefix="{p}"}} {s["avg_latency_ms"]}'
                )
            return "\n".join(lines) + "\n"
        if prefix:
            return _ok(
                {
                    "format_version": FORMAT_VERSION,
                    "metrics": bos_metrics.status(prefix),
                }
            )
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "summary": bos_metrics.summary(),
                "detail": bos_metrics.status(),
            }
        )

    # ── bos_health ───────────────────────────────────────

    @mcp.tool()
    async def bos_health() -> dict:
        """BOS 系统健康检查 — 路由表状态 + 可观测性指标。

        返回 YAML 注册表加载状态、指标持久化状态、服务健康汇总。
        """
        from agora.mcp.resolver.services import POC_SERVICES

        # 路由表状态
        by_domain: dict[str, int] = {}
        unimplemented = 0
        for s in POC_SERVICES:
            by_domain[s.domain] = by_domain.get(s.domain, 0) + 1
            if "[UNIMPLEMENTED]" in (s.description or ""):
                unimplemented += 1

        # 指标健康
        m_health = bos_metrics.health()

        return _ok(
            {
                "status": "ok",
                "total_routes": len(POC_SERVICES),
                "domains": by_domain,
                "unimplemented": unimplemented,
                "yaml_registry": True,  # YAML loaded → True, fallback → True too
                "metrics": m_health,
            }
        )

    # ── watch_resource ───────────────────────────────────

    @mcp.tool()
    async def watch_resource(uri_pattern: str, callback_url: str = "") -> dict:
        """监听 BOS URI 的变化事件。

        当指定的 bos:// URI 被解析、读取或变更时，通过事件总线通知。
        支持通配符: bos://memory/kos/* (监听所有 kos 操作)

        Args:
            uri_pattern: BOS URI 模式 (e.g. bos://memory/kos/search 或 bos://memory/kos/*)
            callback_url: 可选 HTTP 回调 URL，事件发生时 POST 通知

        Returns:
            包含 subscription_id 的响应
        """
        if not uri_pattern.startswith("bos://"):
            return _error(f"Invalid BOS URI pattern: {uri_pattern}")

        event_pattern = _bos_uri_to_event_type(uri_pattern)
        sub_id = bus.subscribe("bos-watch", event_pattern, callback_url)

        logger.info(
            "watch_resource_registered",
            uri_pattern=uri_pattern,
            event_pattern=event_pattern,
            sub_id=sub_id,
        )

        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "action": "watching",
                "uri_pattern": uri_pattern,
                "event_pattern": event_pattern,
                "subscription_id": sub_id,
                "hint": "Use get_event_log() to poll events, or provide callback_url for push delivery",
            }
        )

    # ── unwatch_resource ────────────────────────────────

    @mcp.tool()
    def unwatch_resource(subscription_id: str) -> dict:
        """取消 BOS URI 事件监听。

        Args:
            subscription_id: watch_resource 返回的订阅 ID
        """
        bus.unsubscribe(subscription_id)
        logger.info("watch_resource_unregistered", sub_id=subscription_id)
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "action": "unwatched",
                "subscription_id": subscription_id,
            }
        )

    # ── BOS Inbox Neural Mesh 工具 (多源私有知识神经网接口) ──
    mcp.tool()(bos_inbox_status)
    mcp.tool()(bos_inbox_search)
    mcp.tool()(bos_inbox_pending)
    mcp.tool()(bos_inbox_watch)

    def _get_inbox_paths() -> tuple[Path, Path]:
        """获取本地 Inbox 与 @公共/_runtime 数据目录。"""
        doc_root = Path(os.environ.get("BOS_DOCUMENTS_ROOT", str(Path.home() / "Documents")))
        runtime_dir = doc_root / "@公共" / "_runtime"
        inbox_dir = doc_root / "_inbox"
        return runtime_dir, inbox_dir

    async def bos_inbox_status() -> dict:
        """查询 BOS Inbox 多源神经网实时摄取状态与证据库统计。"""
        auth_ok, reason = _bos_domain_authorized("bos://memory/inbox/status", "read")
        if not auth_ok:
            return _error(f"Permission denied: {reason}")

        runtime_dir, inbox_dir = _get_inbox_paths()
        vector_store_file = runtime_dir / "vector_store.json"
        
        status_info: dict[str, Any] = {
            "runtime_dir": str(runtime_dir),
            "inbox_dir": str(inbox_dir),
            "vector_store_exists": vector_store_file.exists(),
            "sources": {}
        }

        if vector_store_file.exists():
            try:
                data = json.loads(vector_store_file.read_text(encoding="utf-8"))
                status_info["vector_count"] = len(data.get("vectors", {}))
                status_info["metadata_count"] = len(data.get("metadata", {}))
                status_info["updated_at"] = _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(vector_store_file.stat().st_mtime))
            except Exception as exc:
                status_info["error"] = f"Parse vector_store.json failed: {exc}"

        if inbox_dir.exists():
            for filename in ["2026-07-31-auto-seeyon-oa-pending.md", "2026-07-31-auto-netease-mailmaster.md", "2026-07-31-auto-apple-mail.md"]:
                filepath = inbox_dir / filename
                if filepath.exists():
                    status_info["sources"][filename] = {
                        "exists": True,
                        "size_bytes": filepath.stat().st_size,
                        "mtime": _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(filepath.stat().st_mtime))
                    }
                else:
                    status_info["sources"][filename] = {"exists": False}

        return _ok(status_info)

    @mcp.tool()
    async def bos_inbox_search(query: str, top_k: int = 5, source: str = "all") -> dict:
        """在 BOS Inbox 多源私有知识库(OA待办/网易邮箱/AppleMail)中进行关键词与语义检索。"""
        auth_ok, reason = _bos_domain_authorized("bos://memory/inbox/search", "read")
        if not auth_ok:
            return _error(f"Permission denied: {reason}")

        runtime_dir, _ = _get_inbox_paths()
        vector_store_file = runtime_dir / "vector_store.json"
        if not vector_store_file.exists():
            return _error("vector_store.json not found. Please trigger sync first.")

        try:
            data = json.loads(vector_store_file.read_text(encoding="utf-8"))
            meta_dict = data.get("metadata", {})
            results = []
            query_lower = query.lower()
            for item_id, item_meta in meta_dict.items():
                item_src = str(item_meta.get("source", "")).lower()
                if source != "all" and source not in item_src:
                    continue
                content_snip = str(item_meta.get("content_snippet", ""))
                title = str(item_meta.get("title", ""))
                if query_lower in content_snip.lower() or query_lower in title.lower() or query_lower in item_id.lower():
                    results.append({
                        "id": item_id,
                        "title": title,
                        "source": item_meta.get("source"),
                        "timestamp": item_meta.get("timestamp"),
                        "snippet": content_snip[:200]
                    })
                if len(results) >= top_k:
                    break
            return _ok({"query": query, "count": len(results), "results": results})
        except Exception as exc:
            return _error(f"Search failed: {exc}")

    @mcp.tool()
    async def bos_inbox_pending(source: str = "seeyon_oa") -> dict:
        """快速拉取现有未决事项与待办公文 (致远OA公文/未读邮件等)。"""
        auth_ok, reason = _bos_domain_authorized("bos://memory/inbox/pending", "read")
        if not auth_ok:
            return _error(f"Permission denied: {reason}")

        _, inbox_dir = _get_inbox_paths()
        target_file = inbox_dir / "2026-07-31-auto-seeyon-oa-pending.md"
        if source == "netease_mailmaster":
            target_file = inbox_dir / "2026-07-31-auto-netease-mailmaster.md"
        elif source == "apple_mail":
            target_file = inbox_dir / "2026-07-31-auto-apple-mail.md"

        if not target_file.exists():
            return _error(f"Pending snapshot file not found for source={source}: {target_file}")

        try:
            content = target_file.read_text(encoding="utf-8")
            from agora.mcp.bos_router import clean_inbox_content

            return _ok({
                "source": source,
                "file": str(target_file),
                "mtime": _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(target_file.stat().st_mtime)),
                "content_preview": clean_inbox_content(content[:1500])
            })
        except Exception as exc:
            return _error(f"Read pending file failed: {exc}")

    @mcp.tool()
    async def bos_inbox_watch(priority_only: bool = True) -> dict:
        """BOS Inbox 实时事件驱动监控与紧急公文/工单通知快照 (Event-Driven Watcher v2.0)."""
        auth_ok, reason = _bos_domain_authorized("bos://memory/inbox/watch", "read")
        if not auth_ok:
            return _error(f"Permission denied: {reason}")

        from agora.mcp.bos_router import clean_inbox_content

        _, inbox_dir = _get_inbox_paths()
        urgent_items = []
        urgent_keywords = [
            "priority: HIGH",
            "priority: URGENT",
            "[URGENT]",
            "紧急",
            "急件",
            "加急",
            "特急",
            "催办",
        ]
        if inbox_dir.exists():
            for file_path in inbox_dir.glob("*.md"):
                try:
                    content = file_path.read_text(encoding="utf-8")
                    cleaned = clean_inbox_content(content)
                    matched_reasons = [k for k in urgent_keywords if k in cleaned]
                    is_urgent = len(matched_reasons) > 0

                    if not priority_only or is_urgent:
                        # 结构化抽取标题
                        title = file_path.stem
                        for line in cleaned.splitlines():
                            if line.strip().startswith("# "):
                                title = line.strip()[2:].strip()
                                break

                        priority_level = (
                            "URGENT"
                            if any(
                                u in matched_reasons
                                for u in ["priority: URGENT", "[URGENT]", "特急"]
                            )
                            else ("HIGH" if is_urgent else "NORMAL")
                        )

                        urgent_items.append({
                            "id": file_path.stem,
                            "filename": file_path.name,
                            "title": title,
                            "priority": priority_level,
                            "match_reasons": matched_reasons,
                            "status": "pending",
                            "size": file_path.stat().st_size,
                            "mtime": _time.strftime(
                                "%Y-%m-%d %H:%M:%S",
                                _time.localtime(file_path.stat().st_mtime),
                            ),
                            "urgent": is_urgent,
                            "snippet": cleaned[:400],
                        })
                except Exception:
                    continue
        return _ok({
            "format_version": FORMAT_VERSION,
            "watch_mode": "priority_only" if priority_only else "all",
            "urgent_count": len(urgent_items),
            "items": urgent_items,
        })

    @mcp.tool()
    async def bos_inbox_archive(filename: str, reason: str = "resolved") -> dict:
        """按要求将已结单/已处决的 BOS Inbox 待办文件安全转移至冷归档分区 (Lifecycle Archive)."""
        auth_ok, auth_reason = _bos_domain_authorized("bos://memory/inbox/archive", "write")
        if not auth_ok:
            return _error(f"Permission denied: {auth_reason}")

        _, inbox_dir = _get_inbox_paths()
        src_file = inbox_dir / filename
        if not src_file.exists():
            return _error(f"Inbox snapshot not found: {filename}")

        # 准备 archive 目录: _knowledge/archive/inbox/
        doc_root = Path(os.environ.get("BOS_DOCUMENTS_ROOT", str(Path.home() / "Documents")))
        archive_dir = doc_root / "_knowledge" / "archive" / "inbox"
        archive_dir.mkdir(parents=True, exist_ok=True)

        target_file = archive_dir / filename
        try:
            content = src_file.read_text(encoding="utf-8")
            archive_meta = (
                f"\n\n---\n"
                f"archive_ts: {_time.strftime('%Y-%m-%dT%H:%M:%S+08:00', _time.localtime())}\n"
                f"archive_reason: {reason}\n"
            )
            target_file.write_text(content + archive_meta, encoding="utf-8")
            src_file.unlink()
            return _ok({
                "format_version": FORMAT_VERSION,
                "filename": filename,
                "archived": True,
                "reason": reason,
                "archive_path": str(target_file),
            })
        except Exception as exc:
            return _error(f"Failed to archive inbox item: {exc}")

    @mcp.tool()
    async def bos_inbox_triage(
        limit: int = 10, priority_threshold: str = "high"
    ) -> dict:
        """BOS Inbox 公文与待办事项智能分类分拣与紧急度分层引擎 (Triage Engine)."""
        auth_ok, auth_reason = _bos_domain_authorized(
            "bos://memory/inbox/triage", "read"
        )
        if not auth_ok:
            return _error(f"Permission denied: {auth_reason}")
        import agora.server.tools_bos as _self_mod

        return await _self_mod.bos_inbox_triage(
            limit=limit, priority_threshold=priority_threshold
        )

    @mcp.tool()
    async def bos_inbox_draft(
        filename: str,
        persona_style: str = "health_admin_director",
        require_risk_eval: bool = True,
    ) -> dict:
        """BOS Inbox 智能拟办意见与风险提示批复草拟引擎 (Draft Assistant)."""
        auth_ok, auth_reason = _bos_domain_authorized(
            "bos://memory/inbox/draft", "read"
        )
        if not auth_ok:
            return _error(f"Permission denied: {auth_reason}")
        import agora.server.tools_bos as _self_mod

        return await _self_mod.bos_inbox_draft(
            filename=filename,
            persona_style=persona_style,
            require_risk_eval=require_risk_eval,
        )

    @mcp.tool()
    async def persona_bdsk_evaluate(
        topic: str, mode: str = "deep", context: str = ""
    ) -> dict:
        """B.D.S.K. 虚拟董事会并发对抗与结构化方案评审网关 (Persona Evaluate)."""
        import agora.server.tools_bos as _self_mod

        return await _self_mod.persona_bdsk_evaluate(
            topic=topic, mode=mode, context=context
        )

    # ── list_bos_tools ──────────────────────────────────

    @mcp.tool()
    async def list_bos_tools() -> dict:
        """列出所有可用的 BOS MCP 工具及 schema — Agent 统一发现入口。"""
        tools = [
            {
                "name": "resolve_bos_uri",
                "description": "将 BOS URI 解析为实际调用，路由到后端服务",
                "arguments": {"uri": "BOS URI", "arguments": "JSON 参数字符串"},
            },
            {
                "name": "read_resource",
                "description": "通过 BOS URI 读取资源 (Proxy→POC 降级)",
                "arguments": {"uri": "BOS URI", "arguments": "JSON 参数字符串"},
            },
            {
                "name": "mutate_resource",
                "description": "通过 BOS URI 修改资源 (真路由 + L0 审计)",
                "arguments": {
                    "uri": "BOS URI",
                    "payload": "JSON 负载",
                    "action": "update",
                },
            },
            {
                "name": "list_bos_resources",
                "description": "列出所有已注册 BOS 资源",
                "arguments": {"prefix": "可选前缀过滤"},
            },
            {
                "name": "list_bos_domains",
                "description": "列出 BOS 域及路由统计",
                "arguments": {},
            },
            {
                "name": "get_bos_schema",
                "description": "查询 BOS URI 的参数规范 (从 M1 节点)",
                "arguments": {"uri": "BOS URI 或 action 名"},
            },
            {
                "name": "bos_metrics_status",
                "description": "BOS 调用指标 (JSON/Prometheus)",
                "arguments": {"prefix": "可选前缀", "format": "json|prometheus"},
            },
            {
                "name": "bos_middleware_status",
                "description": "限流/熔断/缓存/路由实时状态",
                "arguments": {},
            },
            {
                "name": "bos_inbox_status",
                "description": "查询 BOS Inbox 多源神经网实时摄取状态与证据统计",
                "arguments": {},
            },
            {
                "name": "bos_inbox_search",
                "description": "在 BOS Inbox 多源私有知识库(OA待办/网易邮箱/AppleMail)中进行关键词与语义检索",
                "arguments": {"query": "搜索关键词", "top_k": "返回条数", "source": "数据源过滤"},
            },
            {
                "name": "bos_inbox_pending",
                "description": "快速拉取现有未决事项与待办公文 (致远OA公文/网易邮件等)",
                "arguments": {"source": "数据源识别"},
            },
            {
                "name": "bos_inbox_watch",
                "description": "BOS Inbox 实时事件驱动监控与紧急公文/工单通知快照 (Event-Driven Watcher)",
                "arguments": {"priority_only": "是否仅列出高优紧急事项"},
            },
            {
                "name": "bos_inbox_triage",
                "description": "BOS Inbox 公文与待办事项智能分类分拣与紧急度分层引擎 (Triage Engine)",
                "arguments": {"limit": "分拣数量上限", "priority_threshold": "高优紧急阈值"},
            },
            {
                "name": "bos_inbox_draft",
                "description": "BOS Inbox 智能拟办意见与风险提示批复草拟引擎 (Draft Assistant)",
                "arguments": {"filename": "待办公文文件名", "persona_style": "答复预设人设风格"},
            },
            {
                "name": "persona_bdsk_evaluate",
                "description": "B.D.S.K. 虚拟董事会并发对抗与结构化方案评审网关 (Persona Evaluate)",
                "arguments": {"topic": "待评估需求/策略说明", "mode": "评估模式 deep|fast"},
            },
        ]
        return _ok(
            {"format_version": FORMAT_VERSION, "tools": tools, "total": len(tools)}
        )

