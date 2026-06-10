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
from pathlib import Path
from typing import Any

import yaml

# Round 24 P0: AppendOnlyLog + fcntl_lock 实现搬到 omo._shared.append_only_log
# (§12 跨仓 SSOT). 本文件保留原子写 + JSONL 读 + re-export, 保 backward compat.
from omo._shared.append_only_log import AppendOnlyLog, fcntl_lock  # noqa: F401  (re-export)

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
# Round 24 P0: AppendOnlyLog + fcntl_lock 实际定义在 omo._shared.append_only_log
# (顶部 import 已 re-export). 本节留 placeholder 文档说明跨仓接入.

# AppendOnlyLog 真实实现 + 文档见:
#   omo._shared.append_only_log.AppendOnlyLog
#   omo._shared.append_only_log.fcntl_lock
# 跨仓接入示例见 §12.2.1 Step 1.

__all__ = (
    "AppendOnlyLog",
    "fcntl_lock",
    "read_jsonl",
    "write_text_atomic",
    "write_yaml_atomic",
)
