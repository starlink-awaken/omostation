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
  读运行态投影(health/brief/governance-data…) →
    projection_read(code_root, name, state_root=state_root()),
                            映射单源自 .omo/_truth/registry/runtime-projections.yaml,
                            不要写死 legacy 路径 —— ADR-0129 Phase 2 之后 legacy 那份
                            在 fresh checkout 里根本不存在, 在生产机上又是冻结的。

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
from pathlib import Path, PurePosixPath

MARKER = Path("docs") / "project-registry.yaml"

STATE_ROOT_ENV = "OMOSTATION_STATE_ROOT"
LEDGER_DB_ENV = "OMO_EVENT_LEDGER_DB"
LEDGER_RELATIVE = Path("runtime") / "omo" / "event-ledger.sqlite3"

INSTALL_ROOT_ENV = "OMOSTATION_INSTALL_ROOT"
INSTALL_ROOT_RELATIVE = Path(".local") / "opt" / "omostation"

PROJECTIONS_REGISTRY_RELATIVE = Path(".omo") / "_truth" / "registry" / "runtime-projections.yaml"

# Used when the registry itself is not in this checkout (fresh clone of a tool
# that ships without .omo). Same values runtime-projections.yaml declares today.
_PROJECTION_FALLBACK_RELS: dict[str, tuple[str, str]] = {
    "health": (".omo/state/runtime/health.yaml", ".omo/state/health.yaml"),
    "system_health": (".omo/state/runtime/system_health.yaml", ".omo/state/system_health.yaml"),
    "governance_data": (".omo/state/runtime/governance-data.json", ".omo/_control/governance-data.json"),
    "brief": (".omo/state/runtime/brief.md", "BRIEF.md"),
}


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


def _projection_registry(registry_root: Path | None = None) -> dict[str, tuple[str, str]]:
    """投影登记表: name → (canonical_rel, legacy_rel)。

    只读 canonical / legacy 两个键, 且不 import yaml —— meta-doctor 与 cron 用裸
    python3 跑, 依赖一旦变成 pyyaml 就会在那里 ImportError。登记表格式由
    tests/unit/test_projection_reader_resolution.py 拿 yaml.safe_load_all 逐名对拍钉住。
    """
    path = (registry_root or code_root()) / PROJECTIONS_REGISTRY_RELATIVE
    if not path.is_file():
        return dict(_PROJECTION_FALLBACK_RELS)

    table: dict[str, tuple[str, str]] = {}
    name: str | None = None
    in_block = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        key, sep, value = line.strip().partition(":")
        if not sep:
            continue
        value = value.strip().strip('"').strip("'")
        if indent == 0:
            in_block, name = (key == "projections"), None
            continue
        if not in_block:
            continue
        if indent == 2:
            name = key
            table[name] = ("", "")
        elif indent == 4 and name and key in ("canonical", "legacy"):
            canonical, legacy = table[name]
            table[name] = (value, legacy) if key == "canonical" else (canonical, value)
    return {k: v for k, v in table.items() if all(v)}


def projection_rels(name: str, *, registry_root: Path | None = None) -> tuple[str, str]:
    """已登记投影的 (canonical, legacy) 相对路径。

    返回相对路径而不是绝对路径: 每个读取方把自己那一侧的根 (--workspace /
    state_root / code_root) 锚上去, 于是映射只有一处真源, 解析仍跟着 profile 走。
    未登记的名字抛 KeyError —— 与 omo_paths.projection_path 同口径, 静默回退会把
    读错文件伪装成读到了。
    """
    rels = _projection_registry(registry_root).get(name)
    if rels is None:
        raise KeyError(f"Unknown runtime projection: {name}")
    return rels


def projection_name_for(relative: str | Path, *, registry_root: Path | None = None) -> str | None:
    """该相对路径若是某个投影的 legacy 位, 返回投影名; 否则 None。"""
    target = PurePosixPath(str(relative))
    for name, (_canonical, legacy) in _projection_registry(registry_root).items():
        if PurePosixPath(legacy) == target:
            return name
    return None


