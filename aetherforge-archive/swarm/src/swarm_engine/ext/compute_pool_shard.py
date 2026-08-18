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
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Compute Pool Shard ≡ Module
# 内涵 ≝ {Compute, Pool, Shard}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, ComputePoolShard)}
# 功能 ⊢ {Compute_Pool, Pool_Shard, Shard_Init}
# =============================================================================

# ---
# domain: D-Execution
# layer: organ
# status: active
# description: Compute pool sharding for distributed worker assignment
# ---

import enum
import threading
from dataclasses import dataclass, field


class ShardStrategy(enum.Enum):
    """Strategy for assigning workers to shards."""

    HASH = "hash"
    RANGE = "range"
    ROUND_ROBIN = "round_robin"
    LOCALITY = "locality"


@dataclass
class ComputeShard:
    """A single compute shard within a pool."""

    shard_id: str
    capacity: int
    used: int = 0
    workers: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


class ComputePoolSharding:
    """Manages sharding of compute resources across a pool.

    Thread-safe implementation for distributing workers across shards
    using configurable strategies.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._shards: dict[str, ComputeShard] = {}
        self._quotas: dict[str, int] = {}
        self._round_robin_index: int = 0
        self._worker_shard_map: dict[str, str] = {}

    def create_shard(self, shard_id: str, capacity: int) -> ComputeShard:
        """Create a new shard with the given capacity."""
        if capacity <= 0:
            raise ValueError(f"Capacity must be positive, got {capacity}")
        with self._lock:
            if shard_id in self._shards:
                raise ValueError(f"Shard {shard_id!r} already exists")
            shard = ComputeShard(shard_id=shard_id, capacity=capacity)
            self._shards[shard_id] = shard
            return shard

    def remove_shard(self, shard_id: str) -> None:
        """Remove a shard by id."""
        with self._lock:
            if shard_id not in self._shards:
                raise KeyError(f"Shard {shard_id!r} not found")
            shard = self._shards.pop(shard_id)
            for w in shard.workers:
                self._worker_shard_map.pop(w, None)
            self._quotas.pop(shard_id, None)

    def assign_worker(self, worker_id: str, shard_strategy: ShardStrategy) -> str:
        """Assign a worker to a shard using the given strategy. Returns shard_id."""
        with self._lock:
            if not self._shards:
                raise RuntimeError("No shards available")
            if worker_id in self._worker_shard_map:
                raise ValueError(f"Worker {worker_id!r} already assigned")
            shard = self._pick_shard(worker_id, shard_strategy)
            effective_cap = self._quotas.get(shard.shard_id, shard.capacity)
            if shard.used >= effective_cap:
                raise RuntimeError(f"Shard {shard.shard_id!r} at capacity ({shard.used}/{effective_cap})")
            shard.workers.append(worker_id)
            shard.used += 1
            self._worker_shard_map[worker_id] = shard.shard_id
            return shard.shard_id

    def rebalance(self) -> dict[str, str]:
        """Rebalance workers across shards. Returns {worker_id: new_shard_id} for migrations."""
        with self._lock:
            if not self._shards:
                return {}
            total_workers = sum(s.used for s in self._shards.values())
            target = total_workers // len(self._shards)
            remainder = total_workers % len(self._shards)

            shard_list = sorted(self._shards.keys())
            targets: dict[str, int] = {}
            for i, sid in enumerate(shard_list):
                targets[sid] = target + (1 if i < remainder else 0)

            surplus_workers: list[str] = []
            for sid in shard_list:
                shard = self._shards[sid]
                while shard.used > targets[sid] and shard.workers:
                    w = shard.workers.pop()
                    shard.used -= 1
                    surplus_workers.append(w)

            migrations: dict[str, str] = {}
            for sid in shard_list:
                shard = self._shards[sid]
                while shard.used < targets[sid] and surplus_workers:
                    w = surplus_workers.pop()
                    shard.workers.append(w)
                    shard.used += 1
                    self._worker_shard_map[w] = sid
                    migrations[w] = sid

            return migrations

    def get_shard_load(self) -> dict[str, float]:
        """Return load fraction for each shard (used / capacity)."""
        with self._lock:
            result: dict[str, float] = {}
            for sid, shard in self._shards.items():
                cap = self._quotas.get(sid, shard.capacity)
                result[sid] = shard.used / cap if cap > 0 else 0.0
            return result

    def cross_pool_balance(self, other_pool: ComputePoolSharding) -> list[dict[str, str]]:
        """Balance workers between this pool and another. Returns list of transfer dicts."""
        with self._lock, other_pool._lock:
            my_total = sum(s.used for s in self._shards.values())
            other_total = sum(s.used for s in other_pool._shards.values())
            my_cap = sum(self._quotas.get(s, sh.capacity) for s, sh in self._shards.items())
            other_cap = sum(other_pool._quotas.get(s, sh.capacity) for s, sh in other_pool._shards.items())
            if my_cap == 0 or other_cap == 0:
                return []

            my_load = my_total / my_cap
            other_load = other_total / other_cap
            transfers: list[dict[str, str]] = []

            if my_load > other_load + 0.1:
                source_pool, dest_pool = self, other_pool
                direction = "self_to_other"
            elif other_load > my_load + 0.1:
                source_pool, dest_pool = other_pool, self
                direction = "other_to_self"
            else:
                return []

            for sid, shard in list(source_pool._shards.items()):
                if shard.workers:
                    w = shard.workers[-1]
                    dest_shard = max(
                        dest_pool._shards.values(),
                        key=lambda s: dest_pool._quotas.get(s.shard_id, s.capacity) - s.used,
                    )
                    dest_cap = dest_pool._quotas.get(dest_shard.shard_id, dest_shard.capacity)
                    if dest_shard.used < dest_cap:
                        shard.workers.pop()
                        shard.used -= 1
                        source_pool._worker_shard_map.pop(w, None)
                        dest_shard.workers.append(w)
                        dest_shard.used += 1
                        dest_pool._worker_shard_map[w] = dest_shard.shard_id
                        transfers.append(
                            {
                                "worker": w,
                                "from_shard": sid,
                                "to_shard": dest_shard.shard_id,
                                "direction": direction,
                            }
                        )
                        break
            return transfers

    def set_quota(self, shard_id: str, max_capacity: int) -> None:
        """Set a quota (effective max capacity) for a shard."""
        with self._lock:
            if shard_id not in self._shards:
                raise KeyError(f"Shard {shard_id!r} not found")
            if max_capacity <= 0:
                raise ValueError("Quota must be positive")
            self._quotas[shard_id] = max_capacity

    def priority_preempt(self, high_priority_worker: str, shard_id: str) -> str | None:
        """Preempt lowest-priority worker for a high-priority one. Returns evicted worker or None."""
        with self._lock:
            if shard_id not in self._shards:
                raise KeyError(f"Shard {shard_id!r} not found")
            shard = self._shards[shard_id]
            cap = self._quotas.get(shard_id, shard.capacity)
            if shard.used < cap:
                shard.workers.append(high_priority_worker)
                shard.used += 1
                self._worker_shard_map[high_priority_worker] = shard_id
                return None
            if not shard.workers:
                raise RuntimeError(f"Shard {shard_id!r} full but has no workers to evict")
            evicted = shard.workers.pop(0)
            self._worker_shard_map.pop(evicted, None)
            shard.workers.append(high_priority_worker)
            self._worker_shard_map[high_priority_worker] = shard_id
            return evicted

    # ---- internal helpers ----

    def _pick_shard(self, worker_id: str, strategy: ShardStrategy) -> ComputeShard:
        """Pick a shard for a worker using the given strategy (must hold lock)."""
        available = [s for s in self._shards.values() if s.used < self._quotas.get(s.shard_id, s.capacity)]
        if not available:
            raise RuntimeError("All shards at capacity")

        if strategy == ShardStrategy.HASH:
            idx = hash(worker_id) % len(available)
            return available[idx]

        if strategy == ShardStrategy.RANGE:
            return min(available, key=lambda s: s.used)

        if strategy == ShardStrategy.ROUND_ROBIN:
            idx = self._round_robin_index % len(available)
            self._round_robin_index += 1
            return available[idx]

        if strategy == ShardStrategy.LOCALITY:
            return min(available, key=lambda s: s.used)

        raise ValueError(f"Unknown strategy: {strategy}")
