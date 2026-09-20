#!/usr/bin/env python3
"""claim-suggester.py — 根据 git log + retro + ledger 自动建议 candidate BETs (B1.2).

识别 git log 中尚未录入 ledger 的工作集群, 输出可作为下一阶段 BET 的候选.

检测模式:
  1. CONSOLIDATION : 同一 scope 多次 fix → 建议合并 fix
  2. TRACK-DEEPENING : 同一 track 多个 feat → 建议深化 BET
  3. ORPHAN-WIP : WIP on agent/...: <sha> 残留 → 建议收口
  4. DOC-DRIFT : 反复 chore/docs(doc) → 建议文档收敛 BET
  5. STALE-PLANNED : 长期 ledger 状态的 > N 天 → 建议清理

用法:
  python3 bin/ssot/claim-suggester.py [--since-days 30] [--json]

依赖:
  bin/plan/bet-ledger.py  (查 ledger 现有 BET)
  git log  (commit 历史)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "docs" / "plans" / "3y-bet-ledger.yaml"


def run_git_log(since_days: int) -> list[str]:
    """读取 git log 提交标题, 自 since_days 内."""
    since = (datetime.now(UTC) - timedelta(days=since_days)).strftime("%Y-%m-%d")
    result = subprocess.run(
        ["git", "log", f"--since={since}", "--no-merges", "--pretty=format:%H|%s"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return [line for line in result.stdout.splitlines() if line]


def get_existing_bet_ids() -> set[str]:
    """从 ledger 提取所有 BET-ID."""
    result = subprocess.run(
        ["python3", "bin/plan/bet-ledger.py", "list"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    ids = set()
    for line in result.stdout.splitlines():
        # 格式: "BET-Y1Q4-T7-01           Y1Q4   T7-SCENE     ..."
        m = re.match(r"^(BET-[\w-]+)\s+", line)
        if m:
            ids.add(m.group(1))
    return ids


def detect_consolidation(commits: list[str], since: int) -> list[dict]:
    """检测同一 scope 多次 fix → 建议合并.

    例: fix(panorama): A, B, D, E 三项连续 → "panorama 收口" BET 候选.
    """
    fix_by_scope: dict[str, list[str]] = defaultdict(list)
    pattern = re.compile(r"^([0-9a-f]+)\|fix\(([\w-]+)\):")
    for line in commits:
        m = pattern.match(line)
        if m:
            fix_by_scope[m.group(2)].append(m.group(1)[:7])
    out = []
    for scope, hashes in fix_by_scope.items():
        if len(hashes) >= 3:
            out.append({
                "kind": "CONSOLIDATION",
                "scope": scope,
                "fix_count": len(hashes),
                "fix_hashes": hashes[:5],
                "rationale": f"{scope} 模块 {since} 天内累计 {len(hashes)} 次 fix, 建议合并收口",
                "suggested_id": f"BET-CONSOLIDATE-{scope.upper()}-{since:02d}{datetime.now(UTC).month:02d}",
            })
    return out


def detect_track_deepening(commits: list[str]) -> list[dict]:
    """检测同一 track 多个 feat → 建议深化 BET.

    关键词识别: panorama / claims / value / debt / governance 等大方向.
    """
    track_keywords = {
        "panorama": ["panorama", "dashboard", "claims"],
        "value": ["value", "readiness", "evidence"],
        "debt": ["debt", "drift", "audit"],
        "governance": ["governance", "gac", "rule"],
    }
    feat_by_track: dict[str, list[str]] = defaultdict(list)
    pattern = re.compile(r"^([0-9a-f]+)\|feat\(([\w-]+)\):")
    for line in commits:
        m = pattern.match(line)
        if not m:
            continue
        scope = m.group(2)
        for track, kws in track_keywords.items():
            if any(kw in scope.lower() for kw in kws):
                feat_by_track[track].append(f"{scope} ({m.group(1)[:7]})")
                break
    out = []
    for track, items in feat_by_track.items():
        if len(items) >= 4:
            out.append({
                "kind": "TRACK-DEEPENING",
                "track": track,
                "feat_count": len(items),
                "feat_scopes": items[:5],
                "rationale": f"{track} track {len(items)} 个 feat, 已形成深度, 建议深化 BET",
                "suggested_id": f"BET-{track.upper()}-DEEPEN-{datetime.now(UTC).strftime('%Y%m')}",
            })
    return out


def detect_orphan_wip(commits: list[str]) -> list[dict]:
    """检测 WIP on agent/...: <sha> 残留 → 建议收口."""
    pattern = re.compile(r"^([0-9a-f]+)\|WIP on (agent/[\w/-]+)")
    out = []
    for line in commits:
        m = pattern.match(line)
        if m:
            out.append({
                "kind": "ORPHAN-WIP",
                "wip_branch": m.group(2),
                "wip_sha": m.group(1)[:7],
                "rationale": f"WIP 提交 {m.group(1)[:7]} 在分支 {m.group(2)} 残留, 建议收口或复活",
                "suggested_id": f"BET-WIP-CLOSEOUT-{m.group(1)[:7]}",
            })
    return out


def detect_doc_drift(commits: list[str]) -> list[dict]:
    """检测反复 chore/docs(doc) → 建议文档收敛."""
    doc_pattern = re.compile(r"^([0-9a-f]+)\|chore\((?:tasks|docs|doc|debt)\)")
    doc_commits = [m.group(1)[:7] for line in commits if (m := doc_pattern.match(line))]
    out = []
    if len(doc_commits) >= 5:
        out.append({
            "kind": "DOC-DRIFT",
            "commit_count": len(doc_commits),
            "recent_hashes": doc_commits[:7],
            "rationale": f"近期 {len(doc_commits)} 次 chore/docs 提交, 文档管理本身需要 BET 化",
            "suggested_id": f"BET-DOC-CONSOLIDATE-{datetime.now(UTC).strftime('%Y%m')}",
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--since-days", type=int, default=30,
                    help="读取 git log 的天数范围 (默认 30)")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()

    if not (ROOT / ".git").exists():
        print("❌ 不是 git 仓库根目录")
        return 1

    commits = run_git_log(args.since_days)
    if not commits:
        print("⚠️ 无 git log 数据")
        return 0

    existing = get_existing_bet_ids()

    suggestions = (
        detect_consolidation(commits, args.since_days)
        + detect_track_deepening(commits)
        + detect_orphan_wip(commits)
        + detect_doc_drift(commits)
    )

    # 过滤已被 ledger 覆盖的建议 (suggested_id 含已存在的 BET-id 前缀则去重)
    filtered: list[dict] = []
    for s in suggestions:
        if any(s["suggested_id"].split("-")[1:3] == existing_id.split("-")[1:3]
               for existing_id in existing):
            continue
        filtered.append(s)

    payload = {
        "since_days": args.since_days,
        "commit_count": len(commits),
        "existing_bet_count": len(existing),
        "suggestions": filtered,
        "summary": {
            "CONSOLIDATION": sum(1 for s in filtered if s["kind"] == "CONSOLIDATION"),
            "TRACK-DEEPENING": sum(1 for s in filtered if s["kind"] == "TRACK-DEEPENING"),
            "ORPHAN-WIP": sum(1 for s in filtered if s["kind"] == "ORPHAN-WIP"),
            "DOC-DRIFT": sum(1 for s in filtered if s["kind"] == "DOC-DRIFT"),
        },
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"━━━ claim-suggester (last {args.since_days} days) ━━━")
        print(f"commits: {len(commits)}, existing BETs: {len(existing)}")
        print(f"suggestions: {len(filtered)}\n")
        if not filtered:
            print("✅ 无新建议 — ledger 与 git log 同步")
            return 0
        for i, s in enumerate(filtered, 1):
            print(f"[{i}] {s['kind']} · {s['suggested_id']}")
            print(f"    理由: {s['rationale']}")
            if "scope" in s:
                print(f"    scope: {s['scope']}")
            if "track" in s:
                print(f"    track: {s['track']}")
            if "wip_branch" in s:
                print(f"    branch: {s['wip_branch']}")
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())