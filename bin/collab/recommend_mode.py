#!/usr/bin/env python3
"""P84 协作模式推荐 CLI — ADR-0253/0255 路由表可执行面.

Usage:
  python3 bin/collab/recommend_mode.py --task-type independent_batch
  python3 bin/collab/recommend_mode.py --describe "6 文件 as_of 无共享写"

Exit 0 always (advisory). JSON on --json.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 路由表 (SSOT 叙述: .omo/standards/collab-mode-routing.md · ADR-0253/0255)
RULES: list[tuple[str, str, str]] = [
    (
        "independent_batch",
        "collab_parallel",
        "独立无依赖批量 — D2 人类允许; 多 agent 墙钟未闭环 (batch5 仅微基准非真 dispatch)",
    ),
    (
        "simple_analysis",
        "single_agent",
        "简单分析/归因/串行审查 — K4 批次2 协作 1.7x 劣",
    ),
    (
        "micro_cpu",
        "single_agent",
        "细粒度 CPU/微任务 fan-out — K4 批次3/4 协作 0.3–0.7x 劣",
    ),
    (
        "conflict",
        "single_agent_then_detect",
        "冲突任务 — 先机制检测 (ADR-0254), 默认不并行 fan-out",
    ),
    (
        "failure_inject",
        "single_agent_then_detect",
        "失败注入 — 先机制检测, 并行仅当任务为重 I/O",
    ),
    (
        "dependency_chain",
        "single_agent",
        "强依赖链未验证协作收益前默认单 agent",
    ),
]

HINTS = [
    (re.compile(r"as_of|批量|parallel|独立|无共享|interface", re.I), "independent_batch"),
    (re.compile(r"归因|分析|审查|triage|分类", re.I), "simple_analysis"),
    (re.compile(r"微任务|cpu|场景库|scenario.?batch", re.I), "micro_cpu"),
    (re.compile(r"冲突|divergence|double.?claim|争抢", re.I), "conflict"),
    (re.compile(r"超时|失败|timeout|fail|注入", re.I), "failure_inject"),
    (re.compile(r"依赖|链式|A→B|pipeline", re.I), "dependency_chain"),
]


def recommend(task_type: str | None = None, describe: str | None = None) -> dict:
    tt = task_type
    if not tt and describe:
        for pat, name in HINTS:
            if pat.search(describe):
                tt = name
                break
    if not tt:
        tt = "simple_analysis"  # 保守默认
    for name, mode, reason in RULES:
        if name == tt:
            return {
                "task_type": name,
                "recommended_mode": mode,
                "reason": reason,
                "ssot": [
                    ".omo/standards/collab-mode-routing.md",
                    "ADR-0253",
                    "ADR-0255",
                ],
            }
    return {
        "task_type": tt,
        "recommended_mode": "single_agent",
        "reason": f"未知类型 {tt!r}, 保守单 agent",
        "ssot": ["ADR-0253"],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Recommend collab vs single-agent mode")
    ap.add_argument(
        "--task-type",
        choices=[r[0] for r in RULES],
        default=None,
    )
    ap.add_argument("--describe", default=None, help="自然语言任务描述, 启发式匹配")
    ap.add_argument(
        "--batch-file",
        default=None,
        help="每行一条任务描述, 批量推荐 (stdout JSONL or table)",
    )
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--list-types", action="store_true")
    args = ap.parse_args(argv)
    if args.list_types:
        for name, mode, reason in RULES:
            print(f"{name:20} -> {mode:28}  # {reason}")
        return 0
    if args.batch_file:
        path = Path(args.batch_file)
        lines = [
            ln.strip()
            for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        rows = [recommend(None, desc) | {"describe": desc} for desc in lines]
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            for r in rows:
                print(
                    f"{r['recommended_mode']:28}  type={r['task_type']:20}  "
                    f"desc={r['describe'][:60]}"
                )
        return 0
    rec = recommend(args.task_type, args.describe)
    if args.json:
        print(json.dumps(rec, ensure_ascii=False, indent=2))
    else:
        print(f"mode: {rec['recommended_mode']}")
        print(f"type: {rec['task_type']}")
        print(f"why:  {rec['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
