"""`onboard` 打印给人的命令里的仓内路径必须真的存在。

契约来源：2026-11-16 实测 —— `bin/gac/gac-worktree.sh` 的 `onboard` 指引把路径
写成了 `bin/gac-gac-worktree.sh`（正确是 `bin/gac/gac-worktree.sh`）：
`gac-` 前缀被抄了两遍。照抄的人直接撞 `No such file or directory`。

判据取**路径形状**而不是拼写清单：`bin/` 下的可执行体在本仓布局里是
`bin/<组>/<名>`（`bin/gac/…`），所以 `bin/gac-<名>` 这种「横杠接在 gac 后」
的形状一定是把目录写成了名字。此用例只查 `onboard` 分支里**给人抄的命令**
（`echo` 行），不查注释与本脚本自身的 `$SCRIPT_DIR/../…` 相对路径。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "gac" / "gac-worktree.sh"

# `bin/<组>/<名>` 是本仓布局; `bin/gac-<名>` 是把目录写成了名字。
BAD_SHAPE_RE = re.compile(r"\bbin/gac-[A-Za-z0-9_.-]+")
PATH_RE = re.compile(r"\b(bin/[A-Za-z0-9_./-]+\.(?:sh|py))")


def _onboard_echo_lines(script_text: str) -> list[tuple[int, str]]:
    """抽 `onboard)` 派发分支里、到下一个 `;;` 为止的 echo 行。"""
    lines = script_text.splitlines()
    try:
        start = next(
            i for i, line in enumerate(lines) if line.startswith("  onboard)")
        )
    except StopIteration:
        return []
    out: list[tuple[int, str]] = []
    for i in range(start, len(lines)):
        if i > start and lines[i].strip() == ";;":
            break
        if "echo" in lines[i]:
            out.append((i + 1, lines[i]))
    return out


def test_onboard_advice_has_no_gac_dash_paths() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    bad = [
        (lineno, line.strip())
        for lineno, line in _onboard_echo_lines(text)
        if BAD_SHAPE_RE.search(line)
    ]
    assert bad == [], "`bin/gac-<名>` 形状一定是把目录写成了名字: " + repr(bad)


def test_onboard_advice_paths_exist() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    missing: list[str] = []
    for lineno, line in _onboard_echo_lines(text):
        for match in PATH_RE.finditer(line):
            rel = match.group(1)
            if "$" in rel or not (ROOT / rel).exists():
                missing.append(f"{lineno}: {rel}")
    assert missing == [], "onboard 指引里的路径在仓里不存在: " + "; ".join(missing)


def test_extractor_finds_the_advice_block() -> None:
    """自证: 抽取器真的拿到了 onboard 的 echo 行（否则上面两条是空绿）。"""
    lines = _onboard_echo_lines(SCRIPT.read_text(encoding="utf-8"))
    assert lines, "没抽到 onboard 分支的 echo 行 —— 抽取器失效"
    joined = " ".join(line for _n, line in lines)
    assert "gac-worktree.sh" in joined
