#!/usr/bin/env python3
"""CR-RESIDENT-STATUS-01: resident daemon 水位活性 CI 校验.

resident 体系以 daemon byte_offset 水位判断活性 (cron --once 下无常驻进程,
进程退出属正常, 以水位文件 mtime 新鲜度为准). 与 omo resident status
(projects/omo/src/omo/resident/status.py) 共享同一阈值 STALE_THRESHOLD_SECONDS=1800.

rule: resident.daemon.tick_age_seconds <= 1800 or resident.never_ticked == true
- 无任何水位文件 → never_ticked=true (从未调度, 豁免阻塞, 报告为 advisory)
- 最旧水位 (min mtime) 年龄 > 30min → FAIL (degraded)
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WATERMARKS = REPO / ".omo" / "_delivery" / "resident-orchestrator" / "watermarks"
STALE_THRESHOLD_SECONDS = 1800  # 30min, 与 status.py 对齐


def _load_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def check_daemon_watermark() -> tuple[bool, str]:
    """CR-RESIDENT-STATUS-01: daemon 水位新鲜度 ≤30min 或从未 tick.

    daemon 水位 = 五类角色水位 (resident-{role}.json, 由 daemon --once --role 每 2min 推进).
    排除订阅层 resident-sub.json (subscribe 非 cron --once 触发的 daemon tick 证据,
    若混入会让健康体系被陈旧 sub 水位误判 degraded).
    """
    if not WATERMARKS.is_dir():
        return True, "watermarks dir absent (daemon never configured), never_ticked=true"
    files = sorted(
        p for p in WATERMARKS.glob("resident-*.json") if p.name != "resident-sub.json"
    )
    if not files:
        return True, "no role watermark (daemon never ticked), never_ticked=true"
    oldest = min(files, key=lambda p: p.stat().st_mtime)
    age = time.time() - oldest.stat().st_mtime
    wm = _load_json(oldest)
    byte_offset = int(wm.get("byte_offset", 0)) if wm else None
    detail = (
        f"last daemon tick {age:.0f}s ago (stale >{STALE_THRESHOLD_SECONDS}s), "
        f"watermark={oldest.name} byte_offset={byte_offset}"
    )
    if age > STALE_THRESHOLD_SECONDS:
        return False, f"{detail} → degraded"
    return True, detail


def main() -> int:
    print("── CR-RESIDENT-STATUS-01: resident daemon 水位活性 ──")
    passed, detail = check_daemon_watermark()
    icon = "OK" if passed else "FAIL"
    print(f"  [{icon}] {detail}")
    print()
    if passed:
        print("CR-RESIDENT-STATUS-01 PASS")
        return 0
    print("CR-RESIDENT-STATUS-01 FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
