from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# Federated Memory ≡ Module
# 内涵 ≝ {Federated, Memory}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, FederatedMemory)}
# 功能 ⊢ {Federated_Memory, Init_Federated, Validate_Memory}
# =============================================================================

"""
---
Type: FederatedMemory
Layer: L2
Domain: D-Memory
Status: ACTIVE
Updated: "2026-04-02"
Authority: 2
Compiled-From: []
Keywords: [federated, memory, sync, crdt, distributed]
---

联邦记忆 - 跨节点记忆同步

实现基于CRDT的无冲突复制，支持：
- 向量时钟版本控制
- 选择性同步（按信任级别）
- 自动冲突解决
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class VectorClock:
    """向量时钟

    用于分布式系统中的事件排序和冲突检测
    """

    clocks: dict[str, int] = field(default_factory=dict)

    def increment(self, node_id: str) -> None:
        """递增本节点的时钟"""
        self.clocks[node_id] = self.clocks.get(node_id, 0) + 1

    def merge(self, other: VectorClock) -> VectorClock:
        """合并两个向量时钟"""
        merged = {}
        all_nodes = set(self.clocks.keys()) | set(other.clocks.keys())
        for node in all_nodes:
            merged[node] = max(self.clocks.get(node, 0), other.clocks.get(node, 0))
        return VectorClock(merged)

    def compare(self, other: VectorClock) -> str | None:
        """比较两个向量时钟

        Returns:
            "before": self发生在other之前
            "after": self发生在other之后
            "concurrent": 并发（冲突）
            "equal": 相同
        """
        dominates = False
        dominated = False

        all_nodes = set(self.clocks.keys()) | set(other.clocks.keys())

        for node in all_nodes:
            self_val = self.clocks.get(node, 0)
            other_val = other.clocks.get(node, 0)

            if self_val > other_val:
                dominates = True
            elif other_val > self_val:
                dominated = True

        if dominates and not dominated:
            return "after"
        elif dominated and not dominates:
            return "before"
        elif not dominates and not dominated:
            return "equal"
        else:
            return "concurrent"

    def to_dict(self) -> dict[str, int]:
        return self.clocks.copy()

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> VectorClock:
        return cls(data)


@dataclass
class FederatedMemoryEntry:
    """联邦记忆条目

    包含CRDT元数据的记忆单元
    """

    key: str
    value: Any

    # CRDT元数据
    version: VectorClock
    timestamp: datetime
    node_id: str

    # 同步元数据
    trust_level: float = 0.5  # 0-1
    sync_priority: int = 1  # 同步优先级
    deleted: bool = False  # 软删除标记

    # 内容哈希（用于完整性验证）
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.content_hash:
            self.content_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """计算内容哈希"""
        content = json.dumps({"key": self.key, "value": self.value}, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def verify_integrity(self) -> bool:
        """验证内容完整性"""
        return self.content_hash == self._compute_hash()


class CRDTSet:
    """CRDT集合实现

    基于OR-Set (Observed-Removed Set)的无冲突集合
    """

    def __init__(self) -> None:
        self._additions: dict[str, FederatedMemoryEntry] = {}
        self._removals: set[str] = set()  # 已删除的key

    def add(self, entry: FederatedMemoryEntry) -> None:
        """添加条目"""
        if entry.key in self._additions:
            # 合并版本
            existing = self._additions[entry.key]
            entry.version = existing.version.merge(entry.version)

            # 如果新值的时间戳更新，则更新值
            if entry.timestamp > existing.timestamp:
                self._additions[entry.key] = entry
        else:
            self._additions[entry.key] = entry

        # 从删除集合中移除
        self._removals.discard(entry.key)

    def remove(self, key: str, node_id: str) -> None:
        """软删除条目"""
        if key in self._additions:
            entry = self._additions[key]
            entry.deleted = True
            entry.version.increment(node_id)
            self._removals.add(key)

    def get(self, key: str) -> FederatedMemoryEntry | None:
        """获取条目"""
        if key in self._removals:
            return None
        return self._additions.get(key)

    def merge(self, other: CRDTSet) -> CRDTSet:
        """合并两个CRDT集合"""
        merged = CRDTSet()

        # 合并所有添加
        all_keys = set(self._additions.keys()) | set(other._additions.keys())
        for key in all_keys:
            entry1 = self._additions.get(key)
            entry2 = other._additions.get(key)

            if entry1 and entry2:
                # 冲突解决：选择时间戳更新的
                if entry1.timestamp > entry2.timestamp:
                    merged.add(entry1)
                else:
                    merged.add(entry2)
            elif entry1:
                merged.add(entry1)
            else:
                if entry2 is not None:
                    merged.add(entry2)

        # 合并删除标记
        merged._removals = self._removals | other._removals

        return merged

    def values(self) -> list[FederatedMemoryEntry]:
        """获取所有有效条目"""
        return [entry for key, entry in self._additions.items() if key not in self._removals and not entry.deleted]


class FederatedMemory:
    """联邦记忆管理器

    跨节点的记忆同步与合并
    """

    TRUST_THRESHOLD = 0.3  # 最低信任级别才同步

    def __init__(self, node_id: str) -> None:
        """初始化联邦记忆

        Args:
            node_id: 本节点ID
        """
        self.node_id = node_id
        self._local_memory = CRDTSet()
        self._sync_peers: dict[str, float] = {}  # node_id -> trust_level
        self._sync_history: list[dict] = []

    # ==================== 本地操作 ====================

    def put(self, key: str, value: Any, trust_level: float = 1.0) -> FederatedMemoryEntry:
        """存储记忆

        Args:
            key: 记忆键
            value: 记忆值
            trust_level: 信任级别（影响同步优先级）

        Returns:
            创建的条目
        """
        entry = FederatedMemoryEntry(
            key=key,
            value=value,
            version=VectorClock({self.node_id: 1}),
            timestamp=datetime.now(UTC),
            node_id=self.node_id,
            trust_level=trust_level,
        )

        self._local_memory.add(entry)
        return entry

    def get(self, key: str) -> Any | None:
        """获取记忆值"""
        entry = self._local_memory.get(key)
        return entry.value if entry else None

    def delete(self, key: str) -> bool:
        """删除记忆"""
        if key in self._local_memory._additions:
            self._local_memory.remove(key, self.node_id)
            return True
        return False

    def query(self, min_trust: float = 0.0, since: datetime | None = None) -> list[FederatedMemoryEntry]:
        """查询记忆

        Args:
            min_trust: 最低信任级别
            since: 起始时间

        Returns:
            匹配的条目列表
        """
        entries = self._local_memory.values()

        if min_trust > 0:
            entries = [e for e in entries if e.trust_level >= min_trust]

        if since:
            entries = [e for e in entries if e.timestamp >= since]

        return sorted(entries, key=lambda e: e.timestamp, reverse=True)

    # ==================== 联邦同步 ====================

    def add_sync_peer(self, node_id: str, trust_level: float) -> None:
        """添加同步对等节点

        Args:
            node_id: 节点ID
            trust_level: 信任级别（0-1）
        """
        if trust_level >= self.TRUST_THRESHOLD:
            self._sync_peers[node_id] = trust_level
            print(f"[FederatedMemory] Added sync peer {node_id} (trust: {trust_level})")

    def remove_sync_peer(self, node_id: str) -> None:
        """移除同步对等节点"""
        self._sync_peers.pop(node_id, None)

    def prepare_sync_data(self, target_node: str) -> dict[str, Any] | None:
        """准备同步数据

        Args:
            target_node: 目标节点ID

        Returns:
            同步数据包，如果不应同步则返回None
        """
        trust = self._sync_peers.get(target_node, 0)
        if trust < self.TRUST_THRESHOLD:
            return None

        # 只同步信任级别足够的条目
        entries = [
            {
                "key": e.key,
                "value": e.value,
                "version": e.version.to_dict(),
                "timestamp": e.timestamp.isoformat(),
                "node_id": e.node_id,
                "trust_level": e.trust_level,
                "deleted": e.deleted,
                "content_hash": e.content_hash,
            }
            for e in self._local_memory.values()
            if e.trust_level >= trust
        ]

        return {
            "source": self.node_id,
            "target": target_node,
            "entries": entries,
            "sync_timestamp": datetime.now(UTC).isoformat(),
        }

    def apply_sync_data(self, sync_data: dict[str, Any]) -> dict[str, Any]:
        """应用同步数据

        Args:
            sync_data: 从其他节点接收的同步数据

        Returns:
            同步结果统计
        """
        source = sync_data.get("source")
        entries = sync_data.get("entries", [])

        if source not in self._sync_peers:
            return {"error": "Untrusted source", "added": 0, "updated": 0, "conflicts": 0}

        added = 0
        updated = 0
        conflicts = 0

        for entry_data in entries:
            entry = FederatedMemoryEntry(
                key=entry_data["key"],
                value=entry_data["value"],
                version=VectorClock.from_dict(entry_data["version"]),
                timestamp=datetime.fromisoformat(entry_data["timestamp"]),
                node_id=entry_data["node_id"],
                trust_level=entry_data["trust_level"],
                deleted=entry_data["deleted"],
                content_hash=entry_data["content_hash"],
            )

            # 检查冲突
            existing = self._local_memory.get(entry.key)
            if existing:
                relation = existing.version.compare(entry.version)
                if relation == "concurrent":
                    conflicts += 1
                    # 冲突解决：时间戳优先
                    if entry.timestamp > existing.timestamp:
                        self._local_memory.add(entry)
                        updated += 1
                elif relation == "before":
                    self._local_memory.add(entry)
                    updated += 1
            else:
                self._local_memory.add(entry)
                added += 1

        # 记录同步历史
        self._sync_history.append(
            {
                "source": source,
                "timestamp": datetime.now(UTC),
                "added": added,
                "updated": updated,
                "conflicts": conflicts,
            }
        )

        return {
            "added": added,
            "updated": updated,
            "conflicts": conflicts,
            "total_entries": len(self._local_memory.values()),
        }

    def merge_with(self, other: FederatedMemory) -> FederatedMemory:
        """与另一个联邦记忆合并"""
        merged = FederatedMemory(f"{self.node_id}+{other.node_id}")
        merged._local_memory = self._local_memory.merge(other._local_memory)
        merged._sync_peers = {**self._sync_peers, **other._sync_peers}
        return merged

    # ==================== 统计接口 ====================

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        entries = self._local_memory.values()
        return {
            "total_entries": len(entries),
            "sync_peers": len(self._sync_peers),
            "avg_trust": sum(e.trust_level for e in entries) / len(entries) if entries else 0,
            "sync_history_count": len(self._sync_history),
            "recent_syncs": self._sync_history[-5:],
        }


# ==================== 使用示例 ====================

"""
# FamilyHiveNetwork + FederatedMemory 集成

import importlib

family_hive_module = importlib.import_module("organs.D_Gateway.organs.family_hive")
FamilyHiveNetwork = family_hive_module.FamilyHiveNetwork
from eidos.organs.federated_memory import FederatedMemory

# 创建节点
node_a = FamilyHiveNetwork(node_id="node-a", role=NodeRole.PRIMARY)
memory_a = FederatedMemory("node-a")

node_b = FamilyHiveNetwork(node_id="node-b", role=NodeRole.SECONDARY)
memory_b = FederatedMemory("node-b")

# 配置同步
memory_a.add_sync_peer("node-b", trust_level=0.8)
memory_b.add_sync_peer("node-a", trust_level=0.8)

# 存储记忆
memory_a.put("shared_knowledge", {"key": "value"}, trust_level=0.9)

# 网络同步
sync_data = memory_a.prepare_sync_data("node-b")
result = memory_b.apply_sync_data(sync_data)

print(f"Synced: {result['added']} added, {result['updated']} updated")
assert memory_b.get("shared_knowledge") == {"key": "value"}
"""
