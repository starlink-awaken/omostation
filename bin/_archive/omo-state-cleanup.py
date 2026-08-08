#!/usr/bin/env python3
"""omo-state-cleanup.py — 派生面统一审计 + 收口 (M4 Phase 3, ADR-0135)

ADR-0132 § P3 任务清单:
  - 审计所有 .omo/_derived/ 现有产物
  - 写 omo-state-cleanup.py 统一收口
  - 更新 .gitignore 把所有派生路径纳入 gitignored 范式

设计: 这是派生面范式 (ADR-0129) 的 SSOT enforcement.
  - 派生面 = 由 SSOT 经算法重建的产物 (gitignored)
  - SSOT = 手写, git tracked
  - cleanup.py 验证 SSOT+派生面分离的纪律

用法:
    uv run --with "pyyaml" python bin/gac/omo-state-cleanup.py audit
    uv run --with "pyyaml" python bin/gac/omo-state-cleanup.py status
    uv run --with "pyyaml" python bin/gac/omo-state-cleanup.py canonify
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


# ── 已知派生面路径 (ADR-0128 + ADR-0129 + M4 Phase 1.2 产出的) ──
DERIVED_PATHS = [
    # ADR-0128 投影面
    ".omo/state/runtime/",
    # ADR-0129 + M4 Phase 1.2 (新加)
    ".omo/_derived/",
    # 已知 runtime 残渣
    "runtime/logs/",
    "runtime/run-continuation/",
    "data/cards/",
    # docs/ 派生
    "docs/generated/",
    # governance 残渣
    ".omo/autopilot/",
    ".omo/change-log/mutations.jsonl",
    ".omo/capabilities/",
    ".omo/run-continuation/",
    ".omo/_delivery/ingress/",
    ".omo/_control/evolution/drift/",
    ".omo/_control/evolution/drift-history/",
    ".omo/_control/evolution/approval-board/",
    ".omo/_control/evolution/loop/",
    ".omo/_control/evolution/self-evolve/",
    ".omo/_control/evolution/radar-history.json",
    ".omo/tasks/registry/done/",
    ".omo/_truth/registry/dependency-baseline.yaml",
    # debt dashboard 派生产物 (items/ 例外)
    ".omo/debt/dashboard/",
    ".omo/debt/dispatch/",
    ".omo/debt/action-packet/",
    ".omo/debt/review-queue/",
    ".omo/debt/owner-routing/",
    ".omo/debt/reviews/",
    ".omo/debt/campaign/",
    ".omo/debt/reporting/",
    # sessions / workers 残渣
    ".omo/workers/",
    ".omo/.omo/",
    ".omc/",
    "projects/.omc/",
    # mcp / ssot 派生
    "projects/ecos/src/ecos/ssot/mof/m0/snapshot.yaml",
    "projects/cockpit-ui/",
    # runtime db
    "spaces/*.db",
]

# 必须 tracked (SSOT 不入 ignore)
MUST_BE_TRACKED_PATHS = [
    ".omo/debt/items/",  # canonical debt SSOT (修正 c82cbd23 后入仓)
    ".omo/_knowledge/decisions/",
    ".omo/_knowledge/audits/",
    ".omo/_knowledge/patterns/",
    "docs/M4-ROADMAP.md",  # ADR-0132 路线图
    "docs/M4-report-p1s2-l0-migration.md",  # ADR-0133 报告
    "bin/_archive/l0-constraints-migrate.py",  # P1-S2 工具
    "bin/mof/mof-bootstrap.py",  # P2-S4 校验器
]


def audit(ws: Path) -> dict:
    """审计当前 gitignore 规则 vs 派生面 SSOT 列表.

    检查项:
      1. 每个 DERIVED_PATHS 路径是否被 git check-ignore 拒绝
      2. 每个 MUST_BE_TRACKED 路径是否 NOT gitignored
      3. 工作树里是否有非 gitignored 的派生文件泄漏
    """
    # 1. 每个 DERIVED_PATHS 用 git check-ignore 验证 (权威)
    audit_results = []
    for dp in DERIVED_PATHS:
        is_ignored = _git_check_ignore(ws, dp)
        audit_results.append({
            "path": dp,
            "expected_gitignored": True,
            "currently_gitignored": is_ignored,
            "ok": is_ignored,
        })

    # 2. 检查 must-be-tracked 不应该被 ignore
    must_results = []
    for tp in MUST_BE_TRACKED_PATHS:
        is_ignored = _git_check_ignore(ws, tp)
        must_results.append({
            "path": tp,
            "expected_tracked": True,
            "currently_gitignored": is_ignored,
            "ok": not is_ignored,
        })

    # 3. 工作树非 gitignored 派生文件 (泄漏检查)
    leak_results = []
    try:
        out = subprocess.run(
            ["git", "status", "--ignored", "--porcelain"],
            cwd=ws, capture_output=True, text=True, timeout=30,
        )
        for line in out.stdout.splitlines():
            if line.startswith("?? "):
                fp = line[3:]
                if fp.startswith(".omo/_derived/") or fp.startswith("docs/generated/"):
                    pass  # 已 gitignored
                leak_results.append(fp)
    except Exception as e:
        leak_results.append(f"audit skipped: {e}")

    return {
        "audit": audit_results,
        "must_be_tracked": must_results,
        "leak_check": leak_results,
        "audit_pass": all(r["ok"] for r in audit_results),
        "must_ok": all(r["ok"] for r in must_results),
        "leak_free": len(leak_results) == 0,
    }


def _git_check_ignore(ws: Path, rel_path_str: str) -> bool:
    """用 git 权威判断 relative path string 是否被 gitignore.

    对不存在的目录也能查到 (因为 gitignore 是基于 pattern 而非 inode).
    rc 0 = ignored, rc 1 = not ignored, rc 128 = error (treat as not ignored)

    关键: 传相对路径字符串 (git tree 内部路径), 保留 trailing slash
    (gitignore pattern '.omc/' 对应目录而非文件).
    """
    try:
        out = subprocess.run(
            ["git", "check-ignore", "-q", rel_path_str],
            cwd=ws, capture_output=True, text=True, timeout=10,
        )
        return out.returncode == 0
    except Exception:
        return False


def status(ws: Path) -> str:
    """输出当前派生面状态 (人类可读)."""
    out = subprocess.run(
        ["git", "status", "--ignored", "--short"],
        cwd=ws, capture_output=True, text=True, timeout=30,
    )
    return out.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("audit", help="审计派生面 gitignore 状态")
    sub.add_parser("status", help="git status --ignored 派生面条目")
    sub.add_parser("canonify", help="收口 (增加派生面 gitignore 规则)")
    parser.add_argument("--ws", type=Path, default=Path())
    args = parser.parse_args()

    ws = args.ws.resolve() if args.ws else Path.cwd()

    if args.cmd == "audit":
        result = audit(ws)
        audit_n = len([r for r in result["audit"] if r["ok"]])
        total = len(result["audit"])
        print(f"# 派生面审计 (ws={ws})\n")
        print(f"## 派生面 ({audit_n}/{total} 已 gitignored, {'✅' if result['audit_pass'] else '⚠️'})\n")
        for r in result["audit"]:
            mark = "✓" if r["ok"] else "❌"
            print(f"  {mark} {r['path']:50s} gitignored={r['currently_gitignored']}")
        print(f"\n## 必须 tracked (SSOT, {len(result['must_be_tracked'])} 项, {'✅' if result['must_ok'] else '⚠️'})")
        for r in result["must_be_tracked"]:
            mark = "✓" if r["ok"] else "❌"
            print(f"  {mark} {r['path']:50s}")
        print(f"\n## 派生面泄漏: {'✅ 0' if result['leak_free'] else '⚠️'}")
        for fp in result["leak_check"][:5]:
            print(f"  - {fp}")
        if len(result["leak_check"]) > 5:
            print(f"  ... ({len(result['leak_check']) - 5} more)")
        all_ok = result["audit_pass"] and result["must_ok"] and result["leak_free"]
        print(f"\n{'✅ 全部合规' if all_ok else '⚠️ 有 1+ 项需 canonify'}")
        return 0 if all_ok else 1

    if args.cmd == "status":
        print(status(ws))
        return 0

    if args.cmd == "canonify":
        # 检查 audit, 若非 100% PASS, 报告缺什么规则, 让用户决定
        result = audit(ws)
        missing = [r for r in result["audit"] if not r["ok"]]
        if not missing:
            print("✅ 所有派生面已 gitignored, 无需新增规则")
            return 0
        print(f"⚠️ 以下 {len(missing)} 派生面缺 gitignore 规则 (建议追加):")
        for r in missing:
            print(f"  + {r['path']}")
        print(f"\n复制到 .gitignore 即可. 不在本脚本自动写入(防止非预期变更).")
        return 1


if __name__ == "__main__":
    sys.exit(main())
