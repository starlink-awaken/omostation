#!/usr/bin/env python3
"""auto-merge-decide — F4 merge 状态机决策核心 (auto-PR ISA D2).

四条件 AND 决定 PR 是否 auto-merge (ISC-26):
  1. gate_strict_ok    — gac-gate --strict CI 绿 (含 reachability, A2)
  2. ai_non_blocking   — AI review 非 REQUEST_CHANGES (F1 advisory 时恒真; blocking 时查 review state)
  3. lane_auto         — 文件 lane 全 auto (D1 auto-merge-lane-policy)
  4. reachability_ok   — 子模块 gitlink 可达 (含在 gac-gate strict, 显式单列 ISC-26)

任一红 → manual (ISC-27 回退人工).

依赖状态 (2026-07-02):
  - F1 advisory (ai_non_blocking 恒真), blocking 后激活
  - --pr 真集成待 E2 (测试 PR); --mock 现在可验证决策逻辑

用法:
  python3 bin/auto-merge-decide.py --mock [gate=1,ai=0,lane=1,reach=1]  # mock 测试
  python3 bin/auto-merge-decide.py --pr <num>                            # 查真 PR (gh, 待 E2)
  python3 bin/auto-merge-decide.py --json <...>                          # 机器可读
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

# 复用 D1 auto-merge-lane-policy (importlib, 文件名连字符)
_D1_PATH = Path(__file__).parent / "auto-merge-lane-policy.py"
_spec = importlib.util.spec_from_file_location("_auto_merge_lane_policy", _D1_PATH)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
lane_decide = _mod.decide


def decide(
    gate_strict_ok: bool,
    ai_blocking: bool,
    lane_paths: list[str],
    reachability_ok: bool,
) -> dict:
    """四条件 AND → auto/manual + 各条件状态 + blockers (ISC-26/27).

    lane_paths: PR 改的文件 paths (D1 lane policy 判定).
    ai_blocking: F1 advisory 时 False (恒非 blocking); blocking 时 = review state == REQUEST_CHANGES.
    """
    lane_outcome = lane_decide(lane_paths)
    conditions = {
        "gate_strict_ok": bool(gate_strict_ok),
        "ai_non_blocking": not ai_blocking,
        "lane_auto": lane_outcome["decision"] == "auto",
        "reachability_ok": bool(reachability_ok),
    }
    blockers = sorted(k for k, v in conditions.items() if not v)
    decision = "auto" if not blockers else "manual"
    return {
        "decision": decision,
        "conditions": conditions,
        "blockers": blockers,
        "lane": {
            "decision": lane_outcome["decision"],
            "lanes": lane_outcome["lanes"],
            "reason": lane_outcome["reason"],
        },
        "reason": (
            "四条件全绿 → auto-merge 候选 (ISC-26)"
            if decision == "auto"
            else f"阻塞: {', '.join(blockers)} → 回退人工 (ISC-27)"
        ),
    }


def _parse_mock(spec: str) -> dict:
    """解析 --mock 'gate=1,ai=0,lane=1,reach=1' → dict. 默认全绿."""
    out = {"gate": True, "ai": False, "lane_paths": ["README.md"], "reach": True}
    if spec:
        for item in spec.split(","):
            item = item.strip()
            if "=" not in item:
                continue
            key, _, val = item.partition("=")
            key = key.strip()
            val = val.strip()
            if key in ("gate", "ai", "reach"):
                out[key] = val in ("1", "true", "yes")
            elif key == "lane":
                # lane=auto (README.md) / lane=manual (.omo/...)
                out["lane_paths"] = ["README.md"] if val in ("auto", "1") else [".omo/_truth/x.yaml"]
    return out


def _check_pr(num: int) -> dict:
    """查真 PR 四条件 (gh CLI). 待 E2 测试 PR 完整验证."""
    import subprocess
    # gate: gh pr checks <num> --json name,state (找 gac-gate)
    # review: gh pr view <num> --json reviewDecision
    # files: gh pr view <num> --json files
    # reachability: 含在 gac-gate strict (A2)
    result = subprocess.run(
        ["gh", "pr", "view", str(num), "--json", "files,reviewDecision,state"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return {"error": f"gh pr view 失败: {result.stderr.strip()}", "num": num}
    data = json.loads(result.stdout)
    paths = [f["path"] for f in data.get("files", [])]
    review_decision = data.get("reviewDecision", "")
    ai_blocking = review_decision == "REQUEST_CHANGES"
    # gate + reachability: gac-gate strict CI 状态 (需 gh pr checks 查 gac-gate job)
    # MVP: 假定 reviewDecision 非 REQUEST_CHANGES + state open → 待 gh pr checks 细化
    return {
        "num": num,
        "state": data.get("state"),
        "review_decision": review_decision,
        "ai_blocking": ai_blocking,
        "paths": paths,
        "note": "gate/reachability 待 gh pr checks 细化 (MVP: 假定 gac-gate CI 验)",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="auto-merge-decide — F4 决策核心 (D2)")
    parser.add_argument("--mock", nargs="?", const="", help="mock 测试 (可选 gate=1,ai=0,lane=1,reach=1)")
    parser.add_argument("--pr", type=int, help="查真 PR (gh, 待 E2)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.pr is not None:
        pr = _check_pr(args.pr)
        if "error" in pr:
            print(f"❌ {pr['error']}", file=sys.stderr)
            return 2
        # MVP: gate/reachability 假定 (待 gh pr checks)
        outcome = decide(
            gate_strict_ok=True,  # 待 gh pr checks gac-gate
            ai_blocking=pr["ai_blocking"],
            lane_paths=pr["paths"],
            reachability_ok=True,  # 含 gac-gate strict
        )
        outcome["pr"] = pr
    elif args.mock is not None:
        m = _parse_mock(args.mock)
        outcome = decide(
            gate_strict_ok=m["gate"],
            ai_blocking=m["ai"],
            lane_paths=m["lane_paths"],
            reachability_ok=m["reach"],
        )
        outcome["mock"] = m
    else:
        parser.error("需 --mock 或 --pr <num>")

    if args.json:
        print(json.dumps(outcome, ensure_ascii=False, indent=2))
    else:
        print(f"decision: {outcome['decision']}")
        print(f"conditions: {outcome['conditions']}")
        print(f"reason: {outcome['reason']}")
        print(f"lane: {outcome['lane']['decision']} ({outcome['lane']['reason']})")
    return 0 if outcome["decision"] == "auto" else 1


if __name__ == "__main__":
    sys.exit(main())
