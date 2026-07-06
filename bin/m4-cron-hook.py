#!/usr/bin/env python3
"""m4-cron-hook.py — OMO cron 集成 (Round 4d, ADR-0144)

目的: 把 M4 Health Score (ADR-0140) 接入 OMO operating-rhythm cron 框架。
OMO daily / weekly cron 任务可调用此 hook, 把 m4-health.json 解析为
OMO 易读格式, 写到 .omo/_derived/m4-cron-log.json (gitignored).

对 OMO framework 的影响:
- 不动 .omo/cron/ 任何现有脚本
- 不动 OMO .truth/registry/* YAML
- 不增加 OMO state bus events (硬不违反 P74)

对 OMO framework 的好处:
- OMO daily cron (09:00) 可拿到 m4-health snapshot, 嵌入 daily report
- OMO weekly cron (周一 10:00) 可对比 m4 score 趋势
- P74 governance radar history 可读 m4-cron-log.json (派生面)

用法:
    uv run --with pyyaml python bin/m4-cron-hook.py
    uv run --with pyyaml python bin/m4-cron-hook.py --sync # 写 .omo/_derived/m4-cron-log.json
    uv run --with pyyaml python bin/m4-cron-hook.py --trigger cron # 受 OMO cron 调
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WS = Path(__file__).resolve().parents[1]
DERIVED_HEALTH = WS / "projects/ecos/.omo/_derived/m4-health.json"
DERIVED_LOG = WS / ".omo/_derived/m4-cron-log.json"
GI_LOG = ".omo/_derived/"  # 已 gitignored in main tree (.gitignore 中 ADR-0137 后保留)

OMOCRON_HOOK_MARK = "M4_HOOK_MARK"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_health() -> dict | None:
    if not DERIVED_HEALTH.exists():
        return None
    try:
        return json.loads(DERIVED_HEALTH.read_text())
    except Exception:
        return None


def _existed_log() -> list[dict]:
    if not DERIVED_LOG.exists():
        return []
    try:
        return json.loads(DERIVED_LOG.read_text())
    except Exception:
        return []


def _write_log(entries: list[dict]) -> None:
    DERIVED_LOG.parent.mkdir(parents=True, exist_ok=True)
    DERIVED_LOG.write_text(json.dumps(entries, ensure_ascii=False, indent=2))


def _detect_trigger(args_trigger: str) -> str:
    """判断本次调用的 trigger 源 (手动/cron/test)"""
    if args_trigger:
        return args_trigger
    if os.getenv("OPC_TRIGGER"):
        return "cron"
    return "manual"


def run_hook(sync: bool = True, trigger: str = "") -> dict:
    """执行 hook 主体, 返回单条 entry dict"""
    health = _load_health()
    health_ok = health is not None
    health_score = health.get("overall_score", 0) if health else 0
    health_branch = health.get("branch", "?") if health else "?"
    health_sha = health.get("git_sha", "")[:8] if health else ""
    trigger_src = _detect_trigger(trigger)

    entry = {
        "mark": OMOCRON_HOOK_MARK,
        "ts": _now(),
        "trigger": trigger_src,
        "branch": health_branch,
        "sha": health_sha,
        "health_score": health_score,
        "health_loaded": health_ok,
        "metrics": health.get("metrics", {}) if health else {},
    }

    if sync:
        log = _existed_log()
        log.append(entry)
        # 保留最近 90 条 (3 个月 daily cron)
        log = log[-90:]
        _write_log(log)

    return entry


def format_for_omo(entry: dict) -> str:
    """输出 OMO 易读的单行 summary (governance-evolution format)"""
    score = entry["health_score"]
    trigger = entry["trigger"]
    return f"[M4-Health] branch={entry['branch']} score={score:.2f} trigger={trigger} ts={entry['ts']}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sync", action="store_true",
                        help="写 .omo/_derived/m4-cron-log.json (默认开)")
    parser.add_argument("--trigger", default="",
                        help="触发源 (manual/cron/test), 缺省从 $OPC_TRIGGER 推断")
    args = parser.parse_args()

    entry = run_hook(sync=args.sync, trigger=args.trigger)

    # OMO line-format 输出 (单一字符串, OMO 监控易 grep)
    print(format_for_omo(entry))

    # JSON 输出 (调试)
    if os.getenv("M4_HOOK_JSON"):
        print(json.dumps(entry, ensure_ascii=False, default=str))

    if not entry["health_loaded"]:
        print("# (警告: m4-health.json 不存在, hook 仅记录空 entry)",
              file=sys.stderr)
        # 不返回 1 (避免破坏 OMO cron 链)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
