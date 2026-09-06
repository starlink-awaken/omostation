#!/usr/bin/env python3
"""repo-health-metrics.py — 仓库健康度指标采集与周报生成 (BET-Y1Q4-T10-130).

采集: 分支(本地/远程)/tags/worktree 数、松散对象、悬空跟踪分支(远程已删
本地仍在)、子模块 gitlink 偏差计数。
输出: --snapshot 追加历史采样(runtime/cockpit/repo-health-history.jsonl);
      --report 生成 docs/repository-health.md 周报(当期指标 + 趋势箭头 +
      异常告警区)。

告警阈值: 松散对象 >1000 / 悬空跟踪 >5 / worktree >25 / gitlink 偏差 >3。
定时: launchd/cron 片段见文件尾注释, 由人工安装。

用法:
    python3 bin/gac/repo-health-metrics.py --snapshot --report
    python3 bin/gac/repo-health-metrics.py --json

launchd 片段 (每周日 23:30):
    <dict><key>ProgramArguments</key><array>
      <string>python3</string><string>/Users/xiamingxing/Workspace/bin/gac/repo-health-metrics.py</string>
      <string>--snapshot</string><string>--report</string>
    </array><key>StartCalendarInterval</key><dict>
      <key>Weekday</key><integer>0</integer><key>Hour</key><integer>23</integer><key>Minute</key><integer>30</integer>
    </dict></dict>
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
HISTORY_REL = "runtime/cockpit/repo-health-history.jsonl"
REPORT_REL = "docs/repository-health.md"
SCHEMA = "gac.repo_health.v1"

ALERTS = {
    "loose_objects": 1000,
    "dangling_remote_branches": 5,
    "worktrees": 25,
    "gitlink_drift": 3,
}


def _git(*args: str, timeout: int = 120) -> str:
    res = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, check=False, timeout=timeout)
    return res.stdout.strip()


def collect() -> dict[str, Any]:
    """采集当期健康度指标。"""
    local_branches = [b for b in _git("branch", "--format=%(refname:short)").splitlines() if b.strip()]
    remote_branches = [b for b in _git("branch", "-r", "--format=%(refname:short)").splitlines() if b.strip()]
    tags = [t for t in _git("tag").splitlines() if t.strip()]
    worktrees = [w for w in _git("worktree", "list").splitlines() if w.strip()]

    # 悬空跟踪: 远程已删除但本地 remote-tracking 引用仍在
    _git("fetch", "--prune", timeout=300)
    remote_live = set(_git("ls-remote", "--heads", "origin").split())
    dangling = [
        rb for rb in remote_branches
        if rb.startswith("origin/") and rb != "origin/HEAD"
        and not any(f"refs/heads/{rb.removeprefix('origin/')}" in remote_live for _ in [0])
    ]

    counts_raw = _git("count-objects", "-v")
    counts = dict(line.split(": ", 1) for line in counts_raw.splitlines() if ": " in line)

    # 子模块 gitlink 偏差
    status_out = _git("submodule", "status")
    drift = sum(1 for line in status_out.splitlines() if line[:1] == "+")

    return {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "local_branches": len(local_branches),
        "remote_branches": len(remote_branches),
        "tags": len(tags),
        "worktrees": len(worktrees),
        "loose_objects": int(counts.get("count", 0)),
        "in_pack": int(counts.get("in-pack", 0)),
        "dangling_remote_branches": len(dangling),
        "dangling_names": dangling[:10],
        "gitlink_drift": drift,
    }


def _trend(current: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, str]:
    """逐指标趋势箭头: ↑ 恶化(数值升) / ↓ 改善 / → 持平。"""
    if not previous:
        return {}
    out = {}
    for k in ALERTS:
        c, p = current.get(k, 0), previous.get(k, 0)
        out[k] = "→" if c == p else ("↑" if c > p else "↓")
    return out


def _alerts(current: dict[str, Any]) -> list[str]:
    alerts = []
    for metric, threshold in ALERTS.items():
        v = current.get(metric, 0)
        if v > threshold:
            alerts.append(f"{metric}={v} > 阈值 {threshold}")
    return alerts


def _load_previous(history_path: Path) -> dict[str, Any] | None:
    if not history_path.exists():
        return None
    lines = [l for l in history_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines:
        return None
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError:
        return None


def render_report(current: dict[str, Any], previous: dict[str, Any] | None) -> str:
    trend = _trend(current, previous)
    alerts = _alerts(current)
    dim_labels = {
        "local_branches": "本地分支", "remote_branches": "远程分支", "tags": "Tags",
        "worktrees": "Worktrees", "loose_objects": "松散对象", "in_pack": "打包对象",
        "dangling_remote_branches": "悬空跟踪分支", "gitlink_drift": "Gitlink 偏差",
    }
    lines = [
        "# 仓库健康度周报",
        "",
        f"> 采样时间: {current['ts']} | 生成器: `bin/gac/repo-health-metrics.py` (BET-Y1Q4-T10-130)",
        "",
        "## 当期指标",
        "",
        "| 指标 | 数值 | 趋势 |",
        "|------|------|------|",
    ]
    for k in list(ALERTS) + ["local_branches", "remote_branches", "tags", "in_pack"]:
        label = dim_labels.get(k, k)
        t = trend.get(k, "→") if previous else "—"
        lines.append(f"| {label} | {current.get(k, 0)} | {t} |")
    lines.extend(["", "## 告警", ""])
    if alerts:
        for a in alerts:
            lines.append(f"- ⚠️ {a}")
    else:
        lines.append("- ✅ 所有指标处于阈值内")
    if previous:
        lines.extend([
            "",
            "## 趋势对比基线",
            "",
            f"上次采样: {previous.get('ts', 'n/a')}",
        ])
    lines.append("")
    return "\n".join(lines)


def snapshot(current: dict[str, Any], history_path: Path) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(current, ensure_ascii=False) + "\n")


def main() -> int:
    p = argparse.ArgumentParser(description="仓库健康度指标采集与周报 (BET-Y1Q4-T10-130)")
    p.add_argument("--snapshot", action="store_true", help="追加历史采样")
    p.add_argument("--report", action="store_true", help="生成 docs/repository-health.md")
    p.add_argument("--json", action="store_true", help="采集结果 JSON")
    args = p.parse_args()

    current = collect()
    history_path = REPO / HISTORY_REL
    previous = _load_previous(history_path)

    if args.snapshot:
        snapshot(current, history_path)

    if args.report:
        report = render_report(current, previous)
        report_path = REPO / REPORT_REL
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8")

    if args.json:
        print(json.dumps({"schema": SCHEMA, "current": current, "has_previous": previous is not None}, ensure_ascii=False, indent=2))
    elif not args.snapshot and not args.report:
        alerts = _alerts(current)
        icon = "⚠️ " if alerts else "✅"
        print(f"{icon} 仓库健康度: 分支 {current['local_branches']}/{current['remote_branches']}, worktrees {current['worktrees']}, "
              f"松散对象 {current['loose_objects']}, 悬空跟踪 {current['dangling_remote_branches']}, gitlink 偏差 {current['gitlink_drift']}")
        for a in alerts:
            print(f"  ⚠️ {a}")

    if args.snapshot or args.report:
        done = []
        if args.snapshot:
            done.append("采样已追加")
        if args.report:
            done.append(f"周报已生成 {REPORT_REL}")
        print(" | ".join(done))
    return 0


if __name__ == "__main__":
    sys.exit(main())
