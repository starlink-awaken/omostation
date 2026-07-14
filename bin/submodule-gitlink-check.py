#!/usr/bin/env python3
"""submodule-gitlink-check.py — 检测 submodule gitlink 漂移.

遍历所有 submodule, 比较主仓 gitlink commit vs 工作树 submodule HEAD.
漂移 (gitlink ≠ 工作树 HEAD) 说明工作树 submodule 在别的 commit, 通常是
并发 agent 各自 bump 不同版本后的残留. 这次 (2026-07-14) 实战 3 次全盘
分叉 (agora/ecos/metaos/aetherforge/cockpit/bus-foundation), 靠人工
git submodule update ×9 才清零 — 本脚本把检测自动化.

`git submodule status` 行首前缀:
  - 空格 = 工作树 HEAD == gitlink (干净)
  - '+'    = 漂移 (工作树 HEAD != gitlink)  ← 本脚本核心检测
  - '-'    = 未 init
  - 'U'    = 冲突

用法:
  python3 bin/submodule-gitlink-check.py          # 人读输出, 漂移 exit 1
  python3 bin/submodule-gitlink-check.py --json   # JSON (CI/cron 友好)

CI/cron 集成: 漂移则 exit 1 触发告警, 或管道 `--json` 后自动 update.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

TIMEOUT = 10


def _git(args: list[str], cwd: str | None = None) -> str:
    """跑 git 命令, 失败返回空 (检测脚本, 不抛)."""
    try:
        p = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            cwd=cwd,
        )
        return p.stdout.strip() if p.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def main() -> int:
    as_json = "--json" in sys.argv
    root = _git(["rev-parse", "--show-toplevel"])
    if not root:
        if as_json:
            print(json.dumps({"error": "not a git repo"}, ensure_ascii=False))
        return 0  # 非 git 目录, 不当失败

    status = _git(["submodule", "status"], cwd=root)
    if not status:
        if as_json:
            print(json.dumps({"drift_count": 0, "drifts": []}, ensure_ascii=False))
        else:
            print("ℹ️ 无 submodule")
        return 0

    drift: list[dict[str, str]] = []
    for line in status.splitlines():
        if not line.strip():
            continue
        prefix = line[0]
        rest = line[1:].strip()
        parts = rest.split(None, 2)
        if len(parts) < 2:
            continue
        sha = parts[0].lstrip("-")
        sm_path = parts[1]

        if prefix == "+":
            wt_head = _git(["rev-parse", "HEAD"], cwd=str(Path(root) / sm_path))
            drift.append({
                "path": sm_path,
                "gitlink": sha[:8],
                "worktree_head": (wt_head or "?")[:8],
                "issue": "drift",
                "fix": f"git submodule update --init {sm_path}",
            })
        elif prefix == "-":
            drift.append({
                "path": sm_path,
                "issue": "uninitialized",
                "fix": f"git submodule update --init {sm_path}",
            })
        elif prefix == "U":
            drift.append({
                "path": sm_path,
                "issue": "merge_conflict",
                "fix": f"手动解 {sm_path} 冲突后 git add",
            })

    if as_json:
        print(json.dumps(
            {"drift_count": len(drift), "drifts": drift},
            ensure_ascii=False, indent=2,
        ))
    elif drift:
        print(f"⚠️ {len(drift)} 个 submodule gitlink 异常:")
        for d in drift:
            if d["issue"] == "drift":
                print(f"  +{d['path']}: gitlink={d['gitlink']} worktree={d['worktree_head']}")
            else:
                print(f"  {d['issue']}: {d['path']}")
            print(f"    修复: {d['fix']}")
    else:
        print("✅ 所有 submodule gitlink 同步, 无漂移")

    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
