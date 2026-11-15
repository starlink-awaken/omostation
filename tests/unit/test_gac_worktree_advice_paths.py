"""非归档 shell 脚本**输出给人抄的**仓内路径必须真实存在、形状必须对。

契约来源：2026-11-16 实测，同一条尺在两处抓到真缺陷 ——

  · `bin/gac/gac-worktree.sh` 的 `onboard` / `release` 指引：
    `bin/gac-gac-worktree.sh`（`gac-` 前缀抄了两遍）、`bin/gac-worktree.sh`（漏层）；
  · `bin/gac/gac-worktree-guard.sh` 的 `--check` 指引**与** `--enforce` 的实际执行：
    都指向 `bin/gac/gac-worktree-prune.sh` —— 该脚本**已归档**到 `bin/_archive/`，
    现行等价物是 `bin/gac/gac-branch-prune.sh`（= `make worktree-prune`）。
    即 `--enforce` 不只是建议错，是**执行了一个不存在的脚本**。

两把尺：
  · **形状尺** —— `bin/gac-<名>` 一定是把目录写成了名字（本仓布局是
    `bin/<组>/<名>`，可执行体在 `bin/gac/…`）；
  · **存在性尺** —— `echo`/`printf` 行里的仓内路径（`bin|lib|tests|runtime|docs|
    protocols|.omo` 开头、`.sh/.py/.yaml/.yml/.md/.json` 结尾）必须真实存在。

范围刻意**只取非归档的 `.sh`**：shell 里 `echo`/`printf` 无歧义；放到 `.py` 会
被 docstring 里的「捕获 print 输出」这类散文误报，也会把运行时产物
（`.omo/state/health.yaml`）当成缺陷。`bin/_archive/**` 是**故意**的死代码，排除。
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# `bin/<组>/<名>` 是本仓布局; `bin/gac-<名>` 是把目录写成了名字。
BAD_SHAPE_RE = re.compile(r"\bbin/gac-[A-Za-z0-9_.-]+")
PATH_RE = re.compile(
    r"[\"' =]((?:bin|lib|tests|runtime|docs|protocols|\.omo)/"
    r"[A-Za-z0-9_./-]+\.(?:sh|py|yaml|yml|md|json))"
)
ADVICE_RE = re.compile(r"\becho\b|\bprintf\b")


def tracked_shell_scripts(root: Path = ROOT) -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "bin"], cwd=root, capture_output=True, text=True, check=False
    ).stdout.split()
    return [
        root / rel
        for rel in out
        if rel.endswith(".sh") and not rel.startswith("bin/_archive/")
    ]


def advice_lines(root: Path = ROOT) -> list[tuple[str, int, str]]:
    """所有非归档 `.sh` 的 `echo`/`printf` 行（排除注释行）。"""
    hits: list[tuple[str, int, str]] = []
    for path in tracked_shell_scripts(root):
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            if line.strip().startswith("#"):
                continue
            if ADVICE_RE.search(line):
                hits.append((str(path.relative_to(root)), lineno, line))
    return hits


def _is_gitignored(rel: str) -> bool:
    """gitignored = 设计上的生成态/运行态（干净检出里本就不存在），不算缺陷。

    例: `.omo/state/system.yaml` 被 `.gitignore:304` 忽略 —— 指引里提到它是
    **告诉用户它是生成态**，不是让人去跑一个不存在的路径。
    （判据用 git 自己而不是维护豁免名单：gitignore 就是本仓对「故意缺席」的定义。）
    """
    return (
        subprocess.run(
            ["git", "check-ignore", "-q", rel], cwd=ROOT, capture_output=True, check=False
        ).returncode
        == 0
    )


def test_advice_has_no_gac_dash_paths() -> None:
    bad = [
        (rel, lineno, line.strip())
        for rel, lineno, line in advice_lines()
        if BAD_SHAPE_RE.search(line)
    ]
    assert bad == [], "`bin/gac-<名>` 形状一定是把目录写成了名字: " + repr(bad)


def test_advice_paths_exist() -> None:
    missing: list[str] = []
    for rel, lineno, line in advice_lines():
        for match in PATH_RE.finditer(line):
            target = match.group(1)
            if "$" in target or "{" in target or "..." in target:
                continue
            if (ROOT / target).exists() or _is_gitignored(target):
                continue
            missing.append(f"{rel}:{lineno}: {target}")
    assert missing == [], "输出行里的路径在仓里不存在: " + "; ".join(missing)


SIBLING_EXEC_RE = re.compile(
    r'bash\s+"\$\(dirname\s+"\$0"\)/([A-Za-z0-9_.-]+\.sh)"'
)


def test_sibling_script_executions_exist() -> None:
    """`bash "$(dirname "$0")/<脚本>"` 是**实际执行**，目标必须存在。

    与 `test_advice_paths_exist` 分开: 那把尺查的是**给人抄的文本**里的
    `bin/...` 路径；这把查的是**机器要跑的同目录脚本**。
    `gac-worktree-guard.sh --enforce` 的 bug 正是这一类 —— 它执行了一个
    已归档的 `gac-worktree-prune.sh`，而不只是建议错。
    """
    missing: list[str] = []
    for path in tracked_shell_scripts():
        rel = str(path.relative_to(ROOT))
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            if line.strip().startswith("#"):
                continue
            for match in SIBLING_EXEC_RE.finditer(line):
                if not (path.parent / match.group(1)).exists():
                    missing.append(f"{rel}:{lineno}: {match.group(1)}")
    assert missing == [], "要执行的同目录脚本不存在: " + "; ".join(missing)


def test_extractor_finds_advice_lines() -> None:
    """自证: 抽取器真的拿到了输出行（否则上面两条是空绿）。"""
    lines = advice_lines()
    assert lines, "没抽到任何 echo/printf 行 —— 抽取器失效"
    joined = " ".join(line for _r, _n, line in lines)
    assert "gac-worktree" in joined
