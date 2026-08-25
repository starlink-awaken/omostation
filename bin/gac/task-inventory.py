#!/usr/bin/env python3
"""task-inventory.py — 全谱任务台账判活审计器 (五层图谱抓手, 2026-08-25).

北极星: 治"你不知道自己有什么/什么死了" — 每任务三态判活, 一屏可见.

数据源: .omo/state/task-registry.yaml (SSOT, 扩展 P74 体系不建平行)
判活规则 (docs/operations/2026-08-25-task-landscape-five-layers.md):
  OK       载体登记 + 心跳证据新鲜
  DEAD     心跳证据 mtime 超过 max(4×周期, 30min)   ← 静默死(free_pool 的坑)
  PAPER    有配置无日志产物                          ← 纸面任务(脐带未接的坑)
  DORMANT  registry 显式 dormant_since 标注          ← 僵尸休眠(Hermes 的坑)
  GONE     载体(launchd/cron)中登记消失              ← 配置漂移

输出: 单行 JSON; exit 0=全绿, 1=存在失活项 (meta-doctor 同契约)
--pretty: 人读一屏表. 依赖 pyyaml (cron 行用 uv run --with pyyaml, 有先例).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[2]
REGISTRY = WORKSPACE / ".omo" / "state" / "task-registry.yaml"

FREQ_SECONDS = {
    "1min": 60, "2min": 120, "5min": 300, "30min": 1800,
    "hourly": 3600, "daily": 86400, "weekly": 604800,
}
# 心跳证据判定缓冲: 低频任务(日/周)放宽到 2× 周期再报 DEAD,
# 高频任务(分钟级)至少给 30min 容忍一次性抖动.
def _stale_after(freq: str) -> float:
    sec = FREQ_SECONDS.get(freq)
    if sec is None:
        return 0.0  # resident/event: 不按 mtime 判
    return max(4 * sec, 1800.0) if sec <= 3600 else 2 * sec


def _launchd_labels() -> set[str]:
    try:
        out = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=15).stdout
    except Exception:
        return set()
    labels: set[str] = set()
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 3:
            labels.add(parts[2])
    return labels


def _crontab_text() -> str:
    try:
        return subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return ""


def _carrier_registered(task: dict[str, Any], labels: set[str], cron_text: str) -> tuple[bool, str]:
    carrier = task.get("carrier", "")
    ref = task.get("ref", "")
    if carrier == "launchd":
        # GUI app 类 label 每次安装带 .数字后缀(如 application.app.omlx.240707221), 前缀匹配
        hit = ref in labels or any(l.startswith(ref + ".") for l in labels)
        return (hit, f"launchd:{ref}")
    if carrier == "cron":
        return (ref in cron_text, f"cron:{ref}")
    return (True, f"{carrier}:{ref}")  # resident/hook/mcp: 载体登记不适用


def judge(task: dict[str, Any], labels: set[str], cron_text: str, now: float) -> dict[str, str]:
    tid = task.get("id", "?")
    registered, carrier_desc = _carrier_registered(task, labels, cron_text)

    if not registered:
        return {"id": tid, "status": "GONE", "detail": f"载体未登记 {carrier_desc}"}
    if task.get("dormant_since"):
        return {"id": tid, "status": "DORMANT",
                "detail": f"休眠自 {task['dormant_since']} — 待人工裁决(退役/复活)"}

    ev = task.get("evidence")
    if not ev:
        return {"id": tid, "status": "OK", "detail": f"载体在册(无证据路径, 仅登记检查) {carrier_desc}"}
    p = Path(ev).expanduser()
    if not p.exists():
        return {"id": tid, "status": "PAPER", "detail": f"纸面任务: 证据不存在 {p}"}
    threshold = _stale_after(task.get("freq", ""))
    if threshold <= 0:
        return {"id": tid, "status": "OK", "detail": "载体在册+证据存在(不按mtime判)"}
    age = now - p.stat().st_mtime
    if age > threshold:
        return {"id": tid, "status": "DEAD",
                "detail": f"心跳超期 {int(age/60)}min (阈值 {int(threshold/60)}min) {p.name}"}
    return {"id": tid, "status": "OK", "detail": f"载体在册+心跳新鲜({int(age/60)}min前)"}


def main() -> int:
    ap = argparse.ArgumentParser(description="全谱任务台账判活审计")
    ap.add_argument("--pretty", action="store_true", help="人读一屏表")
    ap.add_argument("--json", action="store_true", help="单行 JSON (默认)")
    args = ap.parse_args()

    try:
        import yaml
    except ImportError:
        print(json.dumps({"error": "pyyaml required: uv run --with pyyaml python bin/gac/task-inventory.py"}))
        return 2
    if not REGISTRY.exists():
        print(json.dumps({"error": f"registry missing: {REGISTRY}"}))
        return 2
    tasks = yaml.safe_load(REGISTRY.read_text()).get("tasks", [])

    labels, cron_text = _launchd_labels(), _crontab_text()
    now = time.time()
    findings = [judge(t, labels, cron_text, now) for t in tasks]

    order = {"DEAD": 0, "GONE": 1, "PAPER": 2, "DORMANT": 3, "OK": 4}
    findings.sort(key=lambda f: order.get(f["status"], 9))
    bad = [f for f in findings if f["status"] != "OK"]
    report = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(now)) + "Z",
        "total": len(findings),
        "ok": len(findings) - len(bad),
        "findings": findings,
    }
    if args.pretty:
        print(f"全谱任务台账 · 判活审计  ({report['generated']})  {report['ok']}/{report['total']} OK")
        for f in findings:
            mark = {"OK": "✅", "DEAD": "☠️ ", "PAPER": "🔧", "DORMANT": "😴", "GONE": "❌"}.get(f["status"], "?")
            print(f"  {mark} {f['status']:<8} {f['id']:<28} {f['detail']}")
    else:
        print(json.dumps(report, ensure_ascii=False))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
