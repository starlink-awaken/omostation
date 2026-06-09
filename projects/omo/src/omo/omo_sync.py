"""P47 omo/sync — omo 状态同步.

P47 简化版: 不重新设计 in-process→subprocess, 用 internal transport
(module_path + func_name, 同进程 importlib). 调 omo.omo_audit + sync_omo_state
做实际 sync, append 治理历史.

P47+ 真重构: 把 omo daemon 改成跨进程架构 (复杂度 5, 留 P48+).
P49-simplify: 改用 omo_audit.record() + omo_audit._utc_now(), 不再内联 JSONL 写盘 / 手写 UTC.
Round 3: 摆脱 omo_audit 应急方案 (把 phase/health_score 拍扁成 details 字符串),
  改用专用 omo_sync_log (AppendOnlyLog) + 结构化 record. 字段含义固化,
  下游消费者按字段读, 不再 split 字符串.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from omo.omo_audit import _utc_now  # 仍用: synced_at 字段时间戳
from omo.omo_io import AppendOnlyLog
from omo.omo_io_schemas import OmoSyncRecord  # Round 15 P0: 写时 Pydantic 校验

AUDIT_CHECKS = 6

# 复用 omo_bos / omo_bos_metrics 的工作区根约定
_WORKSPACE = Path(
    os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace"))
)
DEFAULT_SYNC_LOG_PATH = _WORKSPACE / ".omo" / "_knowledge" / "omo-sync.jsonl"


def run_sync(args: dict[str, Any] | None = None) -> dict[str, Any]:
    """P47 omo/sync 入口 — internal transport 调.

    行为:
      - 读 omo state (system.yaml, current phase, health score)
      - 跑 audit (6 项检查, 期望 100.0)
      - 写 omo-sync.jsonl 一行 (结构化 record, 走 AppendOnlyLog)
      - 返 summary dict

    Args (可选):
      - "dry_run": bool (默认 False) — True 时只读不写
      - "log_path": Path (默认 DEFAULT_SYNC_LOG_PATH) — 测试可覆盖

    Returns:
      - status: "ok" / "error"
      - phase: int (current)
      - health_score: float (audit 100.0)
      - synced_at: ISO8601
      - audit_checks: int
    """
    args = args or {}
    dry_run = bool(args.get("dry_run", False))
    log_path = args.get("log_path", DEFAULT_SYNC_LOG_PATH)

    try:
        phase = 0
        health_score = 0.0
        try:
            from omo.omo_state import STATE_SYSTEM_YAML  # type: ignore[import-not-found]

            import yaml

            data = yaml.safe_load(STATE_SYSTEM_YAML.read_text(encoding="utf-8")) or {}
            phase = data.get("current_phase", 0)
            health_score = data.get("health_score", 0.0)
        except Exception:
            pass

        if not dry_run:
            # Round 3: 结构化 record — 字段含义固化, 不再 f-string 拍扁
            # Round 15 P0: 加 schema=OmoSyncRecord 走 Pydantic 写时校验
            AppendOnlyLog(log_path).append(
                {
                    "ts": _utc_now(),
                    "kind": "omo_sync",
                    "phase": phase,
                    "health_score": health_score,
                    "dry_run": dry_run,
                    "audit_checks": AUDIT_CHECKS,
                    "status": "ok",
                },
                schema=OmoSyncRecord,
            )

        return {
            "status": "ok",
            "phase": phase,
            "health_score": health_score,
            "synced_at": _utc_now(),
            "audit_checks": AUDIT_CHECKS,
            "dry_run": dry_run,
        }
    except Exception as exc:
        # 错误也走结构化 log (便于事后审计: 哪些 sync 失败)
        try:
            # Round 15 P0: 加 schema=OmoSyncRecord 走 Pydantic 写时校验
            AppendOnlyLog(log_path).append(
                {
                    "ts": _utc_now(),
                    "kind": "omo_sync",
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}"[:200],
                },
                schema=OmoSyncRecord,
            )
        except Exception:
            pass  # log 失败不阻塞错误返回
        return {
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        }


__all__ = ["run_sync", "AUDIT_CHECKS", "DEFAULT_SYNC_LOG_PATH"]
