from __future__ import annotations

"""
Extracted from SharedBrain D_Harvest → minerva.

---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# Knowledge Store ≡ Module
# 内涵 ≝ {Knowledge, Store}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, KnowledgeStore)}
# 功能 ⊢ {Knowledge_Store, Init_Knowledge, Validate_Store}
# =============================================================================

# ---
# domain: D-Harvest
# layer: organ
# status: active
# ---

"""
知识库存储层 - SQLite实现

提供持久化知识存储，支持FactGraph集成和向量检索准备。
遵循SOLID原则，简洁高效。
"""
import asyncio
import json
import logging
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

# 知识同步事件总线（可选导入）
_sync_bus = None

# 索引管理器（可选导入）
_index_manager = None


def _get_index_manager() -> Any | None:
    """延迟加载索引管理器（minerva中通过依赖注入配置）"""
    global _index_manager
    if _index_manager is None:
        _log.debug("AutoIndexManager not configured in minerva - use set_index_manager() to configure")
    return _index_manager


def set_index_manager(manager: Any) -> None:
    """配置索引管理器（依赖注入）"""
    global _index_manager
    _index_manager = manager
    _log.info("AutoIndexManager configured via dependency injection")


class KnowledgeStore:
    """
    知识库存储 - 使用SQLite提供高效持久化

    职责：
    - 存储验证后的知识条目
    - 支持去重和查询
    - 为FactGraph集成准备数据
    - 为向量嵌入提供批量导出

    遵循原则：
    - KISS: 简单的SQLite存储，不过度设计
    - SRP: 只负责存储，不负责提取或验证
    - DRY: 复用D-Memory的SQLiteRelationalProvider模式
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """
        初始化知识库存储

        Args:
            db_path: 数据库文件路径（默认: .omc/store/knowledge.db）
        """
        self.db_path = db_path or Path(".omc/store/knowledge.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        # FIX: 添加线程锁保护 SQLite 并发访问
        self._db_lock = threading.Lock()

        # 初始化数据库表
        self._init_schema()

    def _init_schema(self) -> None:
        """初始化数据库表结构"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 知识条目表 - 主存储
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uri TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                metadata TEXT,
                visibility TEXT DEFAULT 'private',
                quality_score REAL DEFAULT 0.0,
                harvested_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                content_hash TEXT UNIQUE,
                factgraph_synced BOOLEAN DEFAULT 0,
                vector_synced BOOLEAN DEFAULT 0
            )
        """)

        # 索引优化
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_uri
            ON knowledge_items(uri)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_content_hash
            ON knowledge_items(content_hash)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_quality_score
            ON knowledge_items(quality_score)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_harvested_at
            ON knowledge_items(harvested_at)
        """)
        # FIX: 添加 factgraph_synced 索引，优化查询性能
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_factgraph_synced
            ON knowledge_items(factgraph_synced)
        """)
        # FIX: 添加 vector_synced 索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_vector_synced
            ON knowledge_items(vector_synced)
        """)

        # 来源统计表 - 用于监控
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS source_stats (
                source_id TEXT PRIMARY KEY,
                total_harvested INTEGER DEFAULT 0,
                successful_harvests INTEGER DEFAULT 0,
                failed_harvests INTEGER DEFAULT 0,
                last_harvest_at TEXT,
                last_harvest_status TEXT,
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)

        conn.commit()
        _log.info(f"Knowledge store initialized at {self.db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接（延迟连接，线程安全）"""
        with self._db_lock:
            if not self._conn:
                self._conn = sqlite3.connect(str(self.db_path), timeout=10, check_same_thread=False)
                self._conn.row_factory = sqlite3.Row
            return self._conn

    def _compute_content_hash(self, uri: str, title: str, body: str) -> str:
        """
        计算内容哈希用于去重

        注意：URI不参与哈希计算，确保相同内容从不同来源收割时能被去重

        Args:
            uri: 资源URI（不参与哈希计算）
            title: 标题
            body: 正文内容

        Returns:
            SHA256哈希值
        """
        import hashlib

        # 只用title和body计算哈希，忽略URI
        content = f"{title}|{body[:1000]}"  # 使用前1000字符计算哈希
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def store_knowledge(
        self,
        uri: str,
        title: str,
        body: str,
        metadata: dict[str, Any] | None = None,
        visibility: str = "private",
        quality_score: float = 0.0,
        harvested_at: str | None = None,
    ) -> int | None:
        """
        存储知识条目

        Args:
            uri: 资源URI
            title: 标题
            body: 正文内容
            metadata: 元数据（JSON序列化）
            visibility: 可见性（private/federated）
            quality_score: 质量分数
            harvested_at: 收割时间（ISO格式）

        Returns:
            插入的记录ID，如果已存在则返回None
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # 计算内容哈希
        content_hash = self._compute_content_hash(uri, title, body)

        # 检查是否已存在（去重）
        cursor.execute("SELECT id FROM knowledge_items WHERE content_hash = ?", (content_hash,))
        if cursor.fetchone():
            _log.debug(f"Duplicate knowledge item skipped: {uri}")
            return None

        # 插入新记录
        harvested_at = harvested_at or datetime.now(UTC).isoformat()
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)

        try:
            cursor.execute(
                """
                INSERT INTO knowledge_items
                (uri, title, body, metadata, visibility, quality_score,
                 harvested_at, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    uri,
                    title,
                    body,
                    metadata_json,
                    visibility,
                    quality_score,
                    harvested_at,
                    content_hash,
                ),
            )

            conn.commit()
            item_id = cursor.lastrowid
            _log.info(f"Stored knowledge item #{item_id}: {uri}")

            # 发布知识创建事件（异步，fire-and-forget）
            if item_id is not None:
                _publish_knowledge_created_event(item_id, uri, title, quality_score, metadata)

            # 触发增量索引更新（异步，fire-and-forget）
            if item_id is not None:
                _trigger_index_update("create", item_id, uri, title, body, metadata)

            return item_id

        except sqlite3.Error as e:
            conn.rollback()
            _log.error(f"Failed to store knowledge item: {e}")
            return None

    async def search_knowledge(
        self, query: str, limit: int = 20, min_quality: float = 0.0, use_bm25: bool = True
    ) -> list[dict[str, Any]]:
        """
        搜索知识条目（支持 BM25 和简单文本匹配）

        Args:
            query: 搜索关键词
            limit: 返回数量限制
            min_quality: 最低质量分数
            use_bm25: 是否使用 BM25 搜索（默认启用）

        Returns:
            匹配的知识条目列表
        """
        # 如果启用 BM25，使用 BM25 搜索
        if use_bm25:
            try:
                from minerva.search.bm25_searcher import BM25Searcher

                searcher = BM25Searcher()
                # 确保索引已构建
                if not searcher._index_built:
                    await searcher.build_index(self, min_quality=0.0)

                results = await searcher.search(query, top_k=limit, min_quality=min_quality)

                # 转换为字典格式
                return [
                    {
                        "id": r.id,
                        "title": r.title,
                        "body": r.body,
                        "uri": r.uri,
                        "quality_score": r.quality_score,
                        "harvested_at": r.harvested_at,
                        "metadata": r.metadata,
                        "bm25_score": r.bm25_score,
                        "matched_terms": r.matched_terms,
                    }
                    for r in results
                ]
            except (OSError, ValueError, KeyError) as e:
                _log.warning(f"[KnowledgeStore] BM25 search failed, falling back to LIKE: {e}")
                # 失败后回退到 LIKE 查询

        # 简单文本搜索：标题或正文包含查询词
        conn = self._get_connection()
        cursor = conn.cursor()

        # FIX: Escape LIKE wildcard characters to prevent injection
        # User input could contain %, _, or \ which have special meaning in LIKE
        safe_query = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        search_pattern = f"%{safe_query}%"

        cursor.execute(
            """
            SELECT * FROM knowledge_items
            WHERE quality_score >= ?
            AND (title LIKE ? ESCAPE '\\' OR body LIKE ? ESCAPE '\\')
            ORDER BY quality_score DESC, harvested_at DESC
            LIMIT ?
        """,
            (min_quality, search_pattern, search_pattern, limit),
        )

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_knowledge(self, item_id: int) -> dict[str, Any] | None:
        """
        获取单条知识

        Args:
            item_id: 知识条目ID

        Returns:
            知识条目字典，不存在则返回None
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM knowledge_items WHERE id = ?", (item_id,))
        row = cursor.fetchone()

        if not row:
            return None

        return dict(row)

    async def list_knowledge(
        self,
        limit: int = 100,
        offset: int = 0,
        min_quality: float = 0.0,
        source_uri: str | None = None,
        unsynced_to_factgraph: bool = False,
    ) -> list[dict[str, Any]]:
        """
        列出知识条目

        Args:
            limit: 返回数量限制
            offset: 偏移量
            min_quality: 最低质量分数
            source_uri: 筛选特定来源URI（前缀匹配）
            unsynced_to_factgraph: 仅返回未同步到FactGraph的条目

        Returns:
            知识条目列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # 构建查询
        conditions = ["quality_score >= ?"]
        params: list[Any] = [min_quality]

        # FIX: Escape LIKE wildcard characters to prevent injection
        if source_uri:
            safe_uri = source_uri.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            conditions.append("uri LIKE ? ESCAPE '\\'")
            params.append(f"{safe_uri}%")

        if unsynced_to_factgraph:
            conditions.append("factgraph_synced = 0")

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT * FROM knowledge_items
            WHERE {where_clause}
            ORDER BY harvested_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    async def mark_factgraph_synced(self, item_ids: list[int]) -> int:
        """
        标记已同步到FactGraph

        Args:
            item_ids: 知识条目ID列表

        Returns:
            成功标记的数量
        """
        if not item_ids:
            return 0

        conn = self._get_connection()
        cursor = conn.cursor()

        placeholders = ",".join("?" * len(item_ids))
        cursor.execute(
            f"""
            UPDATE knowledge_items
            SET factgraph_synced = 1
            WHERE id IN ({placeholders})
        """,
            item_ids,
        )

        conn.commit()
        updated = cursor.rowcount
        _log.info(f"Marked {updated} items as synced to FactGraph")
        return updated

    async def export_for_embedding(self, limit: int = 1000, unsynced_only: bool = True) -> list[dict[str, Any]]:
        """
        导出待向量嵌入的知识条目

        Args:
            limit: 导出数量限制
            unsynced_only: 是否仅导出未同步的条目

        Returns:
            待嵌入的知识条目列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        condition = "vector_synced = 0" if unsynced_only else "1=1"

        cursor.execute(
            f"""
            SELECT id, title, body, uri
            FROM knowledge_items
            WHERE {condition} AND quality_score >= 0.6
            ORDER BY quality_score DESC
            LIMIT ?
        """,
            (limit,),
        )

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    async def mark_vector_synced(self, item_ids: list[int]) -> int:
        """
        标记已生成向量嵌入

        Args:
            item_ids: 知识条目ID列表

        Returns:
            成功标记的数量
        """
        if not item_ids:
            return 0

        conn = self._get_connection()
        cursor = conn.cursor()

        placeholders = ",".join("?" * len(item_ids))
        cursor.execute(
            f"""
            UPDATE knowledge_items
            SET vector_synced = 1
            WHERE id IN ({placeholders})
        """,
            item_ids,
        )

        conn.commit()
        updated = cursor.rowcount
        _log.info(f"Marked {updated} items as vector synced")
        return updated

    async def update_source_stats(self, source_id: str, success: bool = True, items_count: int = 0) -> None:
        """
        更新来源统计信息

        Args:
            source_id: 来源标识
            success: 本次收割是否成功
            items_count: 收割的知识条目数量
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = datetime.now(UTC).isoformat()

        # 尝试更新现有记录
        cursor.execute(
            """
            UPDATE source_stats
            SET total_harvested = total_harvested + 1,
                successful_harvests = successful_harvests + ?,
                failed_harvests = failed_harvests + ?,
                last_harvest_at = ?,
                last_harvest_status = ?,
                updated_at = ?
            WHERE source_id = ?
        """,
            (
                1 if success else 0,
                0 if success else 1,
                now,
                "success" if success else "failed",
                now,
                source_id,
            ),
        )

        # 如果没有更新任何行，则插入新记录
        if cursor.rowcount == 0:
            cursor.execute(
                """
                INSERT INTO source_stats
                (source_id, total_harvested, successful_harvests,
                 failed_harvests, last_harvest_at, last_harvest_status)
                VALUES (?, 1, ?, ?, ?, ?)
            """,
                (
                    source_id,
                    1 if success else 0,
                    0 if success else 1,
                    now,
                    "success" if success else "failed",
                ),
            )

        conn.commit()

    async def get_stats(self) -> dict[str, Any]:
        """
        获取存储统计信息

        Returns:
            统计信息字典
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # 总条目数
        cursor.execute("SELECT COUNT(*) FROM knowledge_items")
        total_items = cursor.fetchone()[0]

        # 平均质量分数
        cursor.execute("SELECT AVG(quality_score) FROM knowledge_items")
        avg_quality = cursor.fetchone()[0] or 0.0

        # FactGraph同步状态
        cursor.execute("""
            SELECT
                COUNT(*) FILTER (WHERE factgraph_synced = 1) as synced,
                COUNT(*) FILTER (WHERE factgraph_synced = 0) as unsynced
            FROM knowledge_items
        """)
        row = cursor.fetchone()
        fg_synced, fg_unsynced = row[0], row[1]

        # 向量同步状态
        cursor.execute("""
            SELECT
                COUNT(*) FILTER (WHERE vector_synced = 1) as synced,
                COUNT(*) FILTER (WHERE vector_synced = 0) as unsynced
            FROM knowledge_items
        """)
        row = cursor.fetchone()
        vec_synced, vec_unsynced = row[0], row[1]

        return {
            "total_items": total_items,
            "average_quality_score": round(avg_quality, 3),
            "factgraph": {"synced": fg_synced, "unsynced": fg_unsynced},
            "vector": {"synced": vec_synced, "unsynced": vec_unsynced},
        }

    def close(self) -> None:
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None
            _log.info("Knowledge store connection closed")


# =============================================================================
# 知识同步事件发布辅助函数
# =============================================================================


def _get_sync_bus() -> Any | None:
    """延迟加载事件总线（minerva中通过依赖注入配置）"""
    global _sync_bus
    if _sync_bus is None:
        _log.debug("KnowledgeSyncEventBus not configured in minerva - use set_sync_bus() to configure")
    return _sync_bus


def set_sync_bus(bus: Any) -> None:
    """配置事件总线（依赖注入）"""
    global _sync_bus
    _sync_bus = bus
    _log.info("KnowledgeSyncEventBus configured via dependency injection")


def _publish_knowledge_created_event(
    item_id: int,
    uri: str,
    title: str,
    quality_score: float,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    发布知识创建事件（异步，fire-and-forget）

    Args:
        item_id: 知识条目ID
        uri: 资源URI
        title: 标题
        quality_score: 质量分数
        metadata: 元数据
    """
    try:
        bus = _get_sync_bus()
        if bus is not None and not bus._running:
            bus.start()

        if bus is not None:
            # 异步发布，不等待结果
            asyncio.create_task(
                bus.publish_knowledge_created(
                    item_id=item_id,
                    uri=uri,
                    title=title,
                    quality_score=quality_score,
                    metadata=metadata,
                )
            )
            _log.debug(f"Published knowledge_created event for item #{item_id}")

    except (ImportError, AttributeError, RuntimeError) as exc:
        # 事件总线不可用不是错误，静默处理
        _log.debug(f"Failed to publish knowledge event: {exc}")


def _trigger_index_update(
    action: str,
    item_id: int,
    uri: str,
    title: str,
    body: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    触发增量索引更新（异步，fire-and-forget）

    Args:
        action: 操作类型 ("create", "update", "delete")
        item_id: 知识条目ID
        uri: 资源URI
        title: 标题
        body: 正文
        metadata: 元数据
    """
    try:
        manager = _get_index_manager()
        if manager is not None:
            # 异步触发索引更新，不等待结果
            asyncio.create_task(
                manager.on_knowledge_change(
                    action=action,
                    item_id=item_id,
                    data={
                        "uri": uri,
                        "title": title,
                        "body": body,
                        "metadata": metadata or {},
                    },
                )
            )
            _log.debug(f"Triggered index update for item #{item_id}")
    except (ImportError, AttributeError, RuntimeError) as exc:
        # 索引管理器不可用不是错误，静默处理
        _log.debug(f"Failed to trigger index update: {exc}")
