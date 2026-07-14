#!/usr/bin/env python3
"""建包前边界检查 — 防违反目标项目 CLAUDE.md 约束.

protocols-layer 教训物化 (2026-06-26): 老王建 protocols-layer 包违反 kairon CLAUDE.md
(明确"历史别名, 不要重新引入已删 workspace 成员"). 此脚本建包/补实现前检查
package 是否在目标项目 CLAUDE.md 的"历史别名/已删成员"段, 防同类错误.

用法:
  python3 bin/ssot/check-boundary.py <package-name> [project]
  python3 bin/ssot/check-boundary.py protocols-layer kairon   # 应 fail
  python3 bin/ssot/check-boundary.py kos kairon                # 应 pass

挂建包流程: 建 kairon packages/<pkg> 前跑此检查.
"""

from __future__ import annotations

import sys
from pathlib import Path

# CI 可移植: __file__ 定位 workspace
WORKSPACE = Path(__file__).resolve().parents[2]

# "历史别名/已删"上下文关键词 (package 名附近出现这些 = 历史别名)
HISTORICAL_CONTEXT = [
    "历史别名",
    "已删",
    "不要重新引入",
    "不是 live",
    "compatibility alias",
    "已删除",
]


def check_package_boundary(package: str, project: str = "kairon") -> tuple[bool, str]:
    """检查 package 是否违反 project CLAUDE.md 边界.

    返回 (ok, reason). ok=False 表示 package 是历史别名/已删, 禁建包.
    """
    claude_md = WORKSPACE / "projects" / project / "CLAUDE.md"
    if not claude_md.exists():
        return True, f"{project}/CLAUDE.md 不存在, 跳过"

    content = claude_md.read_text(encoding="utf-8")

    # 找 package 名所有出现位置, 检查附近是否"历史别名/已删"上下文
    search_from = 0
    while True:
        idx = content.find(package, search_from)
        if idx == -1:
            break
        # package 名附近 ±150 字符上下文
        ctx_start = max(0, idx - 150)
        ctx_end = min(len(content), idx + len(package) + 150)
        context = content[ctx_start:ctx_end]

        for marker in HISTORICAL_CONTEXT:
            if marker in context:
                snippet = context.replace("\n", " ").strip()[:200]
                return (
                    False,
                    f"'{package}' 在 {project}/CLAUDE.md 标记为历史别名/已删 (上下文含 '{marker}')\n"
                    f"   片段: ...{snippet}...",
                )
        search_from = idx + len(package)

    return True, f"'{package}' 未在 {project}/CLAUDE.md 标为历史别名/已删"


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: check-boundary.py <package-name> [project]", file=sys.stderr)
        print("示例: check-boundary.py protocols-layer kairon", file=sys.stderr)
        return 2

    package = sys.argv[1]
    project = sys.argv[2] if len(sys.argv) > 2 else "kairon"

    ok, reason = check_package_boundary(package, project)
    if ok:
        print(f"✅ BOUNDARY OK: {reason}")
        return 0
    print(f"❌ BOUNDARY FAIL: {reason}", file=sys.stderr)
    print(
        f"   禁止建/补实现 '{package}' — {project} CLAUDE.md 明确历史别名. "
        f"正确做法: 删 BOS 声明 (同 sharedbrain).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
