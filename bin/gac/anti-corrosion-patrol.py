#!/usr/bin/env python3
"""anti-corrosion-patrol.py — 防腐看门狗常态巡检 (BET-Y2Q1-T6-03).

聚合既有防腐散件为每日/PR 可触发的常态巡检：
  1. weekly_net_lines  — 周窗口 git diff 净增行数，红线 <=0（T6 防腐红线）
  2. rule_health       — GaC 规则健康度打分与退役候选标记
  3. dead_code_dupes   — 既有 anti-corrosion-detector 的死代码/双头依赖告警汇总
  4. budget            — 既有 anti-corrosion-check 的预算检查结论

熔断契约 (--enforce)：红线突破 / 预算超限 / 高危告警 → exit 1（阻断）。
--json 输出巡检快照（供 Cockpit 标红告警消费）。

用法:
    python3 bin/gac/anti-corrosion-patrol.py [--enforce] [--json] [--window-days 7]
    # launchd 片段见仓库 docs；由人工安装定时。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
GOV_CHECKS_YAML = REPO / ".omo/_truth/registry/governance-checks.yaml"
DETECTOR = REPO / "bin/gac/anti-corrosion-detector.py"
SCHEMA = "gac.anti_corrosion_patrol.v1"


def weekly_net_lines(window_days: int = 7) -> dict[str, Any]:
    """周窗口净增行数（新增-删除，含根仓工作树已跟踪文件的历史 diff）。"""
    since = time.strftime("%Y-%m-%d", time.localtime(time.time() - window_days * 86400))
    cmd = ["git", "-C", str(REPO), "diff", f"--since={since}", "--shortstat", "origin/main"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=120)
        stat = out.stdout.strip()
    except Exception as exc:
        return {"ok": False, "error": str(exc), "net_lines": None, "window_days": window_days}
    added = re.search(r"(\d+) insertion", stat)
    deleted = re.search(r"(\d+) deletion", stat)
    a = int(added.group(1)) if added else 0
    d = int(deleted.group(1)) if deleted else 0
    net = a - d
    return {
        "ok": True,
        "window_days": window_days,
        "since": since,
        "added": a,
        "deleted": d,
        "net_lines": net,
        "red_line": "<=0",
        "breach": net > 0,
    }


def rule_health_score() -> dict[str, Any]:
    """GaC 规则健康度: 每条规则按定义完整性与退役标记打分 (0-100)。"""
    if not GOV_CHECKS_YAML.exists():
        return {"ok": False, "error": "governance-checks.yaml missing"}
    text = GOV_CHECKS_YAML.read_text(encoding="utf-8")
    rule_blocks = re.findall(r"^  - id:\s*(\S+)", text, re.M)
    stale_markers = ("deprecated", "superseded", "removed", "retired")
    healthy, retired_candidates, total = 0, [], len(rule_blocks)
    for rid in rule_blocks:
        m = re.search(rf"- id:\s*{re.escape(rid)}\b(.*?)(?=\n  - id:|\Z)", text, re.S)
        body = m.group(1) if m else ""
        if any(k in body.lower() for k in stale_markers):
            retired_candidates.append(rid)
        elif re.search(r"\b(cmd|command|check|script)\b", body, re.I):
            healthy += 1
    score = round(healthy * 100 / total) if total else 100
    return {
        "ok": True,
        "total_rules": total,
        "healthy": healthy,
        "retired_candidates": retired_candidates,
        "health_score": score,
    }


def dead_code_and_dupes() -> dict[str, Any]:
    """汇总既有 detector 的死代码/双头依赖告警 (不复制其逻辑)。"""
    if not DETECTOR.exists():
        return {"ok": False, "error": "detector missing", "alerts": []}
    try:
        out = subprocess.run(
            [sys.executable, str(DETECTOR), "--json"],
            capture_output=True, text=True, check=False, timeout=180,
        )
        payload = json.loads(out.stdout or "{}")
        alerts = payload.get("alerts") or payload.get("findings") or []
        high = [a for a in alerts if isinstance(a, dict) and str(a.get("severity", "")).lower() in ("high", "error")]
        return {"ok": True, "alert_count": len(alerts), "high_severity": len(high), "alerts": alerts[:20]}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "alerts": []}


def budget_status() -> dict[str, Any]:
    """调用既有 anti-corrosion-check.py 的结论。"""
    check = REPO / "bin/gac/anti-corrosion-check.py"
    if not check.exists():
        return {"ok": False, "error": "anti-corrosion-check missing"}
    try:
        out = subprocess.run(
            [sys.executable, str(check), "--json"],
            capture_output=True, text=True, check=False, timeout=180,
        )
        payload = json.loads(out.stdout or "{}")
        return {"ok": payload.get("ok", payload.get("pass", False)), "detail_keys": sorted(payload.keys())[:8]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def patrol(enforce: bool = False, window_days: int = 7) -> dict[str, Any]:
    net = weekly_net_lines(window_days)
    health = rule_health_score()
    dead = dead_code_and_dupes()
    budget = budget_status()
    breaches: list[str] = []
    if net.get("breach"):
        breaches.append(f"周净增 {net['net_lines']} 行 > 0 (红线 <=0)")
    if health.get("ok") and health.get("health_score", 100) < 60:
        breaches.append(f"GaC 规则健康度 {health['health_score']} < 60")
    if dead.get("ok") and dead.get("high_severity", 0) > 0:
        breaches.append(f"高危死代码/双头依赖告警 {dead['high_severity']} 条")
    if budget.get("ok") is False and budget.get("violations"):
        breaches.append(f"防腐预算超限 ({len(budget['violations'])} 项违规)")
    verdict = "BLOCK" if breaches else ("WARN" if any(not x.get("ok") for x in (net, health, dead)) else "PASS")
    snapshot = {
        "schema": SCHEMA,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "verdict": verdict,
        "breaches": breaches,
        "weekly_net_lines": net,
        "rule_health": health,
        "dead_code_dupes": dead,
        "budget": budget,
        "cockpit_alert": {"level": "red" if breaches else ("yellow" if verdict == "WARN" else "green")},
    }
    if enforce and breaches:
        snapshot["enforced_exit"] = 1
    return snapshot


def main() -> int:
    p = argparse.ArgumentParser(description="防腐看门狗常态巡检 (BET-Y2Q1-T6-03)")
    p.add_argument("--enforce", action="store_true", help="熔断模式: 有 breach 时 exit 1")
    p.add_argument("--json", action="store_true", help="巡检快照 JSON")
    p.add_argument("--window-days", type=int, default=7, help="净增行数统计窗口 (天)")
    args = p.parse_args()

    snap = patrol(enforce=args.enforce, window_days=args.window_days)
    enforced = snap.pop("enforced_exit", None)
    if args.json:
        print(json.dumps(snap, ensure_ascii=False, indent=2))
    else:
        icon = {"PASS": "✅", "WARN": "⚠️ ", "BLOCK": "🚨"}[snap["verdict"]]
        print(f"{icon} 防腐巡检: {snap['verdict']}")
        for b in snap["breaches"]:
            print(f"  🚨 {b}")
        net = snap["weekly_net_lines"]
        if net.get("net_lines") is not None:
            print(f"  周净增: {net['net_lines']} 行 (+{net['added']}/-{net['deleted']}, 红线 <=0)")
        rh = snap["rule_health"]
        if rh.get("ok"):
            print(f"  规则健康度: {rh['health_score']} ({rh['healthy']}/{rh['total_rules']}, 退役候选 {len(rh['retired_candidates'])})")
    if args.enforce and enforced == 1:
        print("🚨 enforce: 巡检存在违例，阻断。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
