#!/usr/bin/env python3
"""GOV-REBAL 派生文档-only fast-track 判定 (差距治理 S5).

背景 (复盘实证): 治理密度已达规模不经济拐点 — 每 100 py 脚本配 40 条 gate 规则,
纯派生文档变更 (capability-registry 重生成 / CLI-REFERENCE 更新) 也走全量
ADR 占号 + agent-workflow 仪式, 治理成本与变更语义不成比例.

本检查器: 判定某次变更是否"纯派生文档" (派生投影, 无真实语义变更):
  派生文档 = docs/generated/* + projects/cockpit/CAPABILITY-MAP.md
           + docs/CLI-REFERENCE.md + docs/INDEX-MCP.md
  若全部变更面都在派生文档集 → 输出 fast-track 建议 (change-lane=derived-doc-only),
  提示: 走 project-doc-change / state-sync 轻量 workflow, 不需 ADR 占号.
  若混入非派生面 (源码/SSOT/治理代码) → derived-only=false, 走常规 gate.

与 gate 的关系 (SOFT check):
  - 纯派生文档变更 → gate 仍 PASS, 但 finding_topics 记录 fast-track 建议
  - 非纯派生文档 → 无 finding, 正常门禁
  不翻转 gate (软信号, 类比 governance-semantic-gate).

用法:
    python3 bin/gac/check-derived-only-fast-track.py                # staged 变更
    python3 bin/gac/check-derived-only-fast-track.py --staged       # staged (默认)
    python3 bin/gac/check-derived-only-fast-track.py --unstaged     # unstaged
    python3 bin/gac/check-derived-only-fast-track.py --file <path>  # 显式文件集
    python3 bin/gac/check-derived-only-fast-track.py --json         # JSON 输出

SSOT:  docs/generated/ (GEN-FORCE 保护生成物) + change-lane-check.py 的 docs 分类.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]

# 派生文档面: 投影重生成产物, 无独立语义变更
DERIVED_DOC_PATTERNS: tuple[str, ...] = (
    "docs/generated/",
    "projects/cockpit/CAPABILITY-MAP.md",
    "docs/CLI-REFERENCE.md",
    "docs/INDEX-MCP.md",
)

# fast-track 适用的轻量 workflow (替代全量 ADR 占号仪式)
FAST_TRACK_WORKFLOWS = ("project-doc-change", "state-sync", "handoff-resume")


def _git_changed(staged: bool, files: list[str] | None) -> list[str]:
    """取变更文件列表 (staged/unstaged/显式)."""
    if files:
        return files
    cmd = ["git", "diff", "--cached", "--name-only"] if staged else ["git", "diff", "--name-only"]
    r = subprocess.run(cmd, cwd=WORKSPACE, capture_output=True, text=True, check=False)
    return [line.strip() for line in r.stdout.splitlines() if line.strip()]


def _is_derived(path: str) -> bool:
    """判定路径是否派生文档面."""
    return any(path.startswith(prefix) or path == prefix.rstrip("/") for prefix in DERIVED_DOC_PATTERNS)


def check(staged: bool = True, files: list[str] | None = None) -> dict:
    """返回判定报告.

    结构:
      {ok, derived_only, derived_files, non_derived_files,
       fast_track, workflows, change_lane}
    """
    changed = _git_changed(staged, files)
    if not changed:
        return {
            "ok": True,
            "derived_only": False,
            "derived_files": [],
            "non_derived_files": [],
            "fast_track": False,
            "workflows": [],
            "change_lane": "no-changes",
        }
    derived = [p for p in changed if _is_derived(p)]
    non_derived = [p for p in changed if not _is_derived(p)]
    derived_only = len(derived) > 0 and len(non_derived) == 0
    return {
        "ok": True,
        "derived_only": derived_only,
        "derived_files": derived,
        "non_derived_files": non_derived,
        "fast_track": derived_only,
        "workflows": list(FAST_TRACK_WORKFLOWS) if derived_only else [],
        "change_lane": "derived-doc-only" if derived_only else "mixed-or-source",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="GOV-REBAL: 派生文档-only fast-track 判定")
    ap.add_argument("--staged", action="store_true", help="检查 staged 变更 (默认)")
    ap.add_argument("--unstaged", action="store_true", help="检查 unstaged 变更")
    ap.add_argument("--file", action="append", default=[], help="显式变更文件路径")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()

    staged = not args.unstaged
    report = check(staged=staged, files=args.file or None)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        if not report["derived_files"] and not report["non_derived_files"]:
            print("check-derived-only-fast-track: 无变更, 跳过")
        elif report["fast_track"]:
            print(
                f"check-derived-only-fast-track: ✅ 纯派生文档变更 "
                f"({len(report['derived_files'])} files, change-lane=derived-doc-only)"
            )
            print(f"  → fast-track 建议: 走 {'/'.join(report['workflows'])} 轻量 workflow, 不需 ADR 占号")
        else:
            n_derived = len(report["derived_files"])
            n_src = len(report["non_derived_files"])
            print(
                f"check-derived-only-fast-track: 非纯派生文档变更 "
                f"(derived={n_derived}, source={n_src}) → 常规 gate, 无 fast-track"
            )
    return 0  # 软信号, 不翻转 gate


if __name__ == "__main__":
    sys.exit(main())
