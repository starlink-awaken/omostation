"""「输入没备齐」判据的**单一实现**，供门禁与各 check 共用。

同一条口径原先在四处各写一份（只差全局根的名字），本轮收敛到这里：

- 未检出的子模块（干净检出 / claim 快速路径 / 半初始化）
- gitignore 覆盖的生成态
- 已归档旧路径（``bin/_archive/``）

另有 ``unchecked_gitlinks()``：直接问 ``git submodule status --recursive``
（含嵌套），取 ``-`` 前缀 —— 扫描面完整性判定用它，不解析 ``.gitmodules``。

**纪律**：新增同类判据请复用本模块，不要再抄一份 —— 抄出来的份数就是下一次
口径漂移的份数。所有路径相对 ``workspace``；仓外绝对路径按构造判 False。
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def repo_relative(raw: str, workspace: Path) -> str | None:
    """仓内路径 → 相对 ``workspace`` 的形式；仓外 → None。"""
    p = Path(raw)
    if not p.is_absolute():
        return raw
    try:
        return str(p.relative_to(workspace))
    except ValueError:
        return None


def input_absent(rel: str, workspace: Path) -> bool:
    """该路径的缺席属**输入没备齐**，不是缺陷。

    与调用方各自维护的副本同解（gac-healthcheck / doc-link-check /
    auto-fix-loop / check-capability-ownership 已于 2026-11-25 收敛到此）。
    """
    rel = repo_relative(str(rel), workspace)
    if rel is None:
        return False
    parts = Path(rel).parts
    if len(parts) >= 2 and parts[0] == "projects":
        return not (workspace / "projects" / parts[1] / ".git").exists()
    if rel.startswith("bin/_archive/"):
        return True
    # gitignore 覆盖 ⇒ 按构造不是仓库的对象（生成态/运行态）。
    try:
        return subprocess.run(
            ["git", "check-ignore", "-q", "--no-index", rel],
            cwd=workspace,
            capture_output=True,
            timeout=15,
            check=False,
        ).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def parse_unchecked(status_text: str) -> list[str]:
    """``git submodule status --recursive`` 输出里 ``-`` 前缀（未初始化）的路径。"""
    out: list[str] = []
    for line in status_text.splitlines():
        if line.startswith("-"):
            parts = line[1:].split()
            if len(parts) >= 2:
                out.append(parts[1])
    return out


def unchecked_gitlinks(workspace: Path) -> list[str]:
    """工作树里**未初始化**的子模块路径（含嵌套 —— 问 git 本身）。

    这些子模块的内容不在本检出里 ⇒ 任何基于全量登记的判定都无法成立
    （读不到消费者，就不能说它「已移除」）。
    """
    try:
        res = subprocess.run(
            ["git", "submodule", "status", "--recursive"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if res.returncode != 0:
        return []
    return parse_unchecked(res.stdout)
