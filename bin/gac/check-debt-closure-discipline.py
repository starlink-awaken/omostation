#!/usr/bin/env python3
"""债务闭环节律 — `resolved` 必须留闭环证据, 且状态字段须唯一.

背景 (2026-09-19 实证):
  `.omo/debt/items/AGENT_COORDINATION.yaml` (sev=high, "多 Agent 协调无强制执行")
  标着 `lifecycle_state: resolved` + 一条 resolution_evidence, 但:
    - 无 `closed_at` / `close_reason`
    - `last_reviewed_at` == `opened_at` (2026-07-14, 从未复审)
  而它声称的"已由 swarm-coordination + D1-D5 门禁强制执行"**在实践中并不成立** ——
  同日为补这个执行层提交了 #4000 / #4013 等 4 个 PR。
  这正是仓库自身登记的最高优先债务「**声明/执行鸿沟**」的实例。

另一类: 8 项同时带 `status` 与 `lifecycle_state`, 其中 7 项两者矛盾
  (`status: registered` vs `lifecycle_state: closed`)。按 `status` 查询会得到
  完全错误的答案 —— 本工具作者在巡查时就被它骗过一次 (读出"17 项未关闭",
  实际只有 1 项)。

两项判据 (终态 = closed / resolved / done):
  A. 字段并存     — 同时有 `status` 与 `lifecycle_state` (应统一为后者)
  C. 终态无闭环戳 — 无 `closed_at`

**与 verify.py 的分工 (2026-09-19 消除重叠)**:
  "终态但无证据" 的检查由 `bin/ssot/verify.py --mode task` 承担 —— 它已收敛到
  真实注册表 `.omo/debt/items/` (#4037), 且 `_shared.check_evidence` 已扩展接受
  文本型 `resolution_evidence`/`closed_evidence`。此前本工具也查这一条, 属**重复**;
  现交还 verify.py, 本工具只保留**债务 schema 特有**的两条卫生规则 (A/C)。
  一个关注点一个工具。

**本工具只报不修**: 凭空补写 `closed_at`/`close_reason` 就是**伪造闭环证据**,
违反"真实性"约束 —— 必须由 owner 用真实记录补齐。

用法:
    python3 bin/gac/check-debt-closure-discipline.py [--json]
退出码: 0 = 合规; 1 = 存在违规
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[2]
ITEMS_DIR = _ROOT / ".omo" / "debt" / "items"
TERMINAL = {"closed", "resolved", "done"}


def scan(items_dir: Path | None = None) -> dict:
    base = items_dir or ITEMS_DIR
    dual_fields: list[dict] = []
    no_closed_at: list[dict] = []
    scanned = 0
    terminal_count = 0

    if not base.is_dir():
        return {"items_dir": str(base), "scanned": 0, "terminal": 0,
                "dual_fields": [], "no_closed_at": []}

    for path in sorted(base.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        scanned += 1
        item_id = str(data.get("id", path.stem))
        status = data.get("status")
        lifecycle = data.get("lifecycle_state")

        # A. 字段并存 (无论是否冲突都算不合规: 单一事实源)
        if status is not None and lifecycle is not None:
            dual_fields.append({
                "id": item_id, "file": path.name,
                "status": status, "lifecycle_state": lifecycle,
                "conflicting": str(status) != str(lifecycle),
            })

        if lifecycle not in TERMINAL:
            continue
        terminal_count += 1

        # C. 终态必须有闭环时间戳
        if not data.get("closed_at"):
            no_closed_at.append({
                "id": item_id, "file": path.name,
                "lifecycle_state": lifecycle,
                "opened_at": data.get("opened_at"),
                "last_reviewed_at": data.get("last_reviewed_at"),
                "never_reviewed": (data.get("last_reviewed_at") is not None
                                   and data.get("last_reviewed_at") == data.get("opened_at")),
            })

    return {"items_dir": str(base), "scanned": scanned, "terminal": terminal_count,
            "dual_fields": dual_fields, "no_closed_at": no_closed_at}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    r = scan()
    violations = len(r["dual_fields"]) + len(r["no_closed_at"])
    if args.json:
        print(json.dumps({**r, "violations": violations}, ensure_ascii=False, indent=1))

    if not violations:
        if not args.json:
            print(f"✅ 债务闭环节律合规 (扫描 {r['scanned']} 项, 终态 {r['terminal']})")
        return 0

    if not args.json:
        print(f"🔴 债务闭环节律违规 {violations} 处 "
              f"(扫描 {r['scanned']} 项, 终态 {r['terminal']}):", file=sys.stderr)
        if r["dual_fields"]:
            print(f"\n  A. 状态字段并存 ({len(r['dual_fields'])}) —— "
                  f"应统一为 lifecycle_state:", file=sys.stderr)
            for d in r["dual_fields"]:
                flag = "  ⚠️ 值冲突" if d["conflicting"] else ""
                print(f"     {d['file']}: status={d['status']} vs "
                      f"lifecycle_state={d['lifecycle_state']}{flag}", file=sys.stderr)
        if r["no_closed_at"]:
            print(f"\n  C. 终态无 closed_at ({len(r['no_closed_at'])}) —— "
                  f"闭环未留时间戳:", file=sys.stderr)
            for d in r["no_closed_at"]:
                extra = "  ← last_reviewed == opened (从未复审)" if d["never_reviewed"] else ""
                print(f"     {d['file']}: {d['lifecycle_state']} "
                      f"opened={d['opened_at']}{extra}", file=sys.stderr)
        print("\n  注: 本检查**只报不修** —— 凭空补写 closed_at/close_reason 即"
              "伪造闭环证据;\n      须由 owner 用真实记录补齐。"
              "\n  A 类可机械修复: python3 bin/gac/fix-debt-fields.py --apply",
              file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
