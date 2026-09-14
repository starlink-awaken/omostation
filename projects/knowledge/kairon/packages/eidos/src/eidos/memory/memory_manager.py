from __future__ import annotations

import sqlite3

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""

import json
import logging
import os
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from kairon_utils import atomic_write_json

from .archetype_loader import ArchetypeLoader, get_archetype_loader  # type: ignore[reportMissingImports]
from .storage_dal import SQLiteError, SQLiteRelationalProvider  # type: ignore[reportMissingImports]

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Memory_Organ ≡ Memory_System
# 内涵 ≝ {Store, Retrieve, Index, Compact}
# 外延 ≝ {m | m ∈ D-Memory ∧ persists(m, Knowledge)}
# 功能 ⊢ {StoreMemories, RetrieveMemories, MaintainIndex}
# =============================================================================

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Sisyphus'
Authority: organs/D-Memory/AGENTS.md
Layer: L3
Constraint: "[!] SIX_LAYER_MEMORY_PROTOCOL"
Summary: 'MemoryManager: 六层记忆管理系统统一接口（Alpha 阶段实现）'
---
"""
# 🧠 六层记忆管理系统 (MemoryManager)
# 职责: 提供 Layer 0-5 的统一读写接口，管理记忆生命周期
#
# 层级定义:
#   Layer 0 - 基因记忆 (Genetic):   只读，来自 Z-Spore/archetypes/
#   Layer 1 - 临时记忆 (Transient):  进程内 dict，任务完成后清理
#   Layer 2 - 私有记忆 (Private):    SQLite per-agent，持久化
#   Layer 3 - 共享记忆 (Shared):     SQLite per-task，任务完成后清理
#   Layer 4 - 共识记忆 (Consensus):  D-Memory 域文件（Alpha 简化实现）
#   Layer 5 - 集体记忆 (Collective): L2 规则文件，只读（Alpha 预留接口）

_log = logging.getLogger(__name__)

# 基础存储路径（支持环境变量覆盖）
_BASE_DIR = Path(os.environ.get("BOS_MEMORY_DIR", "/tmp/sharedbrain/memory"))

# SQLite 连接池最大连接数
_MAX_POOL_SIZE = 10

type JSONScalar = str | int | float | bool | None
type JSONValue = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]
type SovereignView = dict[str, object]


class _OrganBase:
    """Local stub replacing nucleus CoreService for memory_manager."""

    def __init__(self) -> None: ...

    def initialize(self) -> None: ...

    def shutdown(self) -> None: ...


@dataclass
class MemoryMount:
    """Describes a mounted memory view."""

    mount_type: str
    mount_id: str
    source: str
    writable: bool = False
    scope: str = ""
    owner_id: str = ""
    governance_scope: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "mount_type": self.mount_type,
            "mount_id": self.mount_id,
            "source": self.source,
            "writable": self.writable,
            "scope": self.scope,
            "owner_id": self.owner_id,
            "governance_scope": self.governance_scope,
        }


@dataclass
class MemorySovereigntyContext:
    """Request-scoped sovereignty context for memory consumers."""

    owner_id: str
    primary_scope: str
    role_id: str = ""
    task_id: str = ""
    mount_summary: dict[str, object] | None = None
    sovereignty_level: str = "task"


class SecurityManagerProtocol(Protocol):
    def check_permission(self, agent_id: str, resource: str, action: str) -> None: ...

    def filter_sensitive_info(self, value: JSONValue) -> JSONValue: ...


class SQLiteConnectionProtocol(Protocol):
    def execute(self, statement: str, parameters: tuple[object, ...] = ()) -> sqlite3.Cursor: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class _ConnectionPool(_OrganBase):
    """
    轻量级 SQLite 连接池。
    使用上下文管理器获取连接，自动提交/回滚，用完归还池中。
    """

    def __init__(self, db_path: str, max_size: int = _MAX_POOL_SIZE) -> None:
        super().__init__()
        self._db_path = db_path
        self._max_size = max_size
        self._provider = SQLiteRelationalProvider(db_path)
        self._lock = threading.RLock()

    @contextmanager
    def get(self) -> Generator[SQLiteConnectionProtocol]:
        with self._lock:
            self._provider.connect()
            conn = self._provider._conn
            if conn is None:
                raise RuntimeError(f"failed to open memory manager database: {self._db_path}")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def close_all(self) -> None:
        """关闭池中所有连接"""
        with self._lock:
            try:
                self._provider.disconnect()
            except (OSError, AttributeError) as e:
                _log.warning("db connection close failed: %s", e)


def _init_private_schema(conn: SQLiteConnectionProtocol) -> None:
    """初始化 Layer 2 私有记忆 Schema"""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS private_memory (
            key          TEXT PRIMARY KEY,
            value        TEXT NOT NULL,
            created_at   REAL NOT NULL,
            accessed_at  REAL NOT NULL,
            access_count INTEGER DEFAULT 0
        )
    """
    )
    conn.commit()


