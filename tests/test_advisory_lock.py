"""AdvisoryLock 跨 session agent 协调锁测试 (TASK-94BB9C70).

test_plan: 两 agent 并发改同文件, 第二个被 lock 拒.

覆盖:
  - 基础 acquire/release
  - 核心: 两 holder 并发, 第二个被拒 (test_plan)
  - 可重入: 同 holder 再 acquire 刷新 ttl
  - ttl 防死锁: 过期锁可抢占
  - holder 校验: B 不能释放 A 的锁
  - 真跨进程: 子进程持有, 主进程被拒 (模拟两 agent session)
  - check/list 查询
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from omo._shared.advisory_lock import AdvisoryLock


def test_acquire_release_basic(tmp_path: Path) -> None:
    """基础: acquire → ok, release → ok."""
    lock = AdvisoryLock(tmp_path / "locks")
    r = lock.acquire("omo_ingress.py", holder="A")
    assert r["status"] == "ok"
    assert r.get("acquired") is True
    r = lock.release("omo_ingress.py", holder="A")
    assert r["status"] == "ok"


def test_two_holders_second_rejected(tmp_path: Path) -> None:
    """核心 test_plan: A 持有, B acquire 被拒, 返回 holder=A."""
    lock = AdvisoryLock(tmp_path / "locks")
    r1 = lock.acquire("shared.py", holder="A")
    assert r1["status"] == "ok"
    r2 = lock.acquire("shared.py", holder="B")
    assert r2["status"] == "locked"
    assert r2["holder"] == "A"
    # A release 后 B 能拿
    lock.release("shared.py", holder="A")
    r3 = lock.acquire("shared.py", holder="B")
    assert r3["status"] == "ok"


def test_reentrant_same_holder(tmp_path: Path) -> None:
    """同 holder 再 acquire → reentrant (刷新 ttl, 不报错)."""
    lock = AdvisoryLock(tmp_path / "locks")
    lock.acquire("f.py", holder="A", ttl=100)
    r = lock.acquire("f.py", holder="A", ttl=200)
    assert r["status"] == "ok"
    assert r.get("reentrant") is True
    # ttl 被刷新到 200
    meta = AdvisoryLock._read_meta(lock._meta_file("f.py"))
    assert meta is not None
    assert meta["ttl"] == 200


def test_ttl_expiry_preempts(tmp_path: Path) -> None:
    """ttl 过期 → 别的 agent 可抢占 (防 agent 崩溃死锁)."""
    lock = AdvisoryLock(tmp_path / "locks")
    lock.acquire("f.py", holder="A", ttl=1)  # 1s ttl
    time.sleep(1.2)  # 等过期
    r = lock.acquire("f.py", holder="B")
    assert r["status"] == "ok"  # 过期抢占成功
    assert r.get("acquired") is True


def test_release_forbidden_wrong_holder(tmp_path: Path) -> None:
    """B 不能释放 A 的锁 (防误释放/恶意释放)."""
    lock = AdvisoryLock(tmp_path / "locks")
    lock.acquire("f.py", holder="A")
    r = lock.release("f.py", holder="B")
    assert r["status"] == "forbidden"
    assert r["holder"] == "A"
    # A 自己能释放
    r = lock.release("f.py", holder="A")
    assert r["status"] == "ok"


def test_release_not_locked(tmp_path: Path) -> None:
    """release 未锁资源 → not_locked (幂等, 不报错)."""
    lock = AdvisoryLock(tmp_path / "locks")
    r = lock.release("never.py", holder="A")
    assert r["status"] == "not_locked"


def test_check_status(tmp_path: Path) -> None:
    """check: free → locked → stale."""
    lock = AdvisoryLock(tmp_path / "locks")
    assert lock.check("f.py")["status"] == "free"
    lock.acquire("f.py", holder="A", ttl=1)
    assert lock.check("f.py")["status"] == "locked"
    time.sleep(1.2)
    assert lock.check("f.py")["status"] == "stale"


def test_list_locks(tmp_path: Path) -> None:
    """list_locks: 列出所有 lockfile metadata."""
    lock = AdvisoryLock(tmp_path / "locks")
    lock.acquire("a.py", holder="A")
    lock.acquire("b.py", holder="B")
    locks = lock.list_locks()
    resources = {lk["resource"] for lk in locks}
    assert resources == {"a.py", "b.py"}


def test_corrupt_lockfile_treated_as_free(tmp_path: Path) -> None:
    """lockfile 损坏 → 当无锁 (不阻塞 agent, 容错)."""
    lock = AdvisoryLock(tmp_path / "locks")
    meta_file = lock._meta_file("f.py")
    meta_file.parent.mkdir(parents=True, exist_ok=True)
    meta_file.write_text("NOT JSON {broken", encoding="utf-8")
    # 损坏 → check 当 free, acquire 能拿
    assert lock.check("f.py")["status"] == "free"
    r = lock.acquire("f.py", holder="A")
    assert r["status"] == "ok"


def test_cross_process_two_agents(tmp_path: Path) -> None:
    """真跨进程: 子进程 acquire 持有, 主进程 acquire 被拒.

    模拟两 agent session (不同进程) 通过 lockfile 协调 — 病根场景.
    用 subprocess + sleep 序列化 (子进程先拿, 主进程后试).
    """
    lock_dir = tmp_path / "locks"
    # 子进程: acquire 后 sleep 3s 持有锁
    child_code = (
        "import sys, time\n"
        f"sys.path.insert(0, {str(Path(__file__).resolve().parents[1] / 'src')!r})\n"
        "from omo._shared.advisory_lock import AdvisoryLock\n"
        f"lock = AdvisoryLock({str(lock_dir)!r})\n"
        "r = lock.acquire('shared_workspace.py', holder='child-agent', ttl=60)\n"
        "assert r['status'] == 'ok', r\n"
        "time.sleep(3)\n"
    )
    proc = subprocess.Popen([sys.executable, "-c", child_code])
    try:
        time.sleep(1.0)  # 等子进程 acquire 落盘
        # 主进程 (模拟 agent B) 试 acquire → 应被拒
        lock = AdvisoryLock(lock_dir)
        r = lock.acquire("shared_workspace.py", holder="main-agent")
        assert r["status"] == "locked", f"应被拒, 实际: {r}"
        assert r["holder"] == "child-agent"
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_different_resources_independent(tmp_path: Path) -> None:
    """不同 resource 互不干扰 (A 锁 f1 不影响 B 锁 f2)."""
    lock = AdvisoryLock(tmp_path / "locks")
    r1 = lock.acquire("f1.py", holder="A")
    r2 = lock.acquire("f2.py", holder="B")
    assert r1["status"] == "ok"
    assert r2["status"] == "ok"
