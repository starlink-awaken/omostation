#!/usr/bin/env python3
"""CR-CHANGE-LANE-RANGE: CI 侧的 lane 隔离判据 (per-commit 粒度)。

背景 —— 这道尺此前在 CI 上是**空转**的:

- `sgf-policy.yaml` 把 `change-lane-check` 登记为 `bin/change-lane-check.py --staged`;
- CI 干净检出里**没有 staged 文件** ⇒ `--staged` 读到空集 ⇒ 恒 PASS;
- `change-lane-check.py` 的 `PUSH_RANGE` 分支 (按本次 push 的 commit 范围判)
  在 `.githooks/` 里没有任何导出点 ⇒ 该分支从未被触发;
- 本地 `pre-commit` / `pre-push` 也不调这道尺 (hook-runner 的检查清单里没有它)
  ⇒ 三条路径全部空转, 规则**从未真正生效过**。

判据粒度 = **per-commit**, 不是整段合并:
规则原文是「每 commit 单 lane」(ADR-0122 §46) / 「每个 staged set 一个 lane」
(ADR-0456 §验收)。一段范围里可以有多个不同 lane 的 commit, 那是合规的;
违规的是**单个 commit 内**混了多个 lane。这与整段合并判定有实质差别:
「commit A = docs」「commit B = 子模块指针」两个 commit 合规, 合并成一个集合判
就会得到 {docs, submodule_pointer} 的假违规。

范围来源 (CI 事件上下文):
- `pull_request`: base = `github.event.pull_request.base.sha`,
  head = `github.event.pull_request.head.sha`;
- `push` 到 main: base = `github.event.before`, head = `github.sha`;
- 其他事件 (workflow_dispatch 等): 无可比基线 ⇒ 跳过 (不假装通过也不假装失败)。

严重度: **软信号 (advisory)**。实测 40 个已合并 PR 中 13 个 (32.5%) 在此判据下
违规 —— 这不是新缺陷, 而是这条规则**从未生效**留下的历史欠账 (main 近 60 个
commit 里 27 个违规)。直接改成阻断会立刻炸掉约三分之一的 PR, 属于治理政策
变更, 需独立授权。本检查先把信号**显形** (CI 日志可见 + 可 JSON 消费),
阻断与否由后续决策决定。

用法:
    python3 bin/gac/check-change-lane-range.py            # 人类可读
    python3 bin/gac/check-change-lane-range.py --json     # 机器可读
    python3 bin/gac/check-change-lane-range.py --fail-on-violation
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
CHANGE_LANE_CHECK = WORKSPACE / "bin" / "change-lane-check.py"


def _load_change_lane_check():
    """复用 change-lane-check 的 classify/allowed_for (不重写分类逻辑)。"""
    spec = importlib.util.spec_from_file_location("change_lane_check", str(CHANGE_LANE_CHECK))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["change_lane_check"] = module
    spec.loader.exec_module(module)
    return module


def _read_event() -> dict:
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not event_path or not os.path.isfile(event_path):
        return {}
    try:
        with open(event_path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def resolve_range() -> tuple[str, str, str]:
    """返回 (base, head, source); 无法判定时 base/head 为空串。"""
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    event = _read_event()

    if event_name in ("pull_request", "pull_request_target"):
        pr = event.get("pull_request") or {}
        base = str(pr.get("base", {}).get("sha") or "")
        head = str(pr.get("head", {}).get("sha") or "")
        if base and head:
            return base, head, "pull_request"

    if event_name == "push":
        base = str(event.get("before") or "")
        head = str(os.environ.get("GITHUB_SHA") or "")
        # 全零 sha = 该分支首次 push, 无可比基线
        if base and head and set(base) != {"0"}:
            return base, head, "push"

    return "", "", "none"


def main() -> int:
    parser = argparse.ArgumentParser(description="CI lane isolation check (per-commit granularity)")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument(
        "--fail-on-violation",
        action="store_true",
        help="Exit 1 on violation (default: advisory, exit 0)",
    )
    parser.add_argument("--base", default="", help="Override base sha")
    parser.add_argument("--head", default="", help="Override head sha")
    args = parser.parse_args()

    clc = _load_change_lane_check()

    base = args.base
    head = args.head
    source = "explicit"
    if not base or not head:
        base, head, source = resolve_range()

    if not base or not head:
        payload = {
            "ok": True,
            "skipped": True,
            "reason": "no comparable baseline (event context unavailable)",
            "source": source,
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print("[check-change-lane-range] SKIP 无可比基线 (非 PR/push 事件或缺 sha)")
        return 0

    git_range = f"{base}..{head}"
    commits = clc.commit_paths_in_range(git_range, cwd=WORKSPACE)
    if not commits:
        payload = {
            "ok": True,
            "skipped": True,
            "reason": f"no commits resolvable in range {git_range}",
            "source": source,
            "range": git_range,
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"[check-change-lane-range] SKIP 范围 {git_range} 内无可解析 commit")
        return 0

    submodules = clc.submodule_paths()
    allowed_lanes = clc.parse_allowed_lanes([os.environ.get("AGENT_WORKFLOW_ALLOWED_LANES", "")])

    per_commit = []
    violations = []
    for sha, paths in commits:
        by_lane: dict[str, list[str]] = {}
        for path in paths:
            by_lane.setdefault(clc.classify(path, submodules), []).append(path)
        lanes = set(by_lane)
        ok = clc.allowed_for(lanes, allowed_lanes)
        entry = {
            "commit": sha,
            "ok": ok,
            "lanes": sorted(lanes),
            "by_lane": by_lane,
            "files": len(paths),
        }
        per_commit.append(entry)
        if not ok:
            violations.append(entry)

    payload = {
        "ok": not violations,
        "skipped": False,
        "source": source,
        "range": git_range,
        "commits": len(per_commit),
        "violations": len(violations),
        "violation_commits": [v["commit"] for v in violations],
        "per_commit": per_commit,
        "severity": "advisory",
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if violations:
            print(
                f"[check-change-lane-range] WARN {len(violations)}/{len(per_commit)} commits "
                f"混 lane (范围 {git_range}, 来源 {source})"
            )
            for entry in violations:
                print(f"  commit {entry['commit'][:9]}: lanes={','.join(entry['lanes'])}")
                for lane, paths in entry["by_lane"].items():
                    preview = ", ".join(paths[:4])
                    suffix = "" if len(paths) <= 4 else f" ... +{len(paths) - 4}"
                    print(f"    {lane}: {preview}{suffix}")
            print("  判据: 每 commit 单 lane (ADR-0122 §46 / ADR-0456 §验收)")
            print("  状态: advisory —— 该规则此前从未生效 (历史欠账), 阻断与否待独立授权")
        else:
            print(
                f"[check-change-lane-range] OK {len(per_commit)} commits "
                f"均单 lane (范围 {git_range})"
            )

    if violations and args.fail_on_violation:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
