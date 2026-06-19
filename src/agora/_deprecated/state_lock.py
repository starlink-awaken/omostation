from __future__ import annotations

"""
---
Type: Component
Status: ACTIVE
Version: 1.0.0
Owner: '@Prime'
Layer: L3
Summary: 'DHTStateLock: Distributed locking mechanism utilizing the Kademlia DHT.'
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# State Lock ≡ Module
# 内涵 ≝ {State, Lock}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, StateLock)}
# 功能 ⊢ {State_Lock, Init_State, Validate_Lock}
# =============================================================================

import asyncio  # noqa: E402
import logging  # noqa: E402
import time  # noqa: E402
from typing import Any  # noqa: E402

_log = logging.getLogger(__name__)


class DHTStateLock:
    """
    [TRK-038] 分布式状态锁 (DHTStateLock)
    利用 DHT 实现跨节点的互斥访问，保证交易安全。
    """

    def __init__(self, dht: Any | None = None) -> None:
        if dht is None:
            from agora.p2p_discovery import get_p2p  # type: ignore[import-not-found]

            self._dht = get_p2p().dht
        else:
            self._dht = dht

        # 使用实例锁或确保类锁在循环内初始化
        if not hasattr(self.__class__, "_local_lock"):
            self.__class__._local_lock = asyncio.Lock()

    async def acquire(self, lock_id: str, owner: str, ttl: float = 10.0) -> bool:
        """
        尝试获取分布式锁。
        """
        async with self._local_lock:
            key = f"lock:{lock_id}"
            current_lock = await self._dht.get(key)

            now = time.time()

            if current_lock:
                expires_at = current_lock.get("expires_at", 0.0)
                if now < expires_at:
                    # 锁已被占用且未过期
                    _log.debug(
                        "🔒 [StateLock] Lock %s already held by %s",
                        lock_id,
                        current_lock.get("owner"),
                    )
                    return False

            # 写入新锁
            lock_data = {"owner": owner, "expires_at": now + ttl, "created_at": now}

            await self._dht.set(key, lock_data)
            _log.info(
                "🔓 [StateLock] Lock %s acquired by %s (TTL: %.1fs)",
                lock_id,
                owner,
                ttl,
            )
            return True

    async def release(self, lock_id: str, owner: str) -> None:
        """
        释放持有的分布式锁。
        """
        key = f"lock:{lock_id}"
        current_lock = await self._dht.get(key)

        if current_lock and current_lock.get("owner") == owner:
            # 在原型中，我们通过写入一个已过期的值来模拟释放
            # 实际应从 DHT 中删除该 Key
            expired_data = current_lock.copy()
            expired_data["expires_at"] = 0.0
            await self._dht.set(key, expired_data)
            _log.info("🔓 [StateLock] Lock %s released by %s", lock_id, owner)

    async def is_locked(self, lock_id: str) -> bool:
        """
        检查锁是否被占用且有效。
        """
        key = f"lock:{lock_id}"
        current_lock = await self._dht.get(key)
        if not current_lock:
            return False

        return time.time() < current_lock.get("expires_at", 0.0)
