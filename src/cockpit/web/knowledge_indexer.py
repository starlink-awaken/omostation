"""Knowledge Indexer — 订阅 card_updated 事件，触发增量向量索引.

Accepts both:
  - bos://memory/events/card_updated  (canonical, ADR-0372)
  - bos://brain/events/card_updated   (legacy ADR-0294, dual-accept during migration)


架构说明 (ADR-0294):
- 本模块是 api_knowledge.py PUT 写后事件的"消费者 (Consumer)"
- 启动时通过 Agora /v1/tools/call subscribe_event 注册 HTTP callback_url
- Agora EventBus 调用 POST /api/knowledge/indexer/callback 推送事件
- Callback handler 触发 KOS/LanceDB 增量 upsert

事件流:
  PUT /api/knowledge/put
    → /v1/tools/call publish_event(bos://memory/events/card_updated)
    → Agora EventBus → POST {cockpit}/api/knowledge/indexer/callback
    → dual-accept memory + brain card_updated
    → KOS HTTP upsert / LanceDB upsert

Agora 实际 HTTP 端点:
  /v1/tools/call    — 调用任意 MCP tool（含 publish_event, subscribe_event）
  /health           — 健康检查
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("cockpit.web.knowledge_indexer")

_AGORA_HTTP = os.environ.get("AGORA_HTTP_ENDPOINT", "http://127.0.0.1:7422")
_COCKPIT_PORT = int(os.environ.get("COCKPIT_DASHBOARD_PORT", "8090"))
_COCKPIT_HOST = os.environ.get("COCKPIT_HOST", "127.0.0.1")
_KOS_HTTP = os.environ.get("KOS_HTTP_ENDPOINT", "http://127.0.0.1:7430")

# Router 暴露 callback 端点（在 dashboard_server.py 中 include）
callback_router = APIRouter()

_subscription_id: str | None = None
_indexer_task: asyncio.Task | None = None


# ─── Callback endpoint (Agora → Cockpit push) ─────────────────────────────


@callback_router.post("/api/knowledge/indexer/callback")
async def knowledge_indexer_callback(request: Request):
    """接收 Agora EventBus 推送的 card_updated 事件，触发增量向量索引."""
    try:
        try:
            event = await request.json()
        except Exception:
            return JSONResponse({"status": "error", "error": "invalid JSON body"}, status_code=400)

        if not isinstance(event, dict):
            return JSONResponse({"status": "error", "error": "invalid event payload"}, status_code=400)

        event_type = event.get("type", "")
        payload = event.get("data", {})

        # Dual-accept memory (canonical) + brain (legacy) card_updated URIs
        card_updated = {
            "bos://memory/events/card_updated",
            "bos://brain/events/card_updated",
        }
        if event_type not in card_updated:
            # 其他事件类型静默忽略（容错：订阅 pattern 可能宽泛）
            return JSONResponse({"status": "ok", "action": "ignored", "event_type": event_type})

        slug = payload.get("slug", "")
        if slug:
            asyncio.get_running_loop().create_task(_upsert_card(slug, payload))

        return JSONResponse({"status": "ok", "action": "upsert_queued", "slug": slug})
    except Exception as e:
        logger.warning("knowledge_indexer_callback error: %s", e)
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


# ─── KOS upsert ────────────────────────────────────────────────────────────


async def _upsert_card(slug: str, payload: dict) -> None:
    """将 card 推入 KOS/LanceDB 增量向量索引."""
    from cockpit.compat import WORKSPACE_ROOT

    card_path = WORKSPACE_ROOT / "data" / "cards" / f"{slug}.md"
    if not card_path.exists():
        logger.warning("upsert_card: card not found at %s", card_path)
        return

    content = card_path.read_text(encoding="utf-8")
    title = payload.get("title", slug)

    # 优先通过 KOS HTTP PUT /api/index/upsert（若 KOS 可用）
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{_KOS_HTTP}/api/index/upsert",
                json={"slug": slug, "title": title, "content": content},
            )
            if resp.status_code < 300:
                logger.info("kos_upsert ok: slug=%s", slug)
                return
    except Exception as e:
        logger.debug("KOS upsert network error, trying LanceDB direct: %s", e)

    # 降级：直接写 LanceDB（进程内）
    try:
        from cockpit.kos_proxy import _get_kos_client  # type: ignore[import-not-found]

        kos = _get_kos_client()
        if kos:
            await asyncio.to_thread(kos.upsert, slug=slug, title=title, content=content)
            logger.info("lancedb_direct_upsert ok: slug=%s", slug)
    except Exception as e:
        logger.warning("knowledge_indexer upsert all paths failed for %s: %s", slug, e)


# ─── Subscription lifecycle ─────────────────────────────────────────────────


async def _register_subscription() -> None:
    """向 Agora 注册 card_updated 事件订阅（双 pattern：memory + brain，带指数退避重试）."""
    global _subscription_id

    callback_url = f"http://{_COCKPIT_HOST}:{_COCKPIT_PORT}/api/knowledge/indexer/callback"
    # Dual-subscribe during ADR-0372 migration window
    patterns = (
        "bos://memory/events/card_updated",
        "bos://brain/events/card_updated",
    )

    for attempt in range(5):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                last_sub_id = None
                for pattern in patterns:
                    body = {
                        "tool": "subscribe_event",
                        "arguments": {
                            "pattern": pattern,
                            "callback_url": callback_url,
                        },
                    }
                    resp = await client.post(f"{_AGORA_HTTP}/v1/tools/call", json=body)
                    if resp.status_code == 200:
                        data = resp.json()
                        sub_id = data.get("result", {}).get("subscription_id") or data.get("subscription_id")
                        if sub_id:
                            last_sub_id = sub_id
                            logger.info(
                                "knowledge_indexer: subscribed pattern=%s sub_id=%s callback=%s",
                                pattern,
                                sub_id,
                                callback_url,
                            )
                if last_sub_id:
                    _subscription_id = last_sub_id
                    return
        except Exception as e:
            wait = 2**attempt
            logger.info("knowledge_indexer: agora not ready (attempt %d), retry in %ds: %s", attempt + 1, wait, e)
            await asyncio.sleep(wait)

    logger.warning(
        "knowledge_indexer: could not subscribe after 5 attempts — "
        "indexer will retry on next startup. "
        "Cards written while Agora offline are NOT lost (files persisted)."
    )


async def _keepalive_loop() -> None:
    """定期续订 subscription（防止 Agora TTL 清理），每 5 分钟一次."""
    while True:
        await asyncio.sleep(300)
        try:
            await _register_subscription()
        except Exception as e:
            logger.debug("knowledge_indexer keepalive error: %s", e)


# ─── Public lifecycle API ────────────────────────────────────────────────────


async def start_knowledge_indexer() -> None:
    """在 cockpit 启动时调用：注册 Agora subscription + 启动 keepalive 任务.

    设计原则：
    - 非阻塞：subscription 注册失败不阻止 cockpit 启动
    - 自恢复：keepalive loop 每 5 分钟重试注册（Agora 重启后自动恢复）
    - 幂等：重复调用安全（旧 task 自然失效）
    """
    global _indexer_task

    logger.info("knowledge_indexer: starting (agora=%s cockpit=%s:%d)", _AGORA_HTTP, _COCKPIT_HOST, _COCKPIT_PORT)

    # 首次注册（独立 task，不阻塞 lifespan）
    loop = asyncio.get_running_loop()
    loop.create_task(_register_subscription(), name="knowledge_indexer_subscribe")

    # Keepalive loop（每 5 分钟续订）
    _indexer_task = loop.create_task(_keepalive_loop(), name="knowledge_indexer_keepalive")
    logger.info("knowledge_indexer: keepalive task started")


async def stop_knowledge_indexer() -> None:
    """在 cockpit 关闭时调用：取消 keepalive task."""
    global _indexer_task
    if _indexer_task and not _indexer_task.done():
        _indexer_task.cancel()
        logger.info("knowledge_indexer: keepalive task cancelled")
    _indexer_task = None
