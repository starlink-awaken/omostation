#!/usr/bin/env python3
"""check-perf-budget: 验证 sgf-policy gate 的 perf_budget_s 声明 (N1).

标准见 .omo/standards/gac-check-perf-budget.md:
  - 非 ci_only gate 必须声明 perf_budget_s 且 ≤2 (pre-commit 预算)
  - ci_only / broken gate 不约束 (不进 pre-commit)
  - 无声明的存量 gate 进 baseline grace (warn)
  - 无声明的新增 gate (非 baseline) → fail

照搬 baseline 模式 (M2 check-work-landed): 标准化 > 逐个打补丁.
静态 schema 检查, 自身 <0.1s (不读 git, 不跑 subprocess).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
SGF_POLICY = (
    WORKSPACE / "projects/ecos/src/ecos/ssot/mof/m1/governance/sgf-policy.yaml"
)
BASELINE_FILE = WORKSPACE / ".omo/_truth/registry/baseline-perf-budget.txt"
PRECOMMIT_BUDGET_S = 2


def _load_gates() -> list[dict]:
    if not SGF_POLICY.is_file():
        return []
    data = yaml.load(
        SGF_POLICY.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader
    ) or {}
    return data.get("gates") or []


def _load_baseline() -> set[str]:
    if not BASELINE_FILE.is_file():
        return set()
    return {
        line.strip()
        for line in BASELINE_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--dump-baseline",
        action="store_true",
        help="dump current non-ci_only gates without perf_budget_s (grace list).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat baseline grace rows as fail too (CI mode).",
    )
    args = parser.parse_args(argv)

    gates = _load_gates()

    # 生成 baseline grace 清单 (当前无声明的非 ci_only gate)
    if args.dump_baseline:
        for g in gates:
            if g.get("ci_only") or g.get("broken"):
                continue
            if "perf_budget_s" not in g:
                print(g.get("id", "?"))
        return 0

    baseline = _load_baseline()
    findings: list[dict] = []
    summary = {"checked": 0, "passed": 0, "warn": 0, "fail": 0}

    for g in gates:
        gid = g.get("id") or "?"
        if g.get("ci_only") or g.get("broken"):
            continue  # ci_only 不进 pre-commit; broken 已 skip
        summary["checked"] += 1
        budget = g.get("perf_budget_s")
        if budget is None:
            if gid in baseline and not args.strict:
                findings.append({
                    "id": gid,
                    "kind": "missing_grace",
                    "message": "no perf_budget_s (baseline grace, 存量不追溯)",
                })
                summary["warn"] += 1
            else:
                findings.append({
                    "id": gid,
                    "kind": "missing",
                    "message": "gate 缺 perf_budget_s 声明 (新 check 必须声明, 见 gac-check-perf-budget.md §4)",
                })
                summary["fail"] += 1
        elif budget > PRECOMMIT_BUDGET_S:
            findings.append({
                "id": gid,
                "kind": "over_budget",
                "perf_budget_s": budget,
                "message": f"perf_budget_s={budget} > {PRECOMMIT_BUDGET_S} 但未标 ci_only (>2s 必须 ci_only)",
            })
            summary["fail"] += 1
        else:
            summary["passed"] += 1

    ok = summary["fail"] == 0
    report = {"ok": ok, "summary": summary, "findings": findings}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"check-perf-budget: {'PASS' if ok else 'FAIL'}")
        print(
            f"  checked={summary['checked']} passed={summary['passed']} "
            f"warn={summary['warn']} fail={summary['fail']}"
        )
        for f in findings:
            print(f"  - {f['id']} [{f['kind']}] {f.get('message', '')}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
