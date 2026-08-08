"""规范检出定位 — 写机器级配置的工具必须用它, 不要 __file__ 反推。

2026-08-08 两起事故的共同根因: 工具用 `Path(__file__).resolve().parents[N]`
推导仓库根, 于是在哪个 worktree 里跑就把路径写成那个 worktree 的。worktree
是临时的, 而 ~/Library/LaunchAgents、~/.config 这些是机器级、长期存在的 ——
把临时路径写进去, 等 worktree 被清理, 配置就成了死路径, 而且**当场看不出来**。

判据很简单:
  只读仓内文件            → __file__ 反推没问题, 跟随当前检出才对
  写仓外(机器级)路径      → 必须 canonical_root(), 锚定规范检出
"""

from __future__ import annotations

import os
from pathlib import Path

MARKER = Path("docs") / "project-registry.yaml"


def canonical_root() -> Path:
    """规范检出根目录。优先 OMOSTATION_ROOT, 其次 ~/Workspace。"""
    env = os.environ.get("OMOSTATION_ROOT")
    if env and (Path(env) / MARKER).is_file():
        return Path(env)
    home_ws = Path.home() / "Workspace"
    if (home_ws / MARKER).is_file():
        return home_ws
    raise RuntimeError(
        "定位不到规范检出 (~/Workspace 或 $OMOSTATION_ROOT)。"
        "写机器级配置的工具不能退回 __file__ 反推 —— 那会把 worktree 路径写死进配置。"
    )


def is_worktree(path: Path | str) -> bool:
    """该路径是否位于某个临时 worktree(而非规范检出)。"""
    p = Path(path).resolve()
    try:
        return p != canonical_root().resolve() and not str(p).startswith(str(canonical_root().resolve()))
    except RuntimeError:
        return False