def _init_shared_schema(conn: SQLiteConnectionProtocol) -> None:
    """初始化 Layer 3 共享记忆 Schema"""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS shared_memory (
            key          TEXT PRIMARY KEY,
            value        TEXT NOT NULL,
            writer_agent TEXT NOT NULL,
            created_at   REAL NOT NULL,
            updated_at   REAL NOT NULL
        )
    """
    )
    conn.commit()


class MemoryManager(_OrganBase):
    """
    六层记忆管理系统统一接口。

    使用方式（推荐上下文管理器）：
        with MemoryManager(agent_id="agent-001", task_id="task-001") as mem:
            mem.write_transient("key", "value")
            val, layer = mem.read_memory("key")

    或手动管理：
        mem = MemoryManager(agent_id="agent-001", task_id="task-001")
        try:
            ...
        finally:
            mem.close()
    """

    def __init__(
        self,
        agent_id: str,
        task_id: str,
        archetype_loader: ArchetypeLoader | None = None,
        base_dir: Path | None = None,
        security_manager: SecurityManagerProtocol | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.task_id = task_id
        self.status = "active"
        self._loader = archetype_loader or get_archetype_loader()
        self._base_dir = base_dir or _BASE_DIR
        self._security = security_manager
        self._base_dir.mkdir(parents=True, exist_ok=True)

        # Layer 1: 临时记忆（进程内 dict）
        self._transient: dict[str, JSONValue] = {}
        self._transient_lock = threading.Lock()

        # Layer 2: 私有记忆（SQLite per-agent）
        private_db = self._base_dir / f"{agent_id}.db"
        self._private_pool = _ConnectionPool(str(private_db))
        with self._private_pool.get() as conn:
            _init_private_schema(conn)

        # Layer 3: 共享记忆（SQLite per-task）
        shared_db = self._base_dir / f"task_{task_id}.db"
        self._shared_pool = _ConnectionPool(str(shared_db))
        with self._shared_pool.get() as conn:
            _init_shared_schema(conn)

        # Layer 4: 共识记忆（文件存储，Alpha 简化实现）
        self._consensus_dir = self._base_dir / "consensus"
        self._consensus_dir.mkdir(parents=True, exist_ok=True)

    def _pre_write(self, value: JSONValue) -> JSONValue:
        if self._security is None:
            return value
        self._security.check_permission(self.agent_id, "memory", "write")
        return self._security.filter_sensitive_info(value)

    # ── Layer 0: 基因记忆（只读）────────────────────────────────

    def read_genetic(self, category: str, key: str | None = None) -> dict[str, object] | Any | None:
        """
        读取基因记忆（只读，来自 Z-Spore/archetypes/）。

        Args:
            category: 'agents' | 'tools' | 'laws' | 'skills'
            key: 可选，指定具体条目（按文件名 stem 或 id 查找）

        Returns:
            完整字典（key=None）或单个条目
        """
        loaders = {
            "agents": self._loader.get_agent_archetypes,
            "tools": self._loader.get_tool_archetypes,
            "laws": self._loader.get_law_archetypes,
            "skills": self._loader.get_skill_archetypes,
        }
        if category not in loaders:
            raise ValueError(f"未知基因记忆类别: {category!r}，可选: {list(loaders.keys())}")

        data = loaders[category]()
        return data.get(key) if key is not None else data

    # ── Layer 1: 临时记忆────────────────────────────────────────

    def write_transient(self, key: str, value: JSONValue) -> None:
        """写入临时记忆（线程安全，任务完成后需调用 clear_transient）"""
        value = self._pre_write(value)
        with self._transient_lock:
            self._transient[key] = value

    def read_transient(self, key: str, default: JSONValue | None = None) -> JSONValue | None:
        """读取临时记忆，未找到返回 default"""
        with self._transient_lock:
            return self._transient.get(key, default)

    def clear_transient(self) -> None:
        """清空所有临时记忆（任务完成时调用）"""
        with self._transient_lock:
            self._transient.clear()

    # ── Layer 2: 私有记忆────────────────────────────────────────

    def write_private(self, key: str, value: JSONValue) -> None:
        """写入私有记忆（SQLite per-agent，持久化）"""
        now = time.time()
        value = self._pre_write(value)
        serialized = json.dumps(value, ensure_ascii=False)
        with self._private_pool.get() as conn:
            conn.execute(
                """
                INSERT INTO private_memory (key, value, created_at, accessed_at, access_count)
                VALUES (?, ?, ?, ?, 0)
                ON CONFLICT(key) DO UPDATE SET
                    value       = excluded.value,
                    accessed_at = excluded.accessed_at
                """,
                (key, serialized, now, now),
            )

    def read_private(self, key: str, default: JSONValue | None = None) -> JSONValue | None:
        """读取私有记忆，同时更新访问时间和计数"""
        now = time.time()
        with self._private_pool.get() as conn:
            row = conn.execute("SELECT value FROM private_memory WHERE key = ?", (key,)).fetchone()
            if row is None:
                return default
            conn.execute(
                """
                UPDATE private_memory
                SET accessed_at  = ?,
                    access_count = access_count + 1
                WHERE key = ?
                """,
                (now, key),
            )
        return cast("JSONValue | None", json.loads(row["value"]))

    def delete_private(self, key: str) -> None:
        """删除私有记忆条目"""
        with self._private_pool.get() as conn:
            conn.execute("DELETE FROM private_memory WHERE key = ?", (key,))

    # ── Layer 3: 共享记忆────────────────────────────────────────

    def write_shared(self, key: str, value: JSONValue) -> None:
        """写入共享记忆（SQLite per-task，任务完成后清理）"""
        now = time.time()
        value = self._pre_write(value)
        serialized = json.dumps(value, ensure_ascii=False)
        with self._shared_pool.get() as conn:
            conn.execute(
                """
                INSERT INTO shared_memory (key, value, writer_agent, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value        = excluded.value,
                    writer_agent = excluded.writer_agent,
                    updated_at   = excluded.updated_at
                """,
                (key, serialized, self.agent_id, now, now),
            )

    def read_shared(self, key: str, default: JSONValue | None = None) -> JSONValue | None:
        """读取共享记忆"""
        with self._shared_pool.get() as conn:
            row = conn.execute("SELECT value FROM shared_memory WHERE key = ?", (key,)).fetchone()
            if row is None:
                return default
        return cast("JSONValue | None", json.loads(row["value"]))

    def clear_shared(self) -> None:
        """清空共享记忆（任务完成时调用）"""
        with self._shared_pool.get() as conn:
            conn.execute("DELETE FROM shared_memory")

    # ── Layer 4: 共识记忆（Alpha 简化实现）──────────────────────

    def write_consensus(self, key: str, value: JSONValue) -> None:
        """
        写入共识记忆（Alpha 阶段：JSON 文件存储）。
        Beta 阶段将集成知识图谱同步。
        """
        value = self._pre_write(value)
        file_path = self._consensus_dir / f"{key}.json"
        payload = {
            "key": key,
            "value": value,
            "writer_agent": self.agent_id,
            "task_id": self.task_id,
            "updated_at": time.time(),
        }
        atomic_write_json(file_path, payload)

    def read_consensus(self, key: str, default: JSONValue | None = None) -> JSONValue | None:
        """读取共识记忆"""
        file_path = self._consensus_dir / f"{key}.json"
        if not file_path.exists():
            return default
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
            return cast("JSONValue | None", payload.get("value", default))
        except (json.JSONDecodeError, OSError):
            return default

    # ── Layer 5: 集体记忆（只读，Alpha 预留接口）────────────────

    def read_collective(self, category: str = "laws") -> dict[str, object]:
        """
        读取集体记忆（只读）。
        Alpha 阶段：复用 ArchetypeLoader 的 law 读取能力。
        Beta 阶段将集成向量数据库语义检索。
        """
        return cast("dict[str, object]", self._loader.get_law_archetypes())

    # ── 统一读取接口（自动查找合适层级）────────────────────────

    def read_memory(self, key: str, default: JSONValue | None = None) -> tuple[JSONValue | None, int]:
        """
        统一读取接口，按优先级从低层到高层查找：
        L1(临时) → L2(私有) → L3(共享) → L4(共识)

        Returns:
            (value, layer_found)
            layer_found: 1-4 表示找到的层级，-1 表示未找到
        """
        # L1: 临时记忆（最高优先级）
        val = self.read_transient(key)
        if val is not None:
            return val, 1

        # L2: 私有记忆
        val = self.read_private(key)
        if val is not None:
            return val, 2

        # L3: 共享记忆
        val = self.read_shared(key)
        if val is not None:
            return val, 3

        # L4: 共识记忆
        val = self.read_consensus(key)
        if val is not None:
            return val, 4

        return default, -1

    # ── 生命周期管理────────────────────────────────────────────

    def cleanup_task(self) -> None:
        """任务完成时清理：清空临时记忆和共享记忆"""
        self.clear_transient()
        self.clear_shared()

    def validate_internal_state(self) -> None:
        """CoreService 协议：验证内部状态"""
        pass

    def describe(self) -> dict:
        """Return capability descriptor for this MemoryManager instance.

        Returns:
            dict with name, version, capabilities, agent_id, and bos_uri.
        """
        return {
            "name": "MemoryManager",
            "version": "1.0.0",
            "capabilities": [
                "memory.read_genetic",
                "memory.read_transient",
                "memory.write_transient",
                "memory.read_private",
                "memory.write_private",
                "memory.read_shared",
                "memory.write_shared",
                "memory.read_consensus",
                "memory.write_consensus",
                "memory.read_collective",
                "memory.read_unified",
                "memory.describe_sovereign_views",
                "memory.build_sovereignty_context",
            ],
            "agent_id": self.agent_id,
            "bos_uri": f"bos://d-memory/manager/{self.agent_id}",
            "mount_summary": self.summarize_mounts(),
        }

    def describe_mounts(
        self,
        domain_id: str = "",
        include_root: bool = False,
        include_federated: bool = False,
    ) -> list[MemoryMount]:
        """Describe the active memory views exposed by this manager.

        The contract models mounted views, not raw full-copy inheritance.
        """
        mounts = [
            MemoryMount(
                mount_type="runtime",
                mount_id=f"runtime:{self.agent_id}:{self.task_id}",
                source=f"transient://{self.agent_id}/{self.task_id}",
                writable=True,
                scope=self.task_id,
                owner_id=self.agent_id,
                governance_scope=self.task_id,
            ),
            MemoryMount(
                mount_type="shared",
                mount_id=f"shared:{self.task_id}",
                source=f"sqlite://task/{self.task_id}",
                writable=True,
                scope=self.task_id,
                owner_id=self.agent_id,
                governance_scope=self.task_id,
            ),
        ]

        if domain_id:
            mounts.append(
                MemoryMount(
                    mount_type="domain",
                    mount_id=f"domain:{domain_id}",
                    source=f"bos://D-Memory/domain/{domain_id}",
                    scope=domain_id,
                    owner_id=self.agent_id,
                    governance_scope=domain_id,
                )
            )

        if include_root:
            mounts.append(
                MemoryMount(
                    mount_type="root",
                    mount_id="root:sovereign",
                    source="bos://D-Memory/root/sovereign",
                    scope="root",
                    owner_id=self.agent_id,
                    governance_scope="root",
                )
            )

        if include_federated:
            mounts.append(
                MemoryMount(
                    mount_type="federated",
                    mount_id=f"federated:{domain_id or self.agent_id}",
                    source=f"bos://D-Memory/federated/{domain_id or self.agent_id}",
                    scope=domain_id or self.agent_id,
                    owner_id=self.agent_id,
                    governance_scope=domain_id or self.agent_id,
                )
            )

        return mounts

    def summarize_mounts(
        self,
        domain_id: str = "",
        include_root: bool = False,
        include_federated: bool = False,
    ) -> dict[str, object]:
        """Return a sovereign view summary for the currently exposed mounts."""
        mounts = self.describe_mounts(
            domain_id=domain_id,
            include_root=include_root,
            include_federated=include_federated,
        )
        return {
            "owner_id": self.agent_id,
            "primary_scope": self.task_id,
            "mount_types": sorted({mount.mount_type for mount in mounts}),
            "governance_scopes": sorted({mount.governance_scope for mount in mounts if mount.governance_scope}),
            "writable_mount_ids": [mount.mount_id for mount in mounts if mount.writable],
        }

    def describe_sovereign_views(
        self,
        domain_id: str = "",
        include_root: bool = False,
        include_federated: bool = False,
    ) -> dict[str, object]:
        """Return the node's sovereign memory views as grouped mount projections."""
        mounts = self.describe_mounts(
            domain_id=domain_id,
            include_root=include_root,
            include_federated=include_federated,
        )

        grouped = {
            "runtime": [mount.to_dict() for mount in mounts if mount.mount_type == "runtime"],
            "shared": [mount.to_dict() for mount in mounts if mount.mount_type == "shared"],
            "inherited": [mount.to_dict() for mount in mounts if mount.mount_type in {"domain", "root"}],
            "federated": [mount.to_dict() for mount in mounts if mount.mount_type == "federated"],
        }
        return {
            "owner_id": self.agent_id,
            "primary_scope": self.task_id,
            "views": grouped,
            "mount_summary": self.summarize_mounts(
                domain_id=domain_id,
                include_root=include_root,
                include_federated=include_federated,
            ),
        }

    def build_sovereignty_context(
        self,
        domain_id: str = "",
        *,
        role_id: str = "",
        task_id: str = "",
        include_root: bool = False,
        include_federated: bool = False,
    ) -> MemorySovereigntyContext:
        """Construct the request-scoped sovereignty context for memory consumers."""
        mount_summary = self.summarize_mounts(
            domain_id=domain_id,
            include_root=include_root,
            include_federated=include_federated,
        )
        sovereignty_level = (
            "root" if include_root else "federated" if include_federated else "domain" if domain_id else "task"
        )
        return MemorySovereigntyContext(
            owner_id=self.agent_id,
            primary_scope=domain_id or task_id or self.task_id,
            role_id=role_id,
            task_id=task_id or self.task_id,
            mount_summary=mount_summary,
            sovereignty_level=sovereignty_level,
        )

    def read_unified(
        self,
        key: str,
        default: JSONValue | None = None,
        context: MemorySovereigntyContext | None = None,
    ) -> tuple[JSONValue | None, int]:
        """Compatibility alias for the unified read contract."""
        # The lower-layer memory store already enforces the canonical layer order.
        # The sovereignty context is used by service-facing read models.
        _ = context
        return self.read_memory(key, default)

    def heartbeat(self) -> dict:
        """Return liveness status for this MemoryManager instance.

        Returns:
            dict with status, ts, agent_id, task_id, and transient_key_count.
        """
        with self._transient_lock:
            transient_count = len(self._transient)
        return {
            "status": "alive",
            "ts": time.time(),
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "transient_key_count": transient_count,
        }

    def health_check(self) -> dict:
        """Return detailed health metrics for this MemoryManager.

        Probes all active memory layers and reports their availability.

        Returns:
            dict with status, version, layers, and component health details.
        """
        with self._transient_lock:
            transient_count = len(self._transient)

        private_ok = True
        shared_ok = True
        try:
            with self._private_pool.get() as conn:
                conn.execute("SELECT 1 FROM private_memory LIMIT 1")
        except SQLiteError:
            private_ok = False

        try:
            with self._shared_pool.get() as conn:
                conn.execute("SELECT 1 FROM shared_memory LIMIT 1")
        except SQLiteError:
            shared_ok = False

        all_ok = private_ok and shared_ok
        return {
            "status": "healthy" if all_ok else "degraded",
            "version": "1.0.0",
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "layers": {
                "L1_transient": {"available": True, "key_count": transient_count},
                "L2_private": {"available": private_ok},
                "L3_shared": {"available": shared_ok},
                "L4_consensus": {"available": self._consensus_dir.exists()},
            },
        }

    def close(self) -> None:
        """关闭所有连接池，释放资源"""
        self._private_pool.close_all()
        self._shared_pool.close_all()

    def __enter__(self) -> MemoryManager:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def __del__(self) -> None:
        """析构函数确保资源释放"""
        self.close()
