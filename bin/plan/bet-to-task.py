#!/usr/bin/env python3
"""bet-to-task.py — 把台账 bet 物化为 .omo/tasks/planned/ 任务卡（一对一）。

为什么一对一：多一层映射就多一层漂移源。bet.id 即 task.id，
台账是 SSOT，task 卡是投影，冲突时以台账为准。

默认 dry-run。写入前必读 .omo/tasks/README.md 的状态机与晋升协议：
  - planned/ 只存 backlog，不是执行队列
  - 晋升到 active/ 走 scripts/omo_worker.py task promote-eval / promote-apply
  - 本脚本只负责 planned/ 的生成与刷新，不做晋升

Usage:
    python3 bin/plan/bet-to-task.py                    # dry-run，看会生成什么
    python3 bin/plan/bet-to-task.py --window Y1Q1      # 只物化某个窗口
    python3 bin/plan/bet-to-task.py --apply            # 实际写入
    python3 bin/plan/bet-to-task.py --apply --prune    # 并删除台账里已不存在的 bet 卡
    python3 bin/plan/bet-to-task.py --check            # 只报漂移，非 0 退出
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("需要 pyyaml: uv run --with pyyaml python bin/plan/bet-to-task.py ...", file=sys.stderr)
    raise SystemExit(2)

WS = Path(__file__).resolve().parents[2]
LEDGER = WS / "docs" / "plans" / "3y-bet-ledger.yaml"
PLANNED = WS / ".omo" / "tasks" / "planned"
MARKER = "3y-bet-ledger"  # 用于识别哪些卡由本脚本生成

# bet.risk_level → task.allowed_operation_level（沿用 .omo/tasks/README.md 的枚举）
RISK_MAP = {"L1": "L1", "L2": "L2", "L3": "L3"}


def load_ledger() -> dict:
    if not LEDGER.exists():
        sys.exit(f"台账不存在: {LEDGER}")
    data: dict = {}
    for d in yaml.safe_load_all(LEDGER.read_text(encoding="utf-8")):
        if isinstance(d, dict):
            data.update(d)
    if "bets" not in data:
        sys.exit("台账缺少 bets 段")
    return data


def task_path(bet_id: str) -> Path:
    return PLANNED / f"{bet_id.lower()}.yaml"


def to_task(bet: dict, tracks: dict) -> dict:
    """bet → task 卡。只投影，不新增语义。"""
    tr = tracks.get(bet["track"], {})
    risk = bet.get("risk_level", "L1")
    return {
        "id": bet["id"],
        "title": bet["title"],
        # planned 只允许 candidate | pending（见 .omo/tasks/README.md）
        "status": "candidate",
        "task_type": "bet",
        "priority": bet.get("priority", "P2"),
        "owner": "human" if bet.get("human_gate") else "agent",
        "source": MARKER,
        "source_ref": f"docs/plans/3y-bet-ledger.yaml::{bet['id']}",
        "window": bet["window"],
        "track": bet["track"],
        "appetite": bet.get("appetite"),
        "desc": bet.get("goal", ""),
        "non_goals": bet.get("non_goals", []),
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "source_docs": [
            "docs/plans/3y-bet-ledger.yaml",
            "docs/plans/AGENT-BRIEF.md",
            "docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md",
        ],
        "depends_on": bet.get("depends_on", []),
        "risk_level": risk,
        "allowed_operation_level": RISK_MAP.get(risk, "L1"),
        "human_approval_required": bool(bet.get("human_gate")),
        "entry_gate": [f"依赖已 done: {d}" for d in (bet.get("depends_on") or [])],
        "evidence_required": list(bet.get("done_when", [])),
        # 立项依据【指针】——不复制内容，SSOT 仍在台账。
        # 缺这一条时，从 .omo/tasks/planned/ 直接领活的 agent 看不到 bet 的实测依据，
        # 只有走 skill bet-execution → bet-ledger.py show 那条路的才看得到。
        # 两条领取路径给出的信息不等价 = 静默缺口（2026-08-07 实测发现）。
        **(
            {
                "evidence_ref": (
                    f"docs/plans/3y-bet-ledger.yaml::{bet['id']}.evidence "
                    f"（{len(bet['evidence'])} 条，动手前必读："
                    f"bin/plan/bet-ledger.py show {bet['id']}）"
                )
            }
            if bet.get("evidence")
            else {}
        ),
        "test_plan": [v.get("cmd", "") for v in (bet.get("verify") or [])],
        "workflow": bet.get("workflow", "bet-execution"),
        "write_surfaces": bet.get("write_surfaces", []),
        "pasw_required": bool(bet.get("pasw_required")),
        "circuit_breaker": bet.get("circuit_breaker", ""),
        "retro_required": bet.get("retro") == "required",
        "retro_path": f".omo/_knowledge/retros/{bet['id']}.md",
        "agent_profile_hint": tr.get("agent_profile_hint", "engineering-agent"),
        "started_at": None,
        "completed_at": None,
        "blocked_by": None,
        "retry_count": 0,
    }


def dump(task: dict) -> str:
    header = (
        "# AUTOGEN from docs/plans/3y-bet-ledger.yaml — 勿手改\n"
        "# 改台账后重跑: uv run --with pyyaml python bin/plan/bet-to-task.py --apply\n"
        f"# generated_at: {datetime.now(timezone.utc).replace(microsecond=0).isoformat()}\n"
    )
    return header + yaml.safe_dump(task, allow_unicode=True, sort_keys=False)


def existing_generated() -> dict[str, Path]:
    """已由本脚本生成的卡：id → path。"""
    out: dict[str, Path] = {}
    if not PLANNED.is_dir():
        return out
    for p in PLANNED.glob("*.yaml"):
        try:
            txt = p.read_text(encoding="utf-8")
        except Exception:
            continue
        if MARKER not in txt:
            continue
        try:
            d = yaml.safe_load(txt) or {}
        except Exception:
            continue
        if isinstance(d, dict) and d.get("id"):
            out[d["id"]] = p
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="bet → planned task 物化（一对一）")
    ap.add_argument("--window", help="只处理某个窗口，如 Y1Q1")
    ap.add_argument("--apply", action="store_true", help="实际写入（默认 dry-run）")
    ap.add_argument("--prune", action="store_true", help="删除台账里已不存在的生成卡")
    ap.add_argument("--check", action="store_true", help="只报漂移，有漂移则非 0 退出")
    args = ap.parse_args()

    data = load_ledger()
    tracks = data.get("tracks", {})
    bets = data["bets"]
    if args.window:
        bets = [b for b in bets if b["window"] == args.window]

    have = existing_generated()
    want = {b["id"]: to_task(b, tracks) for b in bets}

    to_create, to_update, to_delete = [], [], []
    for bid, task in want.items():
        p = task_path(bid)
        if bid not in have:
            to_create.append((bid, p, task))
        else:
            old = yaml.safe_load(have[bid].read_text(encoding="utf-8")) or {}
            # 忽略执行期字段的差异，只比投影字段
            keep = ("assigned_to", "dispatch_id", "run_ref", "approval_ref",
                    "review_ref", "started_at", "completed_at", "blocked_by",
                    "retry_count", "status")
            merged = dict(task)
            for k in keep:
                if k in old:
                    merged[k] = old[k]
            if merged != old:
                to_update.append((bid, have[bid], merged))

    if args.prune or args.check:
        for bid, p in have.items():
            if bid not in want and not args.window:
                to_delete.append((bid, p))

    print(f"台账 bet: {len(bets)}   已生成卡: {len(have)}")
    print(f"新建 {len(to_create)}   更新 {len(to_update)}   待删 {len(to_delete)}")
    for bid, p, _ in to_create[:8]:
        print(f"  + {bid}  → {p.relative_to(WS)}")
    if len(to_create) > 8:
        print(f"  … 另 {len(to_create)-8} 个")
    for bid, p, _ in to_update[:8]:
        print(f"  ~ {bid}")
    for bid, p in to_delete[:8]:
        print(f"  - {bid}  （台账已移除）")

    if args.check:
        drift = len(to_create) + len(to_update) + len(to_delete)
        print(f"\n漂移: {drift}")
        return 1 if drift else 0

    if not args.apply:
        print("\n(dry-run。加 --apply 实际写入)")
        return 0

    PLANNED.mkdir(parents=True, exist_ok=True)
    for _, p, task in to_create:
        p.write_text(dump(task), encoding="utf-8")
    for _, p, task in to_update:
        p.write_text(dump(task), encoding="utf-8")
    if args.prune:
        for _, p in to_delete:
            p.unlink()

    print(f"\n已写入 {len(to_create)+len(to_update)} 个，删除 {len(to_delete) if args.prune else 0} 个")
    print("⚠ planned/ 只是 backlog。晋升到 active/ 走:")
    print("   python3 scripts/omo_worker.py task promote-eval <TASK_ID> --omo-dir .omo")
    print("   python3 scripts/omo_worker.py task promote-apply <TASK_ID> --promoted-by <ACTOR> --now <ISO8601> --omo-dir .omo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
