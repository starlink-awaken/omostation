#!/usr/bin/env python3
"""BET-Y1Q4-T4-01: 真实评测集 v1 生成器.

从真实 adjudication 数据 (pr-harvest + adjudications) 提取评测集, 标注:
- source: 全部来自真实 PR 评审/裁决 (非合成)
- verdict 分类: positive (merged/accepted) / negative (closed_unmerged/rejected)
              / boundary (小改动 merged 或大改动 rejected — 决策边界)
- origin: 真实来源 ref (github PR / adjudication id)

用法:
  python3 bin/ssot/gen-real-evalset.py           # 生成并落盘
  python3 bin/ssot/gen-real-evalset.py --json    # 输出 JSON
  python3 bin/ssot/gen-real-evalset.py --count   # 统计
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]

PR_HARVEST = WORKSPACE_ROOT / ".omo" / "_delivery" / "outcomes" / "pr-harvest.jsonl"
ADJUDICATIONS = WORKSPACE_ROOT / ".omo" / "_delivery" / "outcomes" / "adjudications.jsonl"
EVALSET_DIR = WORKSPACE_ROOT / ".omo" / "_delivery" / "evalsets"

EVALSET_SCHEMA = "real-evalset/v1"

# 边界例判定: 小改动但被拒 (评审严格) 或 大改动但通过 (评审宽容)
SMALL_DIFF = 30
LARGE_DIFF = 300


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    recs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            recs.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return recs


def _classify(verdict: str, additions: int, deletions: int) -> str:
    """positive / negative / boundary 分类."""
    diff = int(additions or 0) + int(deletions or 0)
    if verdict == "rejected":
        if diff <= SMALL_DIFF:
            return "boundary"  # 小改动被拒 = 决策边界
        return "negative"
    # accepted
    if diff >= LARGE_DIFF:
        return "boundary"  # 大改动通过 = 决策边界
    return "positive"


def _build_evalset() -> dict[str, Any]:
    prs = _read_jsonl(PR_HARVEST)
    adjs = _read_jsonl(ADJUDICATIONS)

    items: list[dict] = []

    # PR harvest → 真实工程裁决
    for r in prs:
        verdict = r.get("verdict", "accepted")
        label = _classify(verdict, r.get("additions", 0), r.get("deletions", 0))
        items.append(
            {
                "id": f"pr-{r.get('pr_number', '?')}",
                "verdict": label,
                "source": f"github://{r.get('repo', 'omostation')}/pull/{r.get('pr_number')}",
                "synthetic": False,
                "features": {
                    "title": r.get("title", ""),
                    "additions": r.get("additions", 0),
                    "deletions": r.get("deletions", 0),
                    "author": r.get("author", ""),
                    "event": r.get("event", ""),
                },
                "label_hint": verdict,
            }
        )

    # adjudications → 人工裁决
    for a in adjs:
        verdict = a.get("verdict", "accepted")
        label = _classify(verdict, 0, 0)
        items.append(
            {
                "id": a.get("id", "adj-?"),
                "verdict": label,
                "source": f"adjudication://{a.get('id', '?')}",
                "synthetic": False,
                "features": {
                    "decision_id": a.get("decision_id", ""),
                    "adjudicator": a.get("adjudicator", ""),
                    "notes": a.get("notes", ""),
                },
                "label_hint": verdict,
            }
        )

    # GitHub closed-unmerged PRs → 真实负例 (评审未通过/被关闭)
    try:
        closed = _fetch_closed_unmerged("starlink-awaken/omostation")
        for pr in closed:
            items.append(
                {
                    "id": f"gh-{pr.get('number', '?')}",
                    "verdict": "negative",
                    "source": f"github://starlink-awaken/omostation/pull/{pr.get('number')}",
                    "synthetic": False,
                    "features": {
                        "title": pr.get("title", ""),
                        "state": pr.get("state", ""),
                        "closed_at": pr.get("closed_at", ""),
                        "user": (pr.get("user") or {}).get("login", ""),
                    },
                    "label_hint": "rejected",
                }
            )
    except (OSError, ValueError):
        # gh api 不可用/无网络时跳过 GitHub 补充, 仍用本地 pr-harvest
        pass

    # GitHub merged PRs (全量分页) → 补充真实正例, 确保 ≥200
    try:
        merged = _fetch_merged("starlink-awaken/omostation", max_pages=3)
        seen_ids = {i["id"] for i in items}
        for pr in merged:
            pid = f"ghm-{pr.get('number', '?')}"
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            label = _classify("accepted", pr.get("additions", 0), pr.get("deletions", 0))
            items.append(
                {
                    "id": pid,
                    "verdict": label,
                    "source": f"github://starlink-awaken/omostation/pull/{pr.get('number')}",
                    "synthetic": False,
                    "features": {
                        "title": pr.get("title", ""),
                        "additions": pr.get("additions", 0),
                        "deletions": pr.get("deletions", 0),
                        "merged_at": pr.get("merged_at", ""),
                        "user": (pr.get("user") or {}).get("login", ""),
                    },
                    "label_hint": "accepted",
                }
            )
    except (OSError, ValueError):
        pass

    return {
        "schema": EVALSET_SCHEMA,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(items),
        "source_note": "全部来自真实 PR 评审 (pr-harvest + GitHub closed-unmerged) 与人工裁决 (adjudications), 非合成数据",
        "distribution": dict(Counter(i["verdict"] for i in items)),
        "items": items,
    }


def _fetch_closed_unmerged(repo: str, per_page: int = 100) -> list[dict]:
    """用 gh api 拉取真实被关闭未合并的 PR (负例来源)."""
    import subprocess

    proc = subprocess.run(
        [
            "gh", "api",
            f"repos/{repo}/pulls?state=closed&per_page={per_page}",
            "--jq",
            '[.[] | select(.merged_at == null) | {number, title, state, closed_at, user}]',
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if proc.returncode != 0:
        return []
    try:
        return json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return []


def _fetch_merged(repo: str, max_pages: int = 3) -> list[dict]:
    """用 gh api 分页拉取真实已合并 PR (正例补充, 带 additions/deletions)."""
    import subprocess

    results: list[dict] = []
    for page in range(1, max_pages + 1):
        proc = subprocess.run(
            [
                "gh", "api",
                f"repos/{repo}/pulls?state=closed&per_page=100&page={page}",
                "--jq",
                '[.[] | select(.merged_at != null) | {number, title, merged_at, user, additions, deletions}]',
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if proc.returncode != 0:
            break
        try:
            batch = json.loads(proc.stdout or "[]")
        except json.JSONDecodeError:
            break
        if not batch:
            break
        results.extend(batch)
    return results


def _write(path: Path, evalset: dict) -> None:
    EVALSET_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evalset, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="真实评测集 v1 生成器 (BET-Y1Q4-T4-01)")
    ap.add_argument("--json", action="store_true", help="输出 JSON 摘要")
    ap.add_argument("--count", action="store_true", help="统计")
    ap.add_argument("--output", type=str, default="evalset-v1.json", help="输出文件名")
    ap.add_argument("--dry-run", action="store_true", help="不落盘")
    args = ap.parse_args()

    evalset = _build_evalset()

    if not args.dry_run:
        _write(EVALSET_DIR / args.output, evalset)

    if args.json:
        print(json.dumps(
            {k: v for k, v in evalset.items() if k != "items"},
            ensure_ascii=False, indent=2,
        ))
        return 0
    if args.count:
        print(f"total={evalset['count']} distribution={evalset['distribution']}")
        return 0

    print(f"真实评测集 v1 ({evalset['count']} 条):")
    print(f"  分布: {evalset['distribution']}")
    print(f"  来源: {evalset['source_note']}")
    if not args.dry_run:
        print(f"  已落盘: {EVALSET_DIR / args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
