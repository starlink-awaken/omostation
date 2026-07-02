#!/usr/bin/env python3
"""auto-merge-decide — F4 merge 状态机决策核心 (auto-PR ISA D2 + F6).

五条件 AND 决定 PR 是否 auto-merge:
  1. gate_strict_ok    — gac-gate --strict CI 绿 (含 reachability, A2)
  2. ai_non_blocking   — AI review 非 REQUEST_CHANGES (F1 advisory 时恒真; blocking 时查 review state)
  3. lane_auto         — 文件 lane 全 auto (D1 auto-merge-lane-policy)
  4. reachability_ok   — 子模块 gitlink 可达 (含在 gac-gate strict, ISC-26 显式单列)
  5. author_is_human   — PR author 非 bot (ISC-33 Anti: bot 不自合自己 PR)

任一红 → manual (ISC-27 回退人工).

F6 (2026-07-02): ISC-33 不自合 (第三道红线) + --pr 真集成 (gh pr checks 查 gac-gate CI,
  不再 MVP 假定). 之前 --pr 假定 gate/reachability=True, 现在真查.

依赖状态 (2026-07-02):
  - F1 advisory (ai_non_blocking 恒真), blocking 后激活
  - --pr 真集成: gh pr checks 查 gac-gate (PR #4 实证 CI 红时正确判 manual)

用法:
  python3 bin/auto-merge-decide.py --mock [gate=1,ai=0,lane=1,reach=1,author=bot]  # mock 测试
  python3 bin/auto-merge-decide.py --pr <num>                                       # 查真 PR (gh)
  python3 bin/auto-merge-decide.py --json <...>                                     # 机器可读
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

# ISC-33: 已知 GitHub bot author (这些 author 开的 PR 强制 manual, 防自合链)
# login 后缀 "[bot]" 通用判定 + 已知 bot 名兜底
_BOT_AUTHORS = {
    "github-actions", "github-actions[bot]",
    "dependabot", "dependabot[bot]",
    "renovate", "renovate[bot]",
    "imgbot", "mergify", "allcontributors", "netlify", "vercel",
}


def _is_bot_author(author):
    """GitHub bot 判定 (ISC-33): login 后缀 '[bot]' 或在已知 bot 集合."""
    if not author:
        return False
    login = (author.lower() if isinstance(author, str) else str(author).lower()).strip()
    if login.endswith("[bot]"):
        return True
    return login in _BOT_AUTHORS


def _check_gac_gate_ci(num):
    """查 gac-gate job CI 状态 (gh pr checks). strict gate 含 reachability (A2).

    返回 (gate_strict_ok, reachability_ok). 查不到/没跑 → 保守 (False, False).
    多个同名 gac-gate job (push/pr 各一) 全 SUCCESS 才绿.
    """
    import subprocess
    result = subprocess.run(
        ["gh", "pr", "checks", str(num), "--json", "name,state"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return (False, False)
    try:
        checks = json.loads(result.stdout)
    except json.JSONDecodeError:
        return (False, False)
    gac = [c for c in checks if c.get("name") == "gac-gate"]
    if not gac:
        return (False, False)
    all_success = all(c.get("state") == "SUCCESS" for c in gac)
    # reachability 含在 gac-gate strict (submodule-reachability-gate 是 strict 子 check)
    return (all_success, all_success)


def decide(gate_strict_ok, ai_blocking, lane_paths, reachability_ok, author=None):
    """五条件 AND → auto/manual + 各条件状态 + blockers (ISC-26/27/33).

    lane_paths: PR 改的文件 paths (D1 lane policy 判定).
    ai_blocking: F1 advisory 时 False (恒非 blocking); blocking 时 = review state == REQUEST_CHANGES.
    author: PR author login (None = 未知, 当 human 处理; bot → ISC-33 manual).
    """
    lane_outcome = lane_decide(lane_paths)
    # ISC-33 Anti: author == bot → 强制 manual (第三道红线, 防自合链)
    author_is_human = not _is_bot_author(author) if author else True
    conditions = {
        "gate_strict_ok": bool(gate_strict_ok),
        "ai_non_blocking": not ai_blocking,
        "lane_auto": lane_outcome["decision"] == "auto",
        "reachability_ok": bool(reachability_ok),
        "author_is_human": author_is_human,
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
        "author": author,
        "reason": (
            "五条件全绿 → auto-merge 候选 (ISC-26 + ISC-33)"
            if decision == "auto"
            else f"阻塞: {', '.join(blockers)} → 回退人工 (ISC-27)"
        ),
    }


def _parse_mock(spec):
    """解析 --mock 'gate=1,ai=0,lane=1,reach=1,author=bot' → dict. 默认全绿 + human author."""
    out = {"gate": True, "ai": False, "lane_paths": ["README.md"], "reach": True, "author": "starlink-awaken"}
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
            elif key == "author":
                out["author"] = val
    return out


def _check_pr(num):
    """查真 PR 五条件 (gh CLI). --pr 真集成 (F6, 2026-07-02).

    gate_strict_ok + reachability_ok: gh pr checks 查 gac-gate job (strict 含 reachability).
    ai_blocking: reviewDecision == REQUEST_CHANGES (F1 advisory 时无此状态 → False).
    author: gh pr view author.login (ISC-33 bot 判定).
    """
    import subprocess
    result = subprocess.run(
        ["gh", "pr", "view", str(num), "--json", "files,reviewDecision,state,author"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return {"error": f"gh pr view 失败: {result.stderr.strip()}", "num": num}
    data = json.loads(result.stdout)
    author_obj = data.get("author") or {}
    author_login = author_obj.get("login", "")
    paths = [f["path"] for f in data.get("files", [])]
    review_decision = data.get("reviewDecision", "")
    ai_blocking = review_decision == "REQUEST_CHANGES"
    gate_strict_ok, reachability_ok = _check_gac_gate_ci(num)
    return {
        "num": num,
        "state": data.get("state"),
        "author": author_login,
        "review_decision": review_decision,
        "ai_blocking": ai_blocking,
        "paths": paths,
        "gate_strict_ok": gate_strict_ok,
        "reachability_ok": reachability_ok,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="auto-merge-decide — F4 决策核心 (D2 + F6)")
    parser.add_argument("--mock", nargs="?", const="", help="mock 测试 (可选 gate=1,ai=0,lane=1,reach=1,author=bot)")
    parser.add_argument("--pr", type=int, help="查真 PR (gh, 含 gac-gate CI 查)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.pr is not None:
        pr = _check_pr(args.pr)
        if "error" in pr:
            print(f"❌ {pr['error']}", file=sys.stderr)
            return 2
        outcome = decide(
            gate_strict_ok=pr["gate_strict_ok"],
            ai_blocking=pr["ai_blocking"],
            lane_paths=pr["paths"],
            reachability_ok=pr["reachability_ok"],
            author=pr["author"],
        )
        outcome["pr"] = pr
    elif args.mock is not None:
        m = _parse_mock(args.mock)
        outcome = decide(
            gate_strict_ok=m["gate"],
            ai_blocking=m["ai"],
            lane_paths=m["lane_paths"],
            reachability_ok=m["reach"],
            author=m["author"],
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
