#!/usr/bin/env python3
"""任务树一致性 — `planned/` 不得含已在 `closed/` 或 `done/` 的 id.

2026-09-19 实证:
  `.omo/tasks/planned/` 有 8 项, 其中 3 项在终态树里已有同 id 副本:
    cockpit-debt-debt-1   → closed/closed-cockpit-debt-debt-1.yaml  (closed 2026-07-28)
    event-loop-dead-loop  → closed/closed-event-loop-dead-loop.yaml
    BET-Y1Q4-T15          → done/BET-Y1Q4-T15-import-perf-regression.yaml

  它们污染 `planned` 计数与 `owner` 分布 —— 健康面据此报出
  "Owner 集中度: human 持有 90% 待处理任务" 的异常, 而其中 3/8 是**已关闭的
  陈旧重复**。

另注 (本工具不判定, 仅提示): 本仓台账 `docs/plans/3y-bet-ledger.yaml` 的 426 个
bet **全部 status=done**, 而 planned/ 里多项 id **不在台账** —— 即它们与台账脱钩。
那属"孤项"问题 (见 debt item DEBT-20260917021531 的相邻议题), 需 owner 决策;
本工具只查**确定无疑**的那一类: 同 id 已在终态树。

用法:
    python3 bin/gac/check-task-tree-consistency.py [--json]
退出码: 0 = 一致; 1 = 存在陈旧重复
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[2]
TASKS = _ROOT / ".omo" / "tasks"
PLANNED = TASKS / "planned"
TERMINAL_DIRS = ("closed", "done", "archived")


def _ids(directory: Path) -> dict[str, str]:
    """id → 文件名."""
    out: dict[str, str] = {}
    if not directory.is_dir():
        return out
    for path in sorted(directory.rglob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if isinstance(data, dict) and data.get("id"):
            out[str(data["id"])] = path.name
    return out


def scan(root: Path | None = None) -> dict:
    base = (root or _ROOT) / ".omo" / "tasks"
    planned = _ids(base / "planned")
    terminal: dict[str, str] = {}
    for name in TERMINAL_DIRS:
        for tid, fname in _ids(base / name).items():
            terminal.setdefault(tid, f"{name}/{fname}")

    stale = [{"id": tid, "planned_file": fname, "terminal_copy": terminal[tid]}
             for tid, fname in sorted(planned.items()) if tid in terminal]
    return {"planned_count": len(planned), "terminal_count": len(terminal),
            "stale": stale}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    r = scan()
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))

    if not r["stale"]:
        if not args.json:
            print(f"✅ 任务树一致: planned {r['planned_count']} 项, "
                  f"无已关闭/完成的重复")
        return 0

    if not args.json:
        print(f"🔴 planned/ 含 {len(r['stale'])} 项陈旧重复 "
              f"(同 id 已在终态树) —— 会污染 planned 计数与 owner 分布:",
              file=sys.stderr)
        for s in r["stale"]:
            print(f"   {s['planned_file']}  ← 终态副本: {s['terminal_copy']}",
                  file=sys.stderr)
        print("   处置: 终态副本已保留该记录, 从 planned/ 移除即可 "
              "(`git rm .omo/tasks/planned/<file>`)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
