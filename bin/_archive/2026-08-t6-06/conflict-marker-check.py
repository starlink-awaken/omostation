#!/usr/bin/env python3
"""pre-commit 冲突标记检测 — 防止未解决 git 冲突被提交.

背景: 并发 agent merge 冲突未解决就提交 (如 SUBMODULE_DRIFT.yaml 含
"<<< HEAD" 冲突段) 会污染 main, 导致 check-yaml/派生文档 CI 失败.

本脚本: pre-commit 调用, 扫描 staged 文本文件是否含冲突标记.
含则阻断 (exit 1), 提示解决冲突.

用法 (pre-commit):
    python3 bin/ssot/conflict-marker-check.py

返回: 0 = 无冲突标记; 1 = 检测到 (阻断).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# git 冲突标记的 ======= 固定 7 字符; markdown Setext 标题下划线通常更长
# (CHANGELOG/docs 常见 ============ 行), 仅 7 字符纯等号行才判冲突 (T6-01 误报修复)
_MARKERS = ("<<<<<<<", ">>>>>>>")
_EQ_LINE = "=" * 7


def _staged_files() -> list[str]:
    """列出 staged 的 tracked 文件 (排除二进制/大文件)."""
    try:
        r = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return [line for line in r.stdout.splitlines() if line]
    except Exception:
        return []


def _has_conflict_marker(path: Path) -> bool:
    """检查文件是否含冲突标记 (仅文本文件)."""
    try:
        # 跳过超大文件 (如 SQLite/node_modules)
        if path.stat().st_size > 5_000_000:
            return False
        text = path.read_text(encoding="utf-8", errors="ignore")
        # 冲突标记必须出现在行首 (排除代码中的字面量)
        lines = text.splitlines()
        if any(line.startswith(m) for line in lines for m in _MARKERS):
            return True
        # 行首恰好 7 个等号 (git 冲突分隔), 更长的纯等号线是 markdown Setext 标题
        return any(line == _EQ_LINE for line in lines)
    except Exception:
        return False


def main() -> int:
    violations: list[str] = []
    for name in _staged_files():
        p = ROOT / name
        if p.exists() and _has_conflict_marker(p):
            violations.append(name)

    if violations:
        print("[conflict-marker] ❌ 检测到未解决 git 冲突标记:")
        for v in violations:
            print(f"  - {v}")
        print("[conflict-marker] 请先解决冲突 (git mergetool / 手动编辑) 再提交")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
