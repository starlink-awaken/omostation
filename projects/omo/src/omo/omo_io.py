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

    def append(
        self,
        record: dict[str, Any],
        **json_kwargs: Any,
    ) -> dict[str, Any]:
        """追加一条 record. 自动创建父目录. 返回 record (供链式调用).

        Args:
            record: 写入的 dict.
            **json_kwargs: 透传给 ``json.dumps()`` (e.g. ``sort_keys=True``
              保 omo_history 与 kairon-governance 旧 JSONL 兼容).
        """
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
        return read_jsonl(self.path)

    def tail(self, n: int, *, chunk_size: int = 8192) -> list[dict[str, Any]]:
        """读最近 N 条 records (Round 7 P1 reverse-seek 优化, Round 8 P1 容错强化).

        算法: 读所有 chunks, parse 后取最后 N 条. 复杂度 O(file_size), 与 read_all 同.
        区别于 read_all: 提供 'reverse-seek 风格' 内存访问模式 (chunked, 8KB).
        真实 O(n) 性能优化需 'windowed seek' (按需扩大读窗口), 留 Round 9+.

        Args:
            n: max records to return (≤0 → empty list).
            chunk_size: 单次读字节数 (默认 8KB). 当前未做 IO 优化, 仅语义.

        边界:
          - 小文件 (≤chunk_size): 走 ``read_jsonl`` 全读
          - 大文件: 按 chunk 反向读, drop first 仅当 mid-line
          - UTF-8 跨 chunk: ``errors='replace'`` 容错
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

        # 大文件: 按 chunk_size 反向读, 累计所有 lines
        raw_lines: list[bytes] = []
        pos = file_size
        with open(self.path, "rb") as f:
            while pos > 0:
                read_size = min(chunk_size, pos)
                pos -= read_size
                f.seek(pos)
                chunk = f.read(read_size)
                # Drop first 仅当 chunk 起始 mid-line (前 1 byte 不是 \n).
                # 若前 1 byte 是 \n, 第一行是完整行 (前一行以 \n 结尾), 不可丢.
                if pos > 0:
                    f.seek(pos - 1)
                    prev_byte = f.read(1)
                    if prev_byte != b"\n":
                        chunk_lines = chunk.split(b"\n")[1:]
                    else:
                        chunk_lines = chunk.split(b"\n")
                else:
                    chunk_lines = chunk.split(b"\n")
                raw_lines = chunk_lines + raw_lines

        # 解析: parse all lines → take last n (skip empty, JSON 错入 raw)
        # 设计: '先 parse 后取 n' 而非 'raw_lines[-n:] 再 parse' —
        # 避免 chunk 边界 trailing empty 偏移最后 n 个真实 record.
        records: list[dict[str, Any]] = []
        for line_bytes in raw_lines:
            line = line_bytes.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                records.append({"raw": line[:200]})
        return records[-n:]
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

    def rotate(self, max_bytes: int) -> bool:
        """文件 > max_bytes 时, rename 当前到 ``.1``, 重新空文件 (Round 8 P0).

        简单轮转策略: 只保留 1 个 backup (覆盖式). 无压缩 (append-only
        log 本身已紧凑, gzip 一般在 daemon 周期外做).

        Returns:
            True 若实际 rotate, False 若未达阈值.

        边界:
          - max_bytes ≤ 0: 不做任何事, 返 False (锁: 0 字节 = 0 触发 = 永远不 rotate)
          - 文件不存在: 返 False
          - 文件 < max_bytes: 不 rotate (返 False)
          - .1 已存在: 覆盖 (用户接受)

        推荐阈值:
          - bos-metrics: 10MB ≈ 100K records, 30 天 @ 50/min
          - omo-history: 1MB (审计记录少, 文件小也无所谓)
          - omo-alerts: 1MB
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
