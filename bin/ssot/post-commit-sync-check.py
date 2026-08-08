#!/usr/bin/env python3
"""post-commit 派生同步检查 — agora 等子模块指针变更后自动 sync-all-docs.

背景: agora 迭代频繁 (新增 MCP 工具/BOS 服务), bump 指针后派生文档
(capability-registry.yaml / CAPABILITY-MAP / CLI-REFERENCE / INDEX-MCP)
需要重新生成, 否则 CI check-docs-drift 失败. 用户每次需手动提醒.

本脚本: post-commit hook 调用, 检测本次 commit 是否变更子模块 gitlink,
若是则自动跑 sync-all-docs 生成派生文档到工作区 (不自动 commit —
由 agent/开发者随下次 commit 提交, 避免残缺生成入库).

用法 (post-commit hook):
    python3 bin/ssot/post-commit-sync-check.py

返回: 0 = 无需同步 / 已同步; 1 = 同步后产生 diff (提示提交).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 迭代敏感的 PASW 子模块 (bump 后需派生文档同步)
SYNC_SUBMODULES = ("projects/agora",)


def _changed_gitlinks() -> list[str]:
    """检测本次 commit (HEAD) 相对上一 commit (HEAD~1) 的 gitlink 变更."""
    try:
        r = subprocess.run(
            ["git", "diff", "HEAD~1", "HEAD", "--name-only"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        changed = r.stdout.splitlines()
        return [s for s in SYNC_SUBMODULES if s in changed]
    except Exception:  # noqa: BLE001 — hook 失败不影响 commit
        return []


def _run_sync_all_docs() -> tuple[bool, str]:
    """跑 make sync-all-docs, 返回 (success, output tail)."""
    try:
        r = subprocess.run(
            ["make", "sync-all-docs"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        return r.returncode == 0, (r.stdout or r.stderr)[-400:]
    except Exception as exc:  # noqa: BLE001 — hook 失败不影响 commit
        return False, str(exc)


def _has_doc_drift() -> bool:
    """检查派生文档是否产生 git diff (待提交)."""
    targets = [
        "docs/generated/",
        "projects/cockpit/CAPABILITY-MAP.md",
        "docs/CLI-REFERENCE.md",
        "docs/INDEX-MCP.md",
    ]
    try:
        r = subprocess.run(
            ["git", "diff", "--name-only", "--", *targets],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return bool(r.stdout.strip())
    except Exception:  # noqa: BLE001 — hook 失败不影响 commit
        return False


def main() -> int:
    changed = _changed_gitlinks()
    if not changed:
        return 0  # 无子模块指针变更, 无需同步

    print(f"[sync-check] 检测到子模块指针变更: {', '.join(changed)}")
    print("[sync-check] 自动运行 make sync-all-docs ...")
    ok, out = _run_sync_all_docs()
    if not ok:
        print(f"[sync-check] ⚠️ sync-all-docs 执行失败 (可能子模块不全):\n{out}")
        return 0  # 失败不阻塞 commit

    if _has_doc_drift():
        print("[sync-check] ⚠️ 派生文档已更新 (capability-registry/CLI-REFERENCE/INDEX-MCP)")
        print("[sync-check] 请随下次 commit 提交这些派生文档 (CI check-docs-drift 依赖)")
        return 1
    print("[sync-check] ✅ 派生文档无漂移")
    return 0


if __name__ == "__main__":
    sys.exit(main())
