#!/usr/bin/env python3
"""任务所有权强制 — 非终态任务必须有 owner.

2026-09-19 实证:
债务项 `UNASSIGNED_ENTROPY`(high,「任务所有权熵 — 15/104 无 owner, 38/104 无 phase」)
声称"已由 bet-ledger + task schema 强制 (owner/phase 必填字段校验)" —— 而该强制
**并不存在**: 唯一相关实现 `bin/_archive/bet-to-task.py` 已归档, 且它的证据引用
`P43-ARCH-ANALYSIS-002` 是全仓不存在的悬空文档。

现场实测 (2026-09-19) 反而给出更精确的结论:
  - **非终态 omo-schema 任务 (active/planned/blocked) 100% 有 owner** —— 前提不成立
  - 缺 owner 的全部是**终态**记录 (closed/done, 历史, 所有权不再可行动)
  - `remediation/` 用**另一套 schema** (`status`/`assigned_to`), 本不适用 owner/phase
  - `phase` 并非 omo 任务 schema 的字段 (active 0/1, closed 0/15, done 0/11 使用;
    仅 archived 与 remediation 使用) —— 故**不应**普遍要求 phase

本工具即把上述"声称存在的强制"真正落地 (范围按实测收敛, 不虚设 phase 要求):
  非终态任务 (active / planned / blocked) 必须带非空 `owner`。

用法:
    python3 bin/gac/check-task-ownership.py [--json]
退出码: 0 = 合规; 1 = 存在非终态无主任务
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[2]
# 非终态树 (omo task schema)。remediation/ 用另一套 schema (assigned_to), 不纳入。
NON_TERMINAL_TREES = ("active", "planned", "blocked")


def scan(root: Path | None = None) -> dict:
    base = (root or _ROOT) / ".omo" / "tasks"
    unowned: list[dict] = []
    scanned = 0
    for tree in NON_TERMINAL_TREES:
        d = base / tree
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*.yaml")):
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            if not isinstance(data, dict) or not data.get("id"):
                continue
            scanned += 1
            owner = str(data.get("owner") or "").strip()
            if not owner:
                unowned.append({"tree": tree, "id": str(data.get("id")),
                                "file": path.name,
                                "state": str(data.get("lifecycle_state")
                                             or data.get("status") or "?")})
    return {"tasks_dir": str(base), "scanned": scanned, "unowned": unowned}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    r = scan()
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))

    if r["unowned"]:
        if not args.json:
            print(f"🔴 非终态任务缺 owner ({len(r['unowned'])} / 扫描 {r['scanned']}):",
                  file=sys.stderr)
            for u in r["unowned"]:
                print(f"   [{u['tree']}] {u['id']} ({u['file']}, {u['state']})",
                      file=sys.stderr)
            print("   处置: 非终态任务必须有明确 owner (单点责任); 历史终态记录不在此列",
                  file=sys.stderr)
        return 1

    if not args.json:
        print(f"✅ 非终态任务所有权完整 (扫描 {r['scanned']} 项, 全部有 owner)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
