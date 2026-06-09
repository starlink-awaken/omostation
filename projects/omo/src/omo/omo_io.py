"""OMO I/O utilities — atomic file writes + append-only log abstraction.

层级 (从低到高):
  1. ``write_text_atomic`` / ``write_yaml_atomic`` — 原子写 (tempfile + fsync + replace)
  2. ``read_jsonl`` — 公开 JSONL 容错读 (JSON 错行保留为 ``{"raw": ...}``)
  3. ``AppendOnlyLog`` — append-only JSONL 物理读写抽象 (SSOT)

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


# ── AppendOnlyLog 抽象 (高层) ──────────────────────────────


class AppendOnlyLog:
    """Append-only JSONL log — domain-agnostic.

    责任 (只做这一件事):
      - 追加一条 record (单行, 原子, 带锁)
      - 读所有 records (容错)
      - 清空文件 (原子, 返回行数供审计)

    不知道:
      - record 字段含义 (uri vs debt_id vs ...)
      - 怎么聚合 (group by 什么字段, 算 p95 还是 unique count)

    锁策略:
      - 默认 ``threading.Lock`` (单进程, 线程安全)
      - 跨进程: 注入 fcntl wrapper 或 portalocker

    用法:
        log = AppendOnlyLog(Path("audit.jsonl"))
        log.append({"ts": _utc_now(), "action": "x"})
        records = log.read_all()
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

    def clear(self) -> int:
        """原子清空文件. 返回清空前 records 数 (供审计).

        注: 文件保留 (空文件), 不删除 — 避免消费者误判文件不存在.
        """
        if not self.path.exists():
            return 0
        n = len(self.read_all())
        write_text_atomic(self.path, "")
        return n


__all__ = (
    "AppendOnlyLog",
    "read_jsonl",
    "write_text_atomic",
    "write_yaml_atomic",
)
