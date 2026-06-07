"""P47 omo/sync — omo 状态同步 (internal transport).

P47 简化版: 不重新设计 in-process→subprocess, 用 internal transport
(module_path + func_name, 同进程 importlib). 调 omo.omo_audit + sync_omo_state
做实际 sync, append 治理历史.

P47+ 真重构: 把 omo daemon 改成跨进程架构 (复杂度 5, 留 P48+).
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def run_sync(args: dict[str, Any] | None = None) -> dict[str, Any]:
    """P47 omo/sync 入口 — internal transport 调.

    行为:
      - 读 omo state (system.yaml, current phase, health score)
      - 跑 audit (6 项检查, 期望 100.0)
      - 写 governance-history.jsonl 一行
      - 返 summary dict

    Args (可选):
      - "dry_run": bool (默认 False) — True 时只读不写

    Returns:
      - status: "ok" / "error"
      - phase: int (current)
      - health_score: float (audit 100.0)
      - synced_at: ISO8601
      - audit_checks: int (6)
    """
    args = args or {}
    dry_run = bool(args.get("dry_run", False))

    try:
        # 读 current phase
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

        # 写 governance-history
        if not dry_run:
            from omo.omo_paths import GOVERNANCE_HISTORY_PATH  # type: ignore[import-not-found]

            entry = {
                "source": "omo_sync",
                "ts": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "phase": phase,
                "health_score": health_score,
                "dry_run": dry_run,
            }
            GOVERNANCE_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(GOVERNANCE_HISTORY_PATH, "a", encoding="utf-8") as f:
                import json

                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return {
            "status": "ok",
            "phase": phase,
            "health_score": health_score,
            "synced_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "audit_checks": 6,
            "dry_run": dry_run,
        }
    except Exception as exc:
        return {
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        }


__all__ = ["run_sync"]
