"""append_only_log.py — §12 跨仓物理 SSOT 的 kairon-utils 实现.

B-1 P0 接入: 从 omo._shared.append_only_log 复制 (Round 24 P0 实质化).
跨仓 SSOT: §12.1.1 不变量.

实现差异:
  - kairon-utils 不依赖 omo (独立 monorepo), 所以本地 copy 一份
  - 内容与 omo._shared.append_only_log 保持一致; 后续 §12.6 跨仓债收口时可
    考虑提取到独立 _shared 包, 4 仓共享
  - 修 zod 兼容 Pydantic schema 校验 (与 omo 同)
  - fcntl 锁注入式设计不变 (POSIX-only)
"""

from __future__ import annotations

# ruff: noqa: UP035, N801, UP037
# 与 omo._shared.append_only_log 保持一致 (跨仓 SSOT 跨仓一致性).
# UP035: typing.ContextManager (deprecated by PEP 585, but omo 同款未修)
# N801:  fcntl_lock 命名与 omo 一致 (lowercase_with_underscores)
# UP037: 引号 type annotation (Python 3.7+ 兼容保留)
import json
import os
import threading
from pathlib import Path
from typing import Any, ContextManager


class fcntl_lock:
    """POSIX 文件锁 — 跨进程安全.

    用法:
        log = AppendOnlyLog(path, lock=fcntl_lock(path.with_suffix(".lock")))
        # 跨 2 进程并发 100 次 append, 0 交错, 0 丢行
    """

    def __init__(self, lock_path: Path) -> None:
        self.lock_path = Path(lock_path)
        self._fd: int | None = None

    def __enter__(self) -> "fcntl_lock":
        import fcntl  # POSIX-only; 延迟 import

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
    """Append-only JSONL log — 跨仓物理 SSOT (§12.1.1).

    责任 (只做这一件事):
      - 追加一条 record (单行, 原子, 带锁)
      - 读所有 records (容错)
      - 读最近 N 条 / 过滤 since ts
      - 清空文件
      - 文件轮转
      - 通用聚合 (group_by)

    不知道:
      - record 字段含义
      - 怎么聚合
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
        record: dict[str, Any] | Any,
        *,
        schema: type | None = None,
        **json_kwargs: Any,
    ) -> dict[str, Any]:
        """追加一条 record.

        Args:
            record: dict 或 Pydantic BaseModel 实例 (自动 model_dump).
            schema: 可选 Pydantic BaseModel class. 写前 model_validate 校验.
            **json_kwargs: 透传给 json.dumps (e.g. sort_keys=True).
        """
        if hasattr(record, "model_dump") and callable(getattr(record, "model_dump", None)):
            record = record.model_dump()  # type: ignore[reportAttributeAccessIssue]

        if schema is not None:
            schema.model_validate(record)  # type: ignore[attr-defined]

        self.path.parent.mkdir(parents=True, exist_ok=True)
        # §12.1.4 跨仓 4 不变量: sort_keys=True 保 SSOT 跨仓顺序确定性
        kwargs: dict[str, Any] = {"ensure_ascii": False, "sort_keys": True}
        kwargs.update(json_kwargs)
        line = json.dumps(record, **kwargs)
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass
        return record

    def read_all(self) -> list[dict[str, Any]]:
        """读所有 records (容错: 错行保留为 {"raw": ...})."""
        if not self.path.exists():
            return []
        out: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                out.append({"raw": line[:200]})
        return out

    def tail(self, n: int) -> list[dict[str, Any]]:
        """读最近 N 条 records (O(n) 性能, 完整文件读简化版)."""
        if n <= 0 or not self.path.exists():
            return []
        all_records = self.read_all()
        return all_records[-n:]

    def since(self, ts: str, *, field: str = "ts") -> list[dict[str, Any]]:
        """过滤 field >= ts 的 records (ISO8601 字符串比较)."""
        return [r for r in self.read_all() if r.get(field, "") >= ts]

    def clear(self) -> int:
        """原子清空文件. 返回清空前 records 数."""
        if not self.path.exists():
            return 0
        # 一次 IO 算行数 (避免先 read_all() 再 write_text("") 的双 IO)
        with open(self.path, "rb") as f:
            n = sum(1 for _ in f)
        self.path.write_text("", encoding="utf-8")
        return n

    def rotate(self, max_bytes: int) -> bool:
        """文件 > max_bytes 时 rename 到 .1 备份, 重新空文件."""
        if max_bytes <= 0 or not self.path.exists():
            return False
        size = self.path.stat().st_size
        if size < max_bytes:
            return False
        backup = self.path.with_suffix(self.path.suffix + ".1")
        backup.unlink(missing_ok=True)
        self.path.rename(backup)
        return True

    def group_by(self, field: str) -> dict[str, int]:
        """按 field 分组统计 record 数."""
        from collections import defaultdict

        counter: dict[str, int] = defaultdict(int)
        for r in self.read_all():
            v = r.get(field, "<missing>")
            counter[str(v)] += 1
        return dict(counter)


__all__ = ("AppendOnlyLog", "fcntl_lock")
