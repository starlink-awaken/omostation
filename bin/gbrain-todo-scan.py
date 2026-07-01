#!/usr/bin/env python3
"""gbrain-todo-scan: 扫描 gbrain 代码 TODO 注释, 分类报告 (ISC-36 重定义).

治本 B1 (ISC-36 重定义): gbrain 无 TODOS.md 文件 (第10次实证修正 — find 空),
81 TODO 是代码注释 (// TODO(v0.35.5), // v0.37+ TODO, // follow-up TODO 等).
本扫描器分类 TODO, 让孤岛 TODO 可见 (未来可 ingress 进 omo debt registry).

分类:
  - version_bound:   TODO(vX.Y) / v0.x TODO — 版本绑定待办
  - deferred_shipped: deferred/shipped/fix wave — 历史已处理
  - follow_up:       follow-up TODO — 后续待办
  - pending_host:    pending-host-work — 迁移脚本 emit 的待办
  - generic:         其余 TODO

用法:
  python bin/gbrain-todo-scan.py
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
GBRAIN_SRC = WORKSPACE / "projects" / "gbrain" / "src"

# 注意顺序: 更具体的 pattern 先匹配
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("deferred_shipped", re.compile(r"deferred\s+TODO|shipped|fix\s+wave", re.IGNORECASE)),
    ("version_bound", re.compile(r"TODO\s*\(?\s*v?\d+\.\d+|v\d+\.\d+.*TODO", re.IGNORECASE)),
    ("follow_up", re.compile(r"follow.?up\s+TODO", re.IGNORECASE)),
    ("pending_host", re.compile(r"pending.?host.?work", re.IGNORECASE)),
    ("generic", re.compile(r"\bTODO\b")),
]


def scan() -> tuple[Counter, dict[str, list[str]]]:
    by_cat: Counter = Counter()
    samples: dict[str, list[str]] = {}
    if not GBRAIN_SRC.is_dir():
        return by_cat, samples
    for f in sorted(GBRAIN_SRC.rglob("*")):
        if f.suffix not in {".ts", ".tsx", ".js", ".jsx"}:
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for cat, pat in PATTERNS:
                if pat.search(line):
                    # generic 只在无更具体分类时计入
                    if cat == "generic":
                        if any(p.search(line) for _, p in PATTERNS[:-1]):
                            continue
                    by_cat[cat] += 1
                    if len(samples.setdefault(cat, [])) < 3:
                        rel = f.relative_to(WORKSPACE)
                        samples[cat].append(f"{rel}:{lineno} {line.strip()[:80]}")
                    break
    return by_cat, samples


def main() -> int:
    by_cat, samples = scan()
    total = sum(by_cat.values())
    real_pending = total - by_cat.get("deferred_shipped", 0)

    print(f"📊 gbrain TODO 扫描: {total} 个 (真实待办 ~{real_pending}, 含 {by_cat.get('deferred_shipped', 0)} 历史)")
    print()
    for cat, n in by_cat.most_common():
        print(f"  {cat:<18} {n}")
        for s in samples.get(cat, [])[:2]:
            print(f"    - {s}")
    print()
    print(f"治本: version_bound + follow_up + pending_host 是真实待办 (可 ingress 进 omo debt registry); deferred_shipped 是历史记录")
    return 0


if __name__ == "__main__":
    sys.exit(main())
