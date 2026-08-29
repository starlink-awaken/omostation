#!/usr/bin/env python3
"""signals-rotate.py — SIGNALS.md 机器信号分流 + 去重

问题: scenario_engine/aggregated 机器信号重复写入 SIGNALS.md (同一 message
重复数十次), 淹没人类关注的跨域信号 (P: 信号噪音)。

做法:
  - 机器信号 (source: aggregated / scenario_engine) → 移出到
    @驾驶舱/_generated/signals-machine.jsonl (按 message+type 去重,
    记录 first_ts/last_ts/occurrences)
  - 人类信号保留在 SIGNALS.md
  - 幂等: 重复运行无副作用, 可挂 cron

用法: python3 signals-rotate.py [--dry-run]
无第三方依赖 (块级正则解析, 不需要 pyyaml)。
v1.0 | 2026-07-02
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DOCS_ROOT = Path(__file__).resolve().parents[2]
SIGNALS = DOCS_ROOT / "@驾驶舱/_control/SIGNALS.md"
MACHINE_LOG = DOCS_ROOT / "@驾驶舱/_generated/signals-machine.jsonl"
# 机器信号源: 精确名或前缀 (daemon/分布式引擎写入)
MACHINE_SOURCES = ("aggregated", "scenario_engine", "distributed.", "lifecycle.")

HEADER = """---
# SIGNALS — 跨域信号总线 (人类信号)
# 机器信号 (aggregated/scenario_engine) 由 signals-rotate.py 自动分流至
# @驾驶舱/_generated/signals-machine.jsonl — 勿在此手写机器信号。
signals:
"""


def split_entries(text: str) -> list[str]:
    """按顶层 '- ' 拆分 signals 列表条目 (保留原始块文本)。"""
    body = text.split("signals:", 1)[1] if "signals:" in text else text
    blocks, cur = [], []
    for line in body.splitlines():
        if re.match(r"^- ", line):
            if cur:
                blocks.append("\n".join(cur))
            cur = [line]
        elif cur and (line.startswith("  ") or not line.strip()):
            cur.append(line)
        elif cur and line.strip() == "---":
            break
    if cur:
        blocks.append("\n".join(cur))
    return [b for b in blocks if b.strip()]


def field(block: str, key: str) -> str:
    m = re.search(rf"^\s*{key}:\s*['\"]?(.+?)['\"]?\s*$", block, re.M)
    return m.group(1) if m else ""


def main() -> int:
    dry = "--dry-run" in sys.argv
    if not SIGNALS.exists():
        print(f"❌ 不存在: {SIGNALS}")
        return 2
    entries = split_entries(SIGNALS.read_text(encoding="utf-8"))
    machine, human = [], []
    for b in entries:
        src = field(b, "source")
        is_machine = any(src == m or src.startswith(m) for m in MACHINE_SOURCES)
        (machine if is_machine else human).append(b)

    # 机器信号去重聚合
    agg: dict[tuple[str, str], dict] = {}
    for b in machine:
        key = (re.sub(r"\s+", " ", field(b, "message"))[:200], field(b, "type"))
        ts = field(b, "ts")
        rec = agg.setdefault(key, {"message": key[0], "type": key[1],
                                   "source": field(b, "source"),
                                   "first_ts": ts, "last_ts": ts, "occurrences": 0})
        rec["occurrences"] += 1
        rec["last_ts"] = max(rec["last_ts"], ts)
        rec["first_ts"] = min(rec["first_ts"], ts)

    print(f"条目: {len(entries)} 总 = 机器 {len(machine)} (去重后 {len(agg)}) + 人类 {len(human)}")
    if dry:
        return 0

    if agg:
        MACHINE_LOG.parent.mkdir(parents=True, exist_ok=True)
        existing = set()
        if MACHINE_LOG.exists():
            for line in MACHINE_LOG.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(line)
                    existing.add((r.get("message"), r.get("type"), r.get("last_ts")))
                except json.JSONDecodeError:
                    pass
        with MACHINE_LOG.open("a", encoding="utf-8") as f:
            rotated_at = datetime.now(timezone.utc).isoformat()
            for rec in agg.values():
                if (rec["message"], rec["type"], rec["last_ts"]) not in existing:
                    f.write(json.dumps({**rec, "rotated_at": rotated_at}, ensure_ascii=False) + "\n")

    SIGNALS.write_text(HEADER + ("\n".join(human) + "\n" if human else "") + "---\n",
                       encoding="utf-8")
    print(f"✅ SIGNALS.md 已收敛为 {len(human)} 条人类信号; 机器信号 → {MACHINE_LOG.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
