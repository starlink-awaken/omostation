#!/usr/bin/env python3
"""event-loop-lint — 闭环回路检测 (健康治理理想态原则4).

emit 必有消费者 (emit → consume → 触达 → 决策 任一段断都失效).
扫 omo-events.jsonl 的 emit kind, 检查每个 kind 在代码里有没消费者
(grep kind 字符串, 排除 emit 端/生成器/test/文档). 无消费者的 kind = 死回路.

治 state_stale 671 条零消费 (九轮诊断: emit 了没人看, 假告警回路).

用法:
  python3 bin/gac/event-loop-lint.py           # 检测死回路, 有则返回 1
  python3 bin/gac/event-loop-lint.py --json    # JSON 输出 (gac-healthcheck 消费)

退出码: 0 = 全 emit 有消费者, 1 = 有死回路
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
EVENTS = WORKSPACE / ".omo" / "_knowledge" / "omo-events.jsonl"

# emit 端/生成器/测试/文档排除 (这些不是消费者)
EXCLUDE_RE = re.compile(
    r"(state-stale-emit|emit|install-watch|gen-tools-index|gen-|/_test|/test_|tests/|"
    r"\.md$|\.pyc$|jsonl$|/conftest)"
)

# 扫描消费者范围 (bin/ + omo 内核)
SCAN_DIRS = ["bin/", "projects/omo/src/"]


def extract_kinds() -> Counter:
    """从 omo-events.jsonl 提取 emit kind 计数."""
    if not EVENTS.is_file():
        return Counter()
    kinds: Counter = Counter()
    for line in EVENTS.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = d.get("kind")
        if kind:
            kinds[kind] += 1
    return kinds


def find_consumers(kind: str) -> list[str]:
    """grep kind 在扫描范围, 排除 emit 端/生成器/测试/文档. 返回消费者文件."""
    try:
        res = subprocess.run(
            ["grep", "-rl", "--include=*.py", kind, *SCAN_DIRS],
            cwd=WORKSPACE, capture_output=True, text=True, timeout=30, check=False,
        )
    except subprocess.TimeoutExpired:
        return []
    return [p for p in res.stdout.splitlines() if p and not EXCLUDE_RE.search(p)]


def main() -> int:
    as_json = "--json" in sys.argv
    kinds = extract_kinds()
    dead_loops: list[dict] = []
    alive: list[dict] = []

    for kind, count in kinds.most_common():
        if count < 5:  # 低频 emit 不判 (< 5 条可能一次性)
            continue
        consumers = find_consumers(kind)
        entry = {
            "kind": kind,
            "emit_count": count,
            "consumer_count": len(consumers),
            "consumers": consumers[:3],
        }
        if len(consumers) == 0:
            entry["status"] = "dead_loop"
            dead_loops.append(entry)
        else:
            entry["status"] = "alive"
            alive.append(entry)

    report = {
        "checked_total": len(alive) + len(dead_loops),
        "alive": len(alive),
        "dead_loops": dead_loops,
        "ok": len(dead_loops) == 0,
    }

    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1

    print("═══ 闭环回路检测 (原则4: emit 必有消费者) ═══")
    print(f"▶ 检查 kind: {report['checked_total']} (alive={report['alive']} dead_loop={len(dead_loops)})")
    for d in dead_loops:
        print(f"  💀 {d['kind']}: {d['emit_count']} 条 emit, 零消费者 (死回路, emit 没人看)")
    for a in alive[:3]:
        print(f"  ✅ {a['kind']}: {a['emit_count']} 条 emit, {a['consumer_count']} 消费者")
    print(f"\n═══ 总体: {'✅ 全 emit 有消费者' if report['ok'] else '❌ 有死回路'} ═══")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
