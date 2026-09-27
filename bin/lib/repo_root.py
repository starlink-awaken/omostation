"""规范检出定位 — 写机器级配置的工具必须用它, 不要 __file__ 反推。

2026-08-08 两起事故的共同根因: 工具用 `Path(__file__).resolve().parents[N]`
推导仓库根, 于是在哪个 worktree 里跑就把路径写成那个 worktree 的。worktree
是临时的, 而 ~/Library/LaunchAgents、~/.config 这些是机器级、长期存在的 ——
把临时路径写进去, 等 worktree 被清理, 配置就成了死路径, 而且**当场看不出来**。

判据很简单:
  只读仓内文件            → code_root() (__file__ 反推), 跟随当前检出才对
  写仓外(机器级)路径      → 必须 canonical_root(), 锚定规范检出
  写运行态(ledger/state)  → state_root(), 由 profile 声明, 未声明时等于 code_root()
  定位运行时安装位        → install_root(), 未落位返回 None; 它只回答"在哪", 不改任何解析结果

第四条 placement 判据 (BET-Y2Q4-T10-209, 交付运行态):
  机器级、长于单检出的交付运行态 (delivery runs/locks/events, 即
  `.omo/_delivery/agent-workflows/` 下的 runs/ locks/ events.jsonl)
    → 已声明 env (OMOSTATION_STATE_ROOT) 用之, 否则 canonical_root();
  linked worktree 内以 symlink 呈现 —— worktree remove 只 unlink 该链接, 不跟随
  删除目标内容 (canonical 侧保留);
  禁止 `rm -rf <link>/` —— 尾斜杠会让 rm 跟随 symlink 删除目标目录的内容。

ADR-0456: 开发与运行时同在一套检出, 所以开发动作直接打击在跑的系统。解法不是搬家,
是先把"根"参数化 —— code_root 跟随检出(保证开发环境随时可跑), state_root 由
$OMOSTATION_STATE_ROOT 声明(保证运行态可独立落位)。本轮只提供机制与取值口径,
把 profile 值真正写进安装位是 B4。

B4a (2026-09-27) 落了安装位本体 (~/.local/opt/omostation —— 独立 clone, 不是 worktree) 并
加上 install_root() 定位器; canonical_root() 的解析结果**刻意未动**。43 个 launchd plist 仍
指向 ~/Workspace 且正在跑, 把解析器改道等于让所有写机器级配置的工具在同一次 commit 后静默
换目标 —— 那是 B4b 的切换, 不属于这一轮。
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from pathlib import Path

MARKER = Path("docs") / "project-registry.yaml"

STATE_ROOT_ENV = "OMOSTATION_STATE_ROOT"
LEDGER_DB_ENV = "OMO_EVENT_LEDGER_DB"
LEDGER_RELATIVE = Path("runtime") / "omo" / "event-ledger.sqlite3"

INSTALL_ROOT_ENV = "OMOSTATION_INSTALL_ROOT"
INSTALL_ROOT_RELATIVE = Path(".local") / "opt" / "omostation"


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


def install_root() -> Path | None:
    """运行时代码安装位; 未落位返回 None。

    失败模式必须是 None 而不是异常: 这是定位器, 调用方在"尚未安装"这台机器上
    (CI、别人的机器)也要能正常跑完。
    """
    env = os.environ.get(INSTALL_ROOT_ENV)
    candidate = Path(env).expanduser() if env else Path.home() / INSTALL_ROOT_RELATIVE
    return candidate if (candidate / MARKER).is_file() else None


def roots_report() -> dict[str, object]:
    """回答"我现在在哪个根" —— CLI 与测试共用这一份, 不在两处各算各的。"""
    cwd = Path.cwd()
    located = install_root()
    try:
        canonical: Path | None = canonical_root()
    except RuntimeError:
        canonical = None
    return {
        "code_root": str(code_root()),
        "canonical_root": str(canonical) if canonical else None,
        "state_root": str(state_root()),
        "state_root_declared": bool(os.environ.get(STATE_ROOT_ENV)),
        "event_ledger_path": str(event_ledger_path()),
        "event_ledger_override": bool(os.environ.get(LEDGER_DB_ENV)),
        "install_root": str(located) if located else None,
        "cwd_is_install_root": bool(located and cwd.resolve() == located.resolve()),
        "cwd_is_canonical_root": bool(canonical and cwd.resolve() == canonical.resolve()),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="报告本检出的各层根 (ADR-0456)。只读, 不写任何配置。"
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON 而非 key<TAB>value 行")
    args = parser.parse_args(argv)
    report = roots_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for key, value in report.items():
            print(f"{key}\t{'-' if value is None else value}")
    return 0


__all__ = (
    "INSTALL_ROOT_ENV",
    "INSTALL_ROOT_RELATIVE",
    "LEDGER_DB_ENV",
    "LEDGER_RELATIVE",
    "MARKER",
    "STATE_ROOT_ENV",
    "canonical_root",
    "code_root",
    "event_ledger_path",
    "install_root",
    "is_worktree",
    "roots_report",
    "state_root",
)


if __name__ == "__main__":
    raise SystemExit(main())
