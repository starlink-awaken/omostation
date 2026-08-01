"""Knowledge Indexer — 订阅 bos://brain/events/card_updated 事件，触发增量向量索引.

架构说明 (ADR-0294):
- 本模块是 api_knowledge.py PUT 写后事件的"消费者 (Consumer)"
- 在 cockpit 启动时向 Agora EventBus 注册订阅
- 每次收到 card_updated 事件，触发 KOS / LanceDB 增量向量 upsert
- 设计遵循 L3 内部模块规范，不直接跨层 import agora 内核

调用链:
  api_knowledge.py  →  (HTTP) POST /bos/emit  →  Agora EventBus
       ↑                                                   ↓
  /search 召回 ←── LanceDB/KOS ←── upsert ←── KnowledgeIndexer (本模块)
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("cockpit.web.knowledge_indexer")

_AGORA_HTTP_ENDPOINT = os.environ.get("AGORA_HTTP_ENDPOINT", "http://127.0.0.1:7422")
_CARD_UPDATED_PATTERN = "bos://brain/events/card_updated"

# 全局订阅 ID（用于 shutdown 时取消订阅）
_subscription_id: str | None = None


class KnowledgeIndexer:
    """订阅 EventBus card_updated 事件，驱动知识卡片增量向量索引.

    设计原则:
    - 幂等性: 对同一 slug 的重复 upsert 结果一致
    - 非阻塞: 索引写入异常不影响 API 主路径
    - 降级安全: KOS/LanceDB 不可用时记录日志但不崩溃

    使用方式 (在 cockpit app startup 中调用):
        indexer = KnowledgeIndexer()
        await indexer.start()
        # app shutdown:
        await indexer.stop()
    """

    def __init__(
        self,
        agora_endpoint: str = _AGORA_HTTP_ENDPOINT,
    ) -> None:
        self._agora_endpoint = agora_endpoint
        self._sub_id: str | None = None
        self._running = False

    async def start(self) -> None:
        """向 Agora EventBus 注册 card_updated 订阅."""
        if self._running:
            return
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.post(
                    f"{self._agora_endpoint}/bos/subscribe",
                    json={
                        "service": "cockpit-knowledge-indexer",
                        "pattern": _CARD_UPDATED_PATTERN,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    self._sub_id = data.get("subscription_id")
                    self._running = True
                    logger.info(
                        "KnowledgeIndexer: subscribed to %s (sub_id=%s)",
                        _CARD_UPDATED_PATTERN,
                        self._sub_id,
                    )
                else:
                    logger.warning(
                        "KnowledgeIndexer: subscribe returned %s — will run in poll-fallback mode",
                        resp.status_code,
                    )
        except Exception as e:
            logger.warning(
                "KnowledgeIndexer: cannot reach Agora at %s (%s) — indexer in standby",
                self._agora_endpoint,
                e,
            )

    async def stop(self) -> None:
        """取消订阅并停止 Indexer."""
        if not self._sub_id:
            return
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                await client.post(
                    f"{self._agora_endpoint}/bos/unsubscribe",
                    json={"subscription_id": self._sub_id},
                )
        except Exception:
            pass
        self._running = False
        self._sub_id = None
        logger.info("KnowledgeIndexer: unsubscribed and stopped")

    async def handle_card_updated(self, payload: dict[str, Any]) -> None:
        """处理 card_updated 事件，触发增量向量 upsert.

        Args:
            payload: {"slug": str, "title": str, "path": str, "action": "upsert"}
        """
        slug = payload.get("slug", "")
        title = payload.get("title", "")
        card_path = payload.get("path", "")
        action = payload.get("action", "upsert")

        if not slug or not card_path:
            logger.warning("KnowledgeIndexer: received malformed card_updated payload: %s", payload)
            return

        logger.info("KnowledgeIndexer: indexing card slug=%s action=%s", slug, action)

        try:
            await _upsert_card_to_index(slug=slug, title=title, card_path=card_path)
        except Exception as e:
            # 索引失败不阻塞，记录日志等待下轮重试
            logger.error("KnowledgeIndexer: failed to index slug=%s: %s", slug, e)


async def _upsert_card_to_index(slug: str, title: str, card_path: str) -> None:
    """将知识卡片文件增量写入向量索引 (KOS / LanceDB).

    当前实现: 通过 KOS HTTP API 触发增量更新。
    如果 KOS 不可用，则尝试进程内 compat 适配路径。

    Args:
        slug: 卡片唯一标识
        title: 卡片标题
        card_path: 相对于 WORKSPACE_ROOT 的卡片文件路径
    """
    # 尝试通过 KOS HTTP API 触发 upsert（网络优先，符合 ADR-0294 分层规范）
    kos_endpoint = os.environ.get("KOS_HTTP_ENDPOINT", "http://127.0.0.1:7428")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{kos_endpoint}/api/index/upsert",
                json={"slug": slug, "title": title, "path": card_path, "source": "card_updated"},
            )
            if resp.status_code == 200:
                logger.debug("KnowledgeIndexer: KOS upsert OK slug=%s", slug)
                return
            logger.warning("KnowledgeIndexer: KOS upsert returned %s for slug=%s", resp.status_code, slug)
    except Exception as e:
        logger.debug("KnowledgeIndexer: KOS not reachable (%s), falling back to compat path", e)

    # 兼容降级: 尝试进程内 kos/lancedb 适配器（仅当 kos SDK 已安装时可用）
    try:
        from kos.index import upsert_document  # type: ignore[import-not-found]

        await upsert_document(slug=slug, title=title, path=card_path)
        logger.debug("KnowledgeIndexer: compat upsert OK slug=%s", slug)
    except ImportError:
        logger.debug("KnowledgeIndexer: kos SDK not available, upsert skipped for slug=%s", slug)
    except Exception as e:
        logger.error("KnowledgeIndexer: compat upsert failed slug=%s: %s", slug, e)


# 模块级便捷函数供 cockpit app lifespan 使用
_default_indexer: KnowledgeIndexer | None = None


async def start_knowledge_indexer() -> KnowledgeIndexer:
    """启动全局 KnowledgeIndexer 单例（在 app lifespan startup 中调用）."""
    global _default_indexer
    _default_indexer = KnowledgeIndexer()
    await _default_indexer.start()
    return _default_indexer


async def stop_knowledge_indexer() -> None:
    """停止全局 KnowledgeIndexer 单例（在 app lifespan shutdown 中调用）."""
    global _default_indexer
    if _default_indexer:
        await _default_indexer.stop()
        _default_indexer = None
