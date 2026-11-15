"""`gac-worktree.sh` 打印给人的命令里的仓内路径必须真的存在、形状必须对。

契约来源：2026-11-16 实测 —— 脚本的 `echo` 指引里把路径写成了
`bin/gac-gac-worktree.sh`（正确 `bin/gac/gac-worktree.sh`，`gac-` 前缀抄了两遍），
以及 `bin/gac-worktree.sh`（漏了 `gac/` 这一层）。照抄的人直接撞
`No such file or directory`。

两把尺：
  · **形状尺** —— `bin/gac-<名>` 一定是把目录写成了名字（本仓布局是
    `bin/<组>/<名>`，可执行体在 `bin/gac/…`）；
  · **存在性尺** —— `echo`/`printf` 行里的仓内路径（`bin|lib|tests|runtime|docs|
    protocols|.omo` 开头、`.sh/.py/.yaml/.yml/.md` 结尾）必须真实存在。

刻意只扫**输出行**，不扫注释、也不扫本脚本自身的 `$SCRIPT_DIR/../…` 相对路径
（初版全文件扫会误报 shebang `bin/bash`、`lib/repo_root.py` 等 9 处）。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "gac" / "gac-worktree.sh"

# `bin/<组>/<名>` 是本仓布局; `bin/gac-<名>` 是把目录写成了名字。
BAD_SHAPE_RE = re.compile(r"\bbin/gac-[A-Za-z0-9_.-]+")
PATH_RE = re.compile(
    r"\b((?:bin|lib|tests|runtime|docs|protocols|\.omo)/"
    r"[A-Za-z0-9_./-]+\.(?:sh|py|yaml|yml|md))"
)
ADVICE_RE = re.compile(r"\b(?:echo|printf)\b")


def advice_lines(script_text: str) -> list[tuple[int, str]]:
    """所有 `echo`/`printf` 行（排除注释行）—— 这些是给人看/抄的文本。"""
    out: list[tuple[int, str]] = []
    for lineno, line in enumerate(script_text.splitlines(), 1):
        if line.strip().startswith("#"):
            continue
        if ADVICE_RE.search(line):
            out.append((lineno, line))
    return out


def test_advice_has_no_gac_dash_paths() -> None:
    bad = [
        (lineno, line.strip())
        for lineno, line in advice_lines(SCRIPT.read_text(encoding="utf-8"))
        if BAD_SHAPE_RE.search(line)
    ]
    assert bad == [], "`bin/gac-<名>` 形状一定是把目录写成了名字: " + repr(bad)


def test_advice_paths_exist() -> None:
    missing: list[str] = []
    for lineno, line in advice_lines(SCRIPT.read_text(encoding="utf-8")):
        for match in PATH_RE.finditer(line):
            rel = match.group(1)
            if "$" in rel or not (ROOT / rel).exists():
                missing.append(f"{lineno}: {rel}")
    assert missing == [], "输出行里的路径在仓里不存在: " + "; ".join(missing)


def test_extractor_finds_advice_lines() -> None:
    """自证: 抽取器真的拿到了输出行（否则上面两条是空绿）。"""
    lines = advice_lines(SCRIPT.read_text(encoding="utf-8"))
    assert lines, "没抽到任何 echo/printf 行 —— 抽取器失效"
    joined = " ".join(line for _n, line in lines)
    assert "gac-worktree.sh" in joined