def projection_read(
    root: Path | str,
    name: str,
    *,
    registry_root: Path | None = None,
    state_root: Path | str | None = None,
) -> tuple[Path, str]:
    """读取侧解析: (该读哪个文件, 它是 canonical 还是 legacy)。

    canonical 挂 state_root (省略时与 root 相同), legacy 挂当前 checkout root。
    canonical 存在就读 canonical; 否则退回 legacy —— 那可能是旧检出自带的、
    也可能是根本没生成过的。**文件不存在不是错误**, 所以这里不判存在性,
    调用方拿 Path 自己判 absent, 从而把"没生成"和"跑过但老化"分开计。
    """
    base = Path(root)
    canonical_rel, legacy_rel = projection_rels(name, registry_root=registry_root)
    canonical = Path(state_root) / canonical_rel if state_root is not None else base / canonical_rel
    if canonical.is_file():
        return canonical, "canonical"
    return base / legacy_rel, "legacy"


def state_file_read(relative: str | Path, *, root: Path | str | None = None) -> Path:
    """同一个相对路径在两根都有份时的读取侧解析: state 根优先, 检出兜底。

    与 projection_read() 的区别是这里没有 canonical/legacy 两个名字 —— 它是同一个文件的
    "最后提交快照 + 运行态镜像" (.omo/state/system.yaml 这一类)。

    **只有 profile 显式声明了 `OMOSTATION_STATE_ROOT` 才去探 state 根**：未声明时
    state_root() == code_root()，历史行为就是 `root / relative`，直接返回它才与历史
    布局逐字节相同。这一条不是简化，是隔离测试的前提 —— 传给 `root=` 的 tmp 检出跟
    state_root()（真实检出）是两个不同目录，无条件优先 state 根会把 fixture 的读取
    劫持到宿主仓库那份文件上。
    """
    base = Path(root) if root is not None else code_root()
    if not os.environ.get(STATE_ROOT_ENV):
        return base / relative
    candidate = state_root() / relative
    return candidate if candidate.is_file() else base / relative


def state_dir_write(relative: str | Path) -> Path:
    """生成态**目录**的写侧解析: 一律挂 state 根 (未声明 profile 时 state_root()==code_root())。

    存在的理由是把「写面在调用时刻取根」这件事变成有名字的接缝 —— 写者一旦把路径写成
    模块级常量, 它就冻结在导入时刻的 env 上, 且没有任何测试会红 (ADR-0456 B5)。
    与 state_file_read() 的"缺副本不写"不同: 这里 mkdir 一份目录副本不会造出半份镜像。
    """
    return state_root() / Path(relative)


def state_dir_read(relative: str | Path, *, root: Path | str | None = None) -> Path:
    """生成态**目录**的读取侧解析: state 根该目录存在则优先, 否则退回当前检出。

    state_file_read() 的同族, 区别是这类面的文件名带日期 (brief-YYYYMMDD.json), 无法按
    单文件比对是否存在, 只能按**目录**定优先级。未声明 profile 时直接返回检出侧, 于是与
    历史布局逐字节相同 —— 同 state_file_read(): 这是隔离测试的前提, 不是简化。
    """
    base = Path(root) if root is not None else code_root()
    if not os.environ.get(STATE_ROOT_ENV):
        return base / Path(relative)
    candidate = state_root() / Path(relative)
    return candidate if candidate.is_dir() else base / Path(relative)


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
    "PROJECTIONS_REGISTRY_RELATIVE",
    "STATE_ROOT_ENV",
    "canonical_root",
    "code_root",
    "event_ledger_path",
    "install_root",
    "is_worktree",
    "projection_name_for",
    "projection_read",
    "projection_rels",
    "roots_report",
    "state_file_read",
    "state_root",
)


if __name__ == "__main__":
    raise SystemExit(main())
