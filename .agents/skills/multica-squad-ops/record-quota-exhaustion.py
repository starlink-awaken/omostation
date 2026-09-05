#!/usr/bin/env python3
"""record-quota-exhaustion.py — 给 quota-ledger.yaml 里某个 runtime 记一次耗尽信号。

用法:
    python3 record-quota-exhaustion.py <runtime> "<观察到的报错文本片段>"

行为:
    - runtime 已在 entries 里: 把报错片段追加进 exhaustion_signals（去重），
      连续命中 >=2 次即把 last_exhausted_at 设为当前 UTC 时间。
    - runtime 不在 entries 里（比如还在 unclassified）: 报错退出，不静默创建新条目，
      避免台账被写坏——先手动确认该 runtime 该进哪个 tier 再补条目。

不做的事: 不做定时轮询、不做自动重试分派——那是 SOP §4 里 leader 的决策逻辑，
这个脚本只管"记一笔"，单一职责。
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

LEDGER_PATH = Path(__file__).parent / "quota-ledger.yaml"
EXHAUSTION_THRESHOLD = 2


def main() -> int:
    if len(sys.argv) != 3:
        print(f"用法: {sys.argv[0]} <runtime> \"<报错文本片段>\"", file=sys.stderr)
        return 1
    runtime, signal_text = sys.argv[1], sys.argv[2]

    raw = LEDGER_PATH.read_text(encoding="utf-8")
    comment_lines = []
    body_start = 0
    for line in raw.splitlines(keepends=True):
        if line.startswith("#") or line.strip() == "":
            comment_lines.append(line)
            body_start += len(line)
        else:
            break
    header = "".join(comment_lines)
    body = raw[body_start:]

    data = yaml.safe_load(body)
    entries = data.get("entries", [])
    entry = next((e for e in entries if e.get("runtime") == runtime), None)
    if entry is None:
        print(
            f"拒绝: runtime={runtime!r} 不在生产 entries 里(可能还是 unclassified)。"
            f"先确认它该进哪个 tier，手动补条目，别让脚本静默创建。",
            file=sys.stderr,
        )
        return 1

    signals = entry.setdefault("exhaustion_signals", [])
    hit_count_before = sum(1 for s in signals if signal_text in s or s in signal_text)
    if signal_text not in signals:
        signals.append(signal_text)

    if hit_count_before + 1 >= EXHAUSTION_THRESHOLD:
        entry["last_exhausted_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"runtime={runtime}: 达到熔断阈值({EXHAUSTION_THRESHOLD})，已标记 last_exhausted_at")
    else:
        print(f"runtime={runtime}: 记录信号({hit_count_before + 1}/{EXHAUSTION_THRESHOLD})，未到熔断阈值")

    new_body = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    LEDGER_PATH.write_text(header + new_body, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
