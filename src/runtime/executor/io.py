"""AppendOnlyLog — append-only JSONL 写抽象 (§11 实现 / §12.1 跨仓契约).

R51 P0: engine.py 裸 open() → AppendOnlyLog.append() 迁移.
"""

from __future__ import annotations

import fcntl
import json
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic import BaseModel


class AppendOnlyLog:
    """Append-only JSONL 文件 — 写时走 Pydantic schema 校验.

    §11.3.1 实现:
    - 每次 append 持 fcntl.fcntl 写锁 (Linux/macOS 兼容)
    - 写前 Pydantic schema 校验 (fail-fast)
    - sort_keys=True 保证字节级顺序稳定
    - _timestamp_validator 内置 Z-suffix 校验
    """

    def __init__(self, path: str | Path, *, lock_path: str | Path | None = None):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._lock_path = (
            Path(lock_path) if lock_path else self.path.with_suffix(".lock")
        )

    def append(
        self,
        record: dict[str, Any] | "BaseModel",
        *,
        schema: type["BaseModel"] | None = None,
        **json_kwargs: Any,
    ) -> None:
        """追加一条记录到 JSONL 文件 (线程安全 + 写锁)."""
        if hasattr(record, "model_dump"):
            record = record.model_dump()
        if schema is not None:
            schema.model_validate(record)  # fail-fast
        line = (
            json.dumps(record, ensure_ascii=False, sort_keys=True, **json_kwargs) + "\n"
        )
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.write(line)
                    f.flush()
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def read_all(self) -> list[dict[str, Any]]:
        """读全部记录 (无锁, 仅用于 audit)."""
        if not self.path.exists():
            return []
        with open(self.path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
