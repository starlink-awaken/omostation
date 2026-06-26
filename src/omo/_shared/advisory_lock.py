"""跨 session agent 协调锁 (TASK-94BB9C70 治本, memory concurrent-agent-contention).

与 fcntl_lock 互补, 各管一层, 别搞混:

  fcntl_lock (进程级 runtime 保护, append_only_log.py):
    - omo CLI/worker 调用时持有, 进程退出/崩溃 fd close 自动释放
    - 保护 AppendOnlyLog + omo_ingress 写操作 (task_lifecycle 16 + registry_writes 9 + ...)
    - 局限: 进程级, 无法跨 session 持有 (agent A 的锁对 agent B 不可见)

  AdvisoryLock (session 级 agent 协调):  ← 本模块
    - agent 编辑共享文件前 acquire, 编辑完 release (声明式长事务)
    - 锁状态持久化到 lockfile (holder/ttl), 跨 session 可见
    - ttl 防死锁 (agent 崩溃没 release, ttl 过期可被抢占)
    - fcntl_lock 保护 acquire/release 那一刻的原子性 (防并发写 lockfile 竞争)

病根 (老王踩过, memory concurrent-agent-contention):
  并发 governance agent (别的会话) 同改 omo_ingress, 老王 Edit/sed 被回滚或吸收.
  fcntl_lock 只在 omo CLI 调用时持有, agent 直接编辑源码完全绕过锁 — 憨批设计缺口.

解法:
  agent 改共享文件前: acquire_lock(resource, holder=session_id)
    → status=ok 才编辑, status=locked 则等 or 换文件
  编辑完: release_lock(resource, holder=session_id)
  崩溃没 release: ttl 过期后别的 agent 可抢占 (不死锁)

设计原则:
  - KISS: 声明式 lockfile (JSON metadata), 不绑进程, 跨 session 可见
  - 容错: ttl 防死锁, 过期锁可抢占; release 验证 holder 防误释放他人锁
  - 可重入: 同 holder 再 acquire 刷新 ttl (不报错, 支持嵌套编辑)
  - 原子: fcntl.flock(LOCK_EX) 序列化 acquire/release, 防并发竞争 lockfile
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from .append_only_log import fcntl_lock


def _utc_now() -> float:
    """单调时钟 (秒). 用 time.time 跨进程可比 (epoch 秒)."""
    return time.time()


class AdvisoryLock:
    """跨 session agent 协调锁 (声明式 lockfile + ttl 防死锁).

    用法:
        lock = AdvisoryLock(Path("/path/to/state/locks"))
        r = lock.acquire("projects/omo/src/omo/omo_ingress.py", holder="session-A")
        if r["status"] == "ok":
            try:
                ...  # agent 编辑文件 (Edit/sed/omo CLI)
            finally:
                lock.release("projects/omo/src/omo/omo_ingress.py", holder="session-A")
        else:
            # status=locked, 别的 agent 在改, 等 or 换文件
            ...

    语义:
        - acquire: fcntl.flock 序列化 → 原子 check+write lockfile
        - 持有: lockfile 存在即"被锁" (无进程绑定, 跨 session 可见)
        - release: 验证 holder 后删 lockfile (防误释放他人锁)
        - ttl: 过期锁可被抢占 (防 agent 崩溃死锁)
        - 可重入: 同 holder 再 acquire 刷新 ttl, 返回 reentrant=True

    文件布局 (lock_dir 下):
        <resource>.lock   — 锁状态 metadata (JSON, 可删)
        .<resource>.lock.guard — fcntl.flock 用的永久 sidecar (不删, 只做内核锁)
    """

    DEFAULT_TTL = 300  # 5 min, 防 agent 崩溃死锁; 长事务可调大

    def __init__(self, lock_dir: Path) -> None:
        self.lock_dir = Path(lock_dir)
        self.lock_dir.mkdir(parents=True, exist_ok=True)

    def _safe_name(self, resource: str) -> str:
        """resource (文件路径/逻辑名) → 安全 lockfile 名 (去路径分隔符)."""
        return resource.replace("/", "_").replace("\\", "_").replace(":", "_")

    def _meta_file(self, resource: str) -> Path:
        return self.lock_dir / f"{self._safe_name(resource)}.lock"

    def _guard_file(self, resource: str) -> Path:
        """fcntl.flock sidecar. 和 meta 分开: meta 可删, guard 永久 (防 flock 语义坑)."""
        return self.lock_dir / f".{self._safe_name(resource)}.lock.guard"

    def acquire(
        self, resource: str, holder: str, ttl: int = DEFAULT_TTL
    ) -> dict[str, Any]:
        """获取锁. 返回 status=ok (acquired/reentrant) 或 status=locked (被他人持有).

        Args:
            resource: 被锁资源 (文件路径或逻辑名, 如 "omo_ingress.py").
            holder: 持有者标识 (session_id / agent_id, 跨 session 唯一).
            ttl: 锁有效期 (秒). 过期后可被抢占. 默认 300s.

        Returns:
            {"status": "ok", "acquired": True, ...}  — 新获取
            {"status": "ok", "reentrant": True, ...}  — 同 holder 再获取 (刷新 ttl)
            {"status": "locked", "holder": ..., "age": ...}  — 被他人持有, 拒绝
        """
        meta_file = self._meta_file(resource)
        guard = self._guard_file(resource)
        with fcntl_lock(guard):  # 内核级序列化, 防并发 acquire 竞争
            existing = self._read_meta(meta_file)
            now = _utc_now()

            if existing is not None:
                expired = now - existing["acquired_at"] > existing["ttl"]
                if expired:
                    existing = None  # 过期, 落到下面新获取 (抢占)
                elif existing["holder"] == holder:
                    # 可重入: 同 holder 刷新 ttl (支持嵌套编辑, 不累计计数 — KISS)
                    meta = {**existing, "acquired_at": now, "ttl": ttl}
                    self._write_meta(meta_file, meta)
                    return {
                        "status": "ok",
                        "reentrant": True,
                        "resource": resource,
                        "holder": holder,
                    }
                else:
                    return {
                        "status": "locked",
                        "resource": resource,
                        "holder": existing["holder"],
                        "acquired_at": existing["acquired_at"],
                        "age": int(now - existing["acquired_at"]),
                        "ttl": existing["ttl"],
                    }

            # 新获取 (或抢占过期锁)
            meta = {
                "holder": holder,
                "acquired_at": now,
                "ttl": ttl,
                "resource": resource,
            }
            self._write_meta(meta_file, meta)
            return {
                "status": "ok",
                "acquired": True,
                "resource": resource,
                "holder": holder,
                "ttl": ttl,
            }

    def release(self, resource: str, holder: str) -> dict[str, Any]:
        """释放锁. 验证 holder (防误释放他人锁).

        Returns:
            {"status": "ok", "released": True}  — 释放成功
            {"status": "not_locked"}  — 本就没锁
            {"status": "forbidden", "holder": ...}  — holder 不匹配, 拒绝释放
        """
        meta_file = self._meta_file(resource)
        guard = self._guard_file(resource)
        with fcntl_lock(guard):
            existing = self._read_meta(meta_file)
            if existing is None:
                return {"status": "not_locked", "resource": resource}
            if existing["holder"] != holder:
                return {
                    "status": "forbidden",
                    "resource": resource,
                    "holder": existing["holder"],
                }
            meta_file.unlink(missing_ok=True)
            return {"status": "ok", "released": True, "resource": resource}

    def check(self, resource: str) -> dict[str, Any]:
        """查询锁状态 (不获取). 供 agent 编辑前 peek.

        Returns:
            {"status": "free"}  — 无人持有
            {"status": "locked", ...}  — 有效持有
            {"status": "stale", ...}  — 已过期但 lockfile 还在 (可抢占)
        """
        meta_file = self._meta_file(resource)
        existing = self._read_meta(meta_file)
        if existing is None:
            return {"status": "free", "resource": resource}
        now = _utc_now()
        expired = now - existing["acquired_at"] > existing["ttl"]
        if expired:
            return {
                "status": "stale",
                **existing,
                "age": int(now - existing["acquired_at"]),
            }
        return {
            "status": "locked",
            **existing,
            "age": int(now - existing["acquired_at"]),
        }

    def list_locks(self) -> list[dict[str, Any]]:
        """列出所有 lockfile (含过期, 供审计/dashboard)."""
        result: list[dict[str, Any]] = []
        for meta_file in self.lock_dir.glob("*.lock"):
            meta = self._read_meta(meta_file)
            if meta is not None:
                now = _utc_now()
                meta = {**meta, "age": int(now - meta.get("acquired_at", now))}
                result.append(meta)
        return result

    @staticmethod
    def _read_meta(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # lockfile 损坏 (并发写崩? 手动改?) 当作无锁, 别阻塞 agent
            return None

    @staticmethod
    def _write_meta(path: Path, meta: dict[str, Any]) -> None:
        # atomic_write: open+write+os.replace (同 write_text_atomic 模式), 防并发读半写 lockfile.
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(meta, ensure_ascii=False)
        tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, path)


__all__ = ("AdvisoryLock",)
