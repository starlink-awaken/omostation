"""规范检出定位 — 写机器级配置的工具必须用它, 不要 __file__ 反推。

2026-08-08 两起事故的共同根因: 工具用 `Path(__file__).resolve().parents[N]`
推导仓库根, 于是在哪个 worktree 里跑就把路径写成那个 worktree 的。worktree
是临时的, 而 ~/Library/LaunchAgents、~/.config 这些是机器级、长期存在的 ——
把临时路径写进去, 等 worktree 被清理, 配置就成了死路径, 而且**当场看不出来**。

判据很简单:
  只读仓内文件            → code_root() (__file__ 反推), 跟随当前检出才对
  写仓外(机器级)路径      → 必须 canonical_root(), 锚定规范检出
  写运行态(ledger/state)  → state_root(), 由 profile 声明, 未声明时等于 code_root()

ADR-0456: 开发与运行时同在一套检出, 所以开发动作直接打击在跑的系统。解法不是搬家,
是先把"根"参数化 —— code_root 跟随检出(保证开发环境随时可跑), state_root 由
$OMOSTATION_STATE_ROOT 声明(保证运行态可独立落位)。本轮只提供机制与取值口径,
把 profile 值真正写进安装位是 B4。
"""

from __future__ import annotations

import os
from pathlib import Path

MARKER = Path("docs") / "project-registry.yaml"

STATE_ROOT_ENV = "OMOSTATION_STATE_ROOT"
LEDGER_DB_ENV = "OMO_EVENT_LEDGER_DB"
LEDGER_RELATIVE = Path("runtime") / "omo" / "event-ledger.sqlite3"


def code_root() -> Path:
    """当前检出根 (bin/lib/repo_root.py 往上两层)。读仓内文件用它。"""
    return Path(__file__).resolve().parents[2]


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


def state_root() -> Path:
    """运行态写入根。未声明 profile 时等于 code_root(), 逐字节复现历史路径。"""
    env = os.environ.get(STATE_ROOT_ENV)
    if env:
        return Path(env).expanduser().absolute()
    return code_root()


def event_ledger_path() -> Path:
    """事件 ledger 路径。OMO_EVENT_LEDGER_DB 优先 (canonical 环境变量名)。"""
    env = os.environ.get(LEDGER_DB_ENV)
    if env:
        return Path(env).expanduser()
    return state_root() / LEDGER_RELATIVE


def is_worktree(path: Path | str) -> bool:
    """该路径是否位于某个临时 worktree(而非规范检出)。"""
    p = Path(path).resolve()
    try:
        return p != canonical_root().resolve() and not str(p).startswith(str(canonical_root().resolve()))
    except RuntimeError:
        return False


__all__ = (
    "LEDGER_DB_ENV",
    "LEDGER_RELATIVE",
    "MARKER",
    "STATE_ROOT_ENV",
    "canonical_root",
    "code_root",
    "event_ledger_path",
    "is_worktree",
    "state_root",
)
