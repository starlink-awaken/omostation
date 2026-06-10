"""AppendOnlyLog + fcntl_lock — §12 跨仓物理 SSOT 实现 (Round 24 P0).

原位置: omo_io.py (Round 1-5 收口, 历史 SSOT)
当前位置: omo._shared.append_only_log (§12 跨仓契约配套)

§12.1.1 不变量 (物理写盘 SSOT):
  - JSONL 物理写盘只走 AppendOnlyLog, 禁裸 open+write
  - 默认锁 = threading.Lock (单进程, 线程安全)
  - 跨进程: 注入 fcntl_lock (POSIX) / portalocker (Windows, 留 owner 实现)
  - 容错: read_all 错行保留为 {"raw": ...}, 不静默丢

设计原则 (与 omo_io.py 原版一致):
  - **SSOT**: JSONL 物理读写只此一处
  - **DRY**: 取代 omo_audit/omo_bos_metrics/omo_sync 中各自实现的 open+json.dump+write
  - **KISS**: AppendOnlyLog 不知道领域语义, 只管 log 物理; 聚合逻辑在领域模块
  - **可换锁策略**: 默认 threading.Lock; 跨进程可注入 fcntl_lock

§12 跨仓示例 (Python):
  from omo._shared.append_only_log import AppendOnlyLog, fcntl_lock
  from pathlib import Path

  log = AppendOnlyLog(Path("/path/to/log.jsonl"))
  log.append({"ts": "2026-06-10T01:00:00Z", "actor": "user", "action": "x"})

  # 跨进程: 注入 fcntl_lock
  log = AppendOnlyLog(
      path,
      lock=fcntl_lock(path.with_suffix(".lock")),
  )
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, ContextManager


class fcntl_lock:
    """POSIX 文件锁 — 跨进程安全 (Round 4 fcntl 注入样板).

    用途: AppendOnlyLog 跨进程并发写时, 默认 ``threading.Lock`` 不够 —
    不同进程拿不到同一个 threading.Lock, 会产生交错半行.
    解法: 用 ``fcntl.flock`` (POSIX 咨询锁) 锁住 .lock sidecar 文件.

    用法:
        log = AppendOnlyLog(path, lock=fcntl_lock(path.with_suffix(".lock")))
        # 跨 2 进程并发 100 次 append, 0 交错, 0 丢行

    平台: 仅 POSIX (Linux/macOS). Windows 需 portalocker 替代, 老王不写.
    """

    def __init__(self, lock_path: Path) -> None:
        self.lock_path = Path(lock_path)
        self._fd: int | None = None

    def __enter__(self) -> "fcntl_lock":
        import fcntl  # POSIX-only; 延迟 import 让 Windows 测试可 import
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR, 0o644)
        fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._fd is not None:
            import fcntl
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            finally:
                os.close(self._fd)
                self._fd = None


class AppendOnlyLog:
    """Append-only JSONL log — domain-agnostic (§12 跨仓物理 SSOT).

    责任 (只做这一件事):
      - 追加一条 record (单行, 原子, 带锁)
      - 读所有 records (容错)
      - 读最近 N 条 / 过滤 since ts
      - 清空文件 (原子, 返回行数供审计)
      - 文件轮转 (rotate, Round 8 P0)
      - 通用聚合 (group_by, Round 7 P0)

    不知道:
      - record 字段含义 (uri vs debt_id vs ...)
      - 怎么聚合 (group by 什么字段, 算 p95 还是 unique count)

    锁策略:
      - 默认 ``threading.Lock`` (单进程, 线程安全)
      - 跨进程: 注入 ``fcntl_lock`` (POSIX)

    用法:
        log = AppendOnlyLog(Path("audit.jsonl"))
        log.append({"ts": _utc_now(), "action": "x"})
        records = log.read_all()
        last10 = log.tail(10)
        recent = log.since("2026-06-09T00:00:00Z")
        n = log.clear()
    """

    def __init__(
        self,
        path: Path,
        *,
        lock: ContextManager | None = None,
    ) -> None:
        self.path = Path(path)
        self._lock = lock if lock is not None else threading.Lock()

    def append(
        self,
        record: dict[str, Any] | Any,  # dict 或 Pydantic BaseModel 实例
        *,
        schema: type | None = None,
        **json_kwargs: Any,
    ) -> dict[str, Any]:
        """追加一条 record. 自动创建父目录. 返回 record (供链式调用).

        Args:
            record: 写入的 dict, 或 Pydantic BaseModel 实例 (自动 model_dump).
            schema: 可选 Pydantic BaseModel class. 若提供, record 写入前
              经 ``schema.model_validate(record)`` 校验. 校验失败抛
              ``pydantic.ValidationError`` (fail-fast, 不静默落 raw).
              适用场景: 想在写盘前锁住 record 形状, 防止 schema 漂移.
            **json_kwargs: 透传给 ``json.dumps()`` (e.g. ``sort_keys=True``
              保 omo_history 与 kairon-governance 旧 JSONL 兼容).

        Round 9 P1: 加 Pydantic 写时校验 (opt-in). 不传 schema = 旧行为不变.
        """
        # 1. Pydantic instance → dict (透明转换)
        if hasattr(record, "model_dump") and callable(getattr(record, "model_dump", None)):
            record = record.model_dump()

        # 2. Pydantic schema 校验 (fail-fast, 不静默)
        if schema is not None:
            schema.model_validate(record)  # 失败抛 pydantic.ValidationError

        self.path.parent.mkdir(parents=True, exist_ok=True)
        # 默认 ensure_ascii=False (中文不转 \\u), 但允许覆盖 (e.g. 测试)
        kwargs: dict[str, Any] = {"ensure_ascii": False}
        kwargs.update(json_kwargs)
        line = json.dumps(record, **kwargs)
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass  # 某些 fs (e.g. 某些 tmpfs) 不支持 fsync
        return record

    def read_all(self) -> list[dict[str, Any]]:
        """读所有 records (容错: 错行保留为 ``{"raw": ...}``)."""
        # 延迟 import 避免循环依赖 (omo_io.read_jsonl 在原 omo_io.py)
        from omo.omo_io import read_jsonl
        return read_jsonl(self.path)

    def tail(self, n: int, *, initial_chunk_size: int = 8192, max_chunk_size: int = 1_048_576) -> list[dict[str, Any]]:
        """读最近 N 条 records (Round 9 P2 真正 O(n) 性能).

        算法: windowed seek — 从末尾 8KB 起始, 读 + parse 累计, 不够 n 条就
        把窗口翻倍 (doubling), 直到满足或触顶 1MB. 真正 O(n) 而非 O(file_size).
        """
        from omo.omo_io import read_jsonl
        if n <= 0 or not self.path.exists():
            return []
        file_size = self.path.stat().st_size
        if file_size == 0:
            return []

        # 小文件: 直接全读 (windowed seek 复杂度不值得)
        if file_size <= initial_chunk_size:
            return read_jsonl(self.path)[-n:]

        # 大文件: windowed seek (doubling chunk, 早停当 ≥ n real records)
        chunk_size = initial_chunk_size
        all_lines: list[bytes] = []
        pos = file_size
        with open(self.path, "rb") as f:
            while pos > 0:
                read_size = min(chunk_size, pos)
                pos -= read_size
                f.seek(pos)
                chunk = f.read(read_size)
                # Drop first 仅当 chunk 起始 mid-line (前 1 byte 不是 \n).
                if pos > 0:
                    f.seek(pos - 1)
                    prev_byte = f.read(1)
                    if prev_byte != b"\n":
                        chunk_lines = chunk.split(b"\n")[1:]
                    else:
                        chunk_lines = chunk.split(b"\n")
                else:
                    chunk_lines = chunk.split(b"\n")
                # Prepend (we're reading backwards in time)
                all_lines = chunk_lines + all_lines
                # 累计非空行数 (cheap, 不 full parse)
                real_count = sum(1 for _ in all_lines if _.strip())
                if real_count >= n:
                    # 够了, 跳出循环
                    break
                # 不够: 翻倍窗口, 下一轮读更多
                if chunk_size >= max_chunk_size:
                    # 触顶: 已读 1MB+ 但仍不够 n, 退化到 '读完剩余文件'
                    while pos > 0:
                        read_size = min(chunk_size, pos)
                        pos -= read_size
                        f.seek(pos)
                        chunk = f.read(read_size)
                        if pos > 0:
                            f.seek(pos - 1)
                            prev_byte = f.read(1)
                            if prev_byte != b"\n":
                                chunk_lines = chunk.split(b"\n")[1:]
                            else:
                                chunk_lines = chunk.split(b"\n")
                        else:
                            chunk_lines = chunk.split(b"\n")
                        all_lines = chunk_lines + all_lines
                    break
                chunk_size = min(chunk_size * 2, max_chunk_size)

        # 解析: '先 parse 后取 n' (避免 chunk 边界 trailing empty 偏移)
        records: list[dict[str, Any]] = []
        for line_bytes in all_lines:
            line = line_bytes.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                records.append({"raw": line[:200]})
        return records[-n:]

    def since(
        self,
        ts: str,
        *,
        field: str = "ts",
    ) -> list[dict[str, Any]]:
        """过滤 ``field >= ts`` 的 records.

        Args:
            ts: ISO8601 时间戳 (e.g. ``"2026-06-09T00:00:00Z"``).
            field: 时间戳字段名. omo_audit 用 ``ts`` (默认), omo_bos_metrics 用
              ``recorded_at``. 显式传 field 避免 2 种约定混用.

        Returns:
            records where ``record[field] >= ts``. 字符串比较对 ISO8601 也成立
            (lexicographic = chronological for ISO 8601 with same format).
        """
        return [r for r in self.read_all() if r.get(field, "") >= ts]

    def clear(self) -> int:
        """原子清空文件. 返回清空前 records 数 (供审计).

        注: 文件保留 (空文件), 不删除 — 避免消费者误判文件不存在.
        """
        from omo.omo_io import write_text_atomic
        if not self.path.exists():
            return 0
        n = len(self.read_all())
        write_text_atomic(self.path, "")
        return n

    def rotate(self, max_bytes: int) -> bool:
        """文件 > max_bytes 时, rename 当前到 ``.1``, 重新空文件 (Round 8 P0).

        简单轮转策略: 只保留 1 个 backup (覆盖式). 无压缩 (append-only
        log 本身已紧凑, gzip 一般在 daemon 周期外做).
        """
        if max_bytes <= 0 or not self.path.exists():
            return False
        size = self.path.stat().st_size
        if size < max_bytes:
            return False
        backup = self.path.with_suffix(self.path.suffix + ".1")
        backup.unlink(missing_ok=True)
        self.path.rename(backup)
        return True

    def group_by(self, field: str, *, path: Path | None = None) -> dict[str, int]:
        """按 ``field`` 分组统计 record 数 (Round 7 P0 通用聚合)."""
        log = AppendOnlyLog(path) if path is not None else self
        from collections import defaultdict
        counter: dict[str, int] = defaultdict(int)
        for r in log.read_all():
            v = r.get(field, "<missing>")
            counter[str(v)] += 1
        return dict(counter)


__all__ = ("AppendOnlyLog", "fcntl_lock")
