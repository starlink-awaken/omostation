"""OMO I/O utilities — atomic file writes + append-only log abstraction.

层级 (从低到高):
  1. ``write_text_atomic`` / ``write_yaml_atomic`` — 原子写 (tempfile + fsync + replace)
  2. ``read_jsonl`` — 公开 JSONL 容错读 (JSON 错行保留为 ``{"raw": ...}``)
  3. ``AppendOnlyLog`` — append-only JSONL 物理读写抽象 (SSOT)
  4. ``fcntl_lock`` — POSIX 跨进程文件锁 (供 AppendOnlyLog 注入升级)

设计原则:
  - **SSOT**: JSONL 物理写盘只此一处, 3+ 领域 (omo_audit / omo_bos_metrics / omo_sync) 共享
  - **DRY**: 取代 omo_audit + omo_bos_metrics 中各自实现的 ``open("a") + json.dumps + write``
  - **KISS**: AppendOnlyLog 不知道领域语义, 只管 log 物理; 聚合逻辑在领域模块
  - **可换锁策略**: 默认 ``threading.Lock`` (单进程); 上生产可注入 fcntl (跨进程)
"""
from __future__ import annotations

import json
import os
import threading
from collections import defaultdict
from pathlib import Path
from typing import Any, ContextManager

import yaml

# ── 原子写 (低层) ────────────────────────────────────────────


def _replace_atomic(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    with open(tmp_path, "w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


def write_text_atomic(path: Path, payload: str) -> None:
    _replace_atomic(path, payload)


def write_yaml_atomic(path: Path, data: dict[str, Any]) -> None:
    _replace_atomic(path, yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


# ── JSONL 容错读 (中层) ──────────────────────────────────────


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """读 JSONL 文件, 返回 list[dict].

    容错策略 (与 omo_observability._read_jsonl 一致):
      - 文件不存在 → ``[]``
      - 空行 → 跳过
      - JSON 解析失败 → 保留为 ``{"raw": line[:200]}`` (下游 ``r.get("uri")`` 自然返回 None, 无害)

    与 ``omo_audit.query`` (静默 drop) 的差异: 保留原始行方便事后审计.
    """
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            out.append({"raw": line[:200]})
    return out


# ── 跨进程文件锁 (POSIX) ──────────────────────────────────────


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
        import fcntl  # POSIX-only; 延迟 import 让 Windows 测试可 import omo_io
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


# ── AppendOnlyLog 抽象 (高层) ──────────────────────────────


class AppendOnlyLog:
    """Append-only JSONL log — domain-agnostic.

    责任 (只做这一件事):
      - 追加一条 record (单行, 原子, 带锁)
      - 读所有 records (容错)
      - 读最近 N 条 / 过滤 since ts
      - 清空文件 (原子, 返回行数供审计)

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

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        """追加一条 record. 自动创建父目录. 返回 record (供链式调用)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False)
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
        return read_jsonl(self.path)

    def tail(self, n: int, *, chunk_size: int = 8192) -> list[dict[str, Any]]:
        """读最近 N 条 records (Round 7 P1 reverse-seek 优化).

        实现: 从文件末尾按 chunk_size (默认 8KB) 反向读字节, 累计到
        N+1 条完整行为止. 不需要读整个文件 → O(n) 而非 O(file_size).

        Args:
            n: max records to return (≤0 → empty list).
            chunk_size: 单次读字节数 (默认 8KB). 调大可减少读次数, 调小可减少内存.

        边界:
          - 小文件 (≤chunk_size): 走 ``read_jsonl`` 全读, 等价于 ``read_all()[-n:]``
          - UTF-8 跨 chunk 边界: 罕见 (8KB / max 4B/char = 0.05%), 落 raw 容错
          - 文件为空: 返回 []
        """
        if n <= 0 or not self.path.exists():
            return []
        file_size = self.path.stat().st_size
        if file_size == 0:
            return []

        # 小文件: 直接全读 (reverse-seek 复杂度不值得)
        if file_size <= chunk_size:
            return read_jsonl(self.path)[-n:]

        # 大文件: reverse-seek 读 chunks
        raw_lines: list[bytes] = []
        pos = file_size
        with open(self.path, "rb") as f:
            while pos > 0 and len(raw_lines) < n + 1:
                read_size = min(chunk_size, pos)
                pos -= read_size
                f.seek(pos)
                chunk = f.read(read_size)
                chunk_lines = chunk.split(b"\n")
                # 若非文件首, 第一个元素是可能不完整的行, 丢弃
                if pos > 0:
                    chunk_lines = chunk_lines[1:]
                raw_lines = chunk_lines + raw_lines

        # 取最后 n 条 + 解析
        records: list[dict[str, Any]] = []
        for line_bytes in raw_lines[-n:]:
            line = line_bytes.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                records.append({"raw": line[:200]})
        return records

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

        Note:
            字符串比较对 ``"2026-06-09T01:00:00Z"`` vs ``"2026-06-09T00:00:00Z"``
            成立 (Z 结尾统一). 但混用 ``"2026-06-09T00:00:00Z"`` 和
            ``"2026-06-09T00:00:00+00:00"`` 时, 字符串比较会失真 — 调用方负责.
        """
        return [r for r in self.read_all() if r.get(field, "") >= ts]

    def clear(self) -> int:
        """原子清空文件. 返回清空前 records 数 (供审计).

        注: 文件保留 (空文件), 不删除 — 避免消费者误判文件不存在.
        """
        if not self.path.exists():
            return 0
        n = len(self.read_all())
        write_text_atomic(self.path, "")
        return n

    def group_by(self, field: str, *, path: Path | None = None) -> dict[str, int]:
        """按 ``field`` 分组统计 record 数 (Round 7 P0 通用聚合).

        返回 ``{field_value: count}`` dict. 适用于:
          - omo_audit.summary: ``log.group_by("action")`` → 替代手写 Counter
          - omo_bos_metrics.summary: ``log.group_by("status")`` → by_status
          - 任何"按某字段分组计数"场景

        边界:
          - field 缺失 → 归到 ``"<missing>"`` 分组 (不抛)
          - field 非 str (int/bool) → 走 ``str(v)`` 归一化
          - 大文件: O(file_size), 暂不优化 (与 read_all 一致)
        """
        log = AppendOnlyLog(path) if path is not None else self
        counter: dict[str, int] = defaultdict(int)
        for r in log.read_all():
            v = r.get(field, "<missing>")
            counter[str(v)] += 1
        return dict(counter)


__all__ = (
    "AppendOnlyLog",
    "fcntl_lock",
    "read_jsonl",
    "write_text_atomic",
    "write_yaml_atomic",
)
