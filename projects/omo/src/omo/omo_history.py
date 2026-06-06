"""治理历史 — append-only JSONL(从 kairon_governance.history 迁移).

文件路径(默认): .omo/_knowledge/governance-history.jsonl
每行: {"date": "2026-06-06", "timestamp": "...", "total_score": 99.0, "grade": "A+",
       "checks": [...], "watchlist_count": N, "source": "omo_daemon"}

API:
  - append_entry(data, path)           追加一条记录
  - read_history(path, limit)          读历史(最新的在前)
  - score_trend(entries)               计算趋势统计
  - render_trend_chart(entries)        生成 ASCII 趋势图

设计原则:
  - 零外部依赖(仅标准库)
  - 追加写入失败不影响主流程(异常被 audit 等调用方捕获/上报)
  - 容忍历史文件缺失/损坏(坏行被跳过)
  - 与 kairon-governance 旧 JSONL 完全兼容(history 路径不变)
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from omo.omo_paths import GOVERNANCE_HISTORY_PATH

# 默认历史文件路径
DEFAULT_PATH = GOVERNANCE_HISTORY_PATH


def append_entry(
    data: dict[str, Any],
    path: Path | str | None = None,
) -> Path:
    """追加一条治理记录(同步, 行式追加).

    Args:
        data: 业务字段(date / timestamp 由本函数注入, 用户传入的会被覆盖)
        path: 目标 JSONL 文件路径; None → 使用 DEFAULT_PATH

    Returns:
        最终写入的文件路径
    """
    target = Path(path) if path is not None else DEFAULT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    entry: dict[str, Any] = dict(data)
    entry["date"] = now.strftime("%Y-%m-%d")
    entry["timestamp"] = now.isoformat()
    line = json.dumps(entry, ensure_ascii=False, sort_keys=True)
    with open(target, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return target


def read_history(
    path: Path | str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """读历史(最新的在前)."""
    target = Path(path) if path is not None else DEFAULT_PATH
    if not target.exists():
        return []
    try:
        raw = target.read_text(encoding="utf-8")
    except OSError:
        return []
    entries: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                entries.append(obj)
        except json.JSONDecodeError:
            continue
    entries.reverse()  # 最新的在前
    if limit is not None and limit > 0:
        return entries[:limit]
    return entries


def score_trend(
    entries: list[dict[str, Any]] | None = None,
    *,
    path: Path | str | None = None,
) -> dict[str, Any]:
    """计算健康分趋势(相对上一条)."""
    if entries is None:
        entries = read_history(path=path)
    if not entries:
        return {"trend": "no_data", "current": None, "delta": 0.0, "history": []}

    current = entries[0].get("total_score")
    last_entry = next(
        (e for e in entries[1:] if e.get("total_score") is not None),
        None,
    )
    if current is None:
        current = 0.0
    last_score = (
        last_entry.get("total_score", current) if last_entry is not None else current
    )
    try:
        delta = float(current) - float(last_score)
    except (TypeError, ValueError):
        delta = 0.0

    if delta > 0.05:
        trend = "up"
    elif delta < -0.05:
        trend = "down"
    else:
        trend = "stable"

    return {
        "trend": trend,
        "current": current,
        "delta": round(delta, 2),
        "history": [
            {"date": e.get("date", "?"), "score": float(e.get("total_score") or 0.0)}
            for e in entries[:30]
        ],
    }


def render_trend_chart(
    entries: list[dict[str, Any]] | None = None,
    *,
    path: Path | str | None = None,
    width: int = 40,
) -> str:
    """生成 ASCII 趋势图(最近 30 条)."""
    trend = score_trend(entries, path=path)
    history = trend["history"]
    if not history:
        return "_无历史数据_"

    delta_str = f"{trend['delta']:+.2f}"
    lines = [
        f"**趋势**: {trend['trend']} (当前 {trend['current']}, 变化 {delta_str})",
        "",
    ]
    max_score = 100.0
    for h in reversed(history):
        score = float(h.get("score") or 0.0)
        ratio = max(0.0, min(1.0, score / max_score))
        bar_len = int(ratio * width)
        bar = "#" * bar_len + "-" * (width - bar_len)
        lines.append(f"`{h['date']}` {bar} {score:.1f}")
    return "\n".join(lines)


__all__ = (
    "DEFAULT_PATH",
    "append_entry",
    "read_history",
    "render_trend_chart",
    "score_trend",
)
