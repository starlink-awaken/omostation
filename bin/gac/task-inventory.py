#!/usr/bin/env python3
"""task-inventory.py — TLM 任务生命周期审计器 (2026-08-25, M1)

背景: 2026-08-25 审计暴露四类无检测的事故 — 纸面任务(cron 因日志目录不存在
从未执行)、不知情运行(mail-daemon 30s 调大模型)、休眠无感知(Hermes 死 3 月)、
僵尸资源(pg/neo4j)。本审计器是 TLM 体系的执行面: 采集全谱任务载体, 对照
.omo/state/task-registry.yaml 台账判活, 产出四分级快照与漂移事件。

四分级:
  HEALTHY  证据 mtime <= 3 x expected_period
  PAPER    载体有配置但证据产物不存在 (纸面/脐带未接)
  DORMANT  证据存在但严重过期
  DRIFT    载体存在但台账未登记 (不知情任务)

用法: uv run --with pyyaml python bin/gac/task-inventory.py [--json] [--quiet]
退出码: DRIFT>0 或 DORMANT>0 时为 1 (供 governance-scanner 消费)。
"""

from __future__ import annotations

import json
import os
import plistlib
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

WORKSPACE = Path(os.environ.get("WORKSPACE_ROOT", Path(__file__).resolve().parents[2]))
REGISTRY = WORKSPACE / ".omo" / "state" / "task-registry.yaml"
SNAP_DIR = WORKSPACE / "runtime" / "task-inventory" / "snapshots"
DRIFTS = WORKSPACE / "runtime" / "task-inventory" / "drifts.jsonl"

STALE_FACTOR = 3

# 第三方/系统原生的载体白名单: 不登记也不报 DRIFT (纯环境件, 非自有任务资产)
DRIFT_IGNORE = {
    "com.google.GoogleUpdater.wake.system",
    "com.macpaw.CleanMyMac5.Agent",
    "com.macpaw.CleanMyMac5.Updater",
    "com.west2online.ClashX.ProxyConfigHelper",
    "com.docker.socket",
    "com.docker.vmnetd",
    "lm studio",  # 登录项名(已有 registry: lmstudio-server)
    "application.",
}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_registry() -> list[dict]:
    import yaml

    try:
        doc = yaml.safe_load(REGISTRY.read_text())
        return doc.get("tasks", []) if doc else []
    except Exception as exc:
        print(f"registry 加载失败: {exc}", file=sys.stderr)
        return []


def collect_carriers() -> set[str]:
    """采集全谱任务载体标识(cron 行特征 + plist label + 登录项 + brew 服务)。"""
    refs: set[str] = set()
    # cron: 以脚本名或核心参数为锚
    try:
        cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10).stdout
        for line in cron.splitlines():
            if line.strip() and not line.startswith("#"):
                # 取命令部分的关键脚本名
                for part in line.split():
                    if part.endswith((".py", ".sh")):
                        refs.add(f"cron:{Path(part).stem}")
    except Exception:
        pass
    # launchd: 用户级 + 系统级 label
    for d in (Path.home() / "Library" / "LaunchAgents", Path("/Library/LaunchDaemons")):
        for f in d.glob("*.plist"):
            try:
                pl = plistlib.loads(f.read_bytes())
                refs.add(pl.get("Label", f.stem))
            except Exception:
                refs.add(f.stem)
    # 登录项
    try:
        out = subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to get the name of every login item'],
            capture_output=True, text=True, timeout=15,
        ).stdout.strip()
        for name in out.split(","):
            if name.strip():
                refs.add(name.strip())
    except Exception:
        pass
    return refs


def classify(task: dict) -> tuple[str, str]:
    """单任务判活: 返回 (状态, 说明)。expected_period=0 视为无法判活(active 免检)。"""
    if task.get("lifecycle") in ("proposed", "retired", "archived"):
        return task["lifecycle"], "台账豁免"
    period = int(task.get("expected_period") or 0)
    evidence = task.get("evidence") or []
    if period == 0 or not evidence:
        return "HEALTHY" if task.get("lifecycle") == "active" else task.get("lifecycle", "unknown"), "免检(无周期或无证据定义)"
    best_age: float | None = None
    for ev in evidence:
        p = Path(os.path.expanduser(ev.get("path", "")))
        if not p.exists():
            continue
        try:
            age = time.time() - p.stat().st_mtime
        except OSError:
            continue
        if best_age is None or age < best_age:
            best_age = age
    if best_age is None:
        return "PAPER", "有配置但证据产物不存在(纸面/脐带未接)"
    if best_age > STALE_FACTOR * period:
        days = best_age / 86400
        return "DORMANT", f"证据过期 {days:.0f} 天 (阈值 {STALE_FACTOR * period / 86400:.1f} 天)"
    return "HEALTHY", f"证据 {best_age / 60:.0f}min 前"


def main() -> int:
    args = sys.argv[1:]
    as_json = "--json" in args
    quiet = "--quiet" in args
    tasks = load_registry()
    if not tasks:
        print("FATAL: 台账为空或不可读", file=sys.stderr)
        return 2

    results = []
    for t in tasks:
        status, note = classify(t)
        results.append({"id": t["id"], "system": t.get("system"), "status": status, "note": note,
                        "carrier_ref": t.get("carrier_ref"), "lifecycle": t.get("lifecycle")})

    # DRIFT: 载体有但台账无(按 label/名字粗匹配)
    carriers = collect_carriers()
    known_refs = {t.get("carrier_ref", "") for t in tasks}
    known_stems = set()
    for r in known_refs:
        known_stems.add(str(r).split(":")[-1].split("/")[-1].lower())
    drifts = []
    for c in carriers:
        c_l = c.split(":")[-1].lower()
        if c_l in known_stems or c in DRIFT_IGNORE or c_l in DRIFT_IGNORE:
            continue
        # 苹果原生服务免报
        if c.startswith("com.apple."):
            continue
        drifts.append(c)
    for d in sorted(drifts):
        results.append({"id": f"drift:{d}", "system": "?", "status": "DRIFT", "note": "载体存在但台账未登记",
                        "carrier_ref": d, "lifecycle": "?"})

    # 汇总
    counts: dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    if as_json:
        SNAP_DIR.mkdir(parents=True, exist_ok=True)
        snap = {"ts": _now(), "counts": counts, "results": results}
        path = SNAP_DIR / f"{datetime.now().strftime('%Y%m%d-%H%M')}.json"
        path.write_text(json.dumps(snap, ensure_ascii=False, indent=1))
        DRIFTS.parent.mkdir(parents=True, exist_ok=True)
        with DRIFTS.open("a") as f:
            f.write(json.dumps({"event": "task_inventory", "ts": _now(), "counts": counts,
                                "drifts": drifts}, ensure_ascii=False) + "\n")
        if not quiet:
            print(json.dumps({"snapshot": str(path), "counts": counts, "drifts": drifts}, ensure_ascii=False, indent=1))
    elif not quiet:
        print(f"=== TLM 任务台账审计 {_now()} | 台账 {len(tasks)} 项 ===")
        order = ["HEALTHY", "PAPER", "DORMANT", "DRIFT", "proposed", "degraded"]
        for st in order:
            rows = [r for r in results if r["status"] == st]
            if not rows:
                continue
            print(f"\n[{st}] x{len(rows)}")
            for r in rows[:15]:
                print(f"  {r['id']:32s} {str(r.get('system')):11s} {r['note']}")

    bad = counts.get("DORMANT", 0) + counts.get("DRIFT", 0)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
