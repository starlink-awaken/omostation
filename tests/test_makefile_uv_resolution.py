"""Makefile 的 `uv` 解析必须对**最小 PATH** 健壮 (cron 场景).

实测 (2026-11-09): cron 的最小 PATH 是 `/usr/bin:/bin`, 不含 `uv` 所在的
`~/.local/bin` 与 `/opt/homebrew/bin` ⇒ 任何命令里含 `uv run` 的 `make <target>`
在 cron 下直接 `make: uv: No such file or directory`。crontab 的 `hygiene-dir`
(每日 05:00, 走 `root-directory-governance`) 正是这条路径, 日志里连续报该错。

同源: `projects/l4-kernel/scripts/harness-cron.sh` 用裸 `uv` 静默全 ERR
(omostation-l4-kernel#21)。
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"


def _minimal_env(path: str = "/usr/bin:/bin") -> dict[str, str]:
    return {"PATH": path, "HOME": os.environ.get("HOME", "/")}


def test_uv_resolves_to_absolute_path_under_minimal_cron_path() -> None:
    """最小 PATH 下 make 打印的 uv 命令必须是**绝对路径**, 不能是裸 `uv`。"""
    result = subprocess.run(
        ["make", "-n", "root-directory-governance"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=_minimal_env(),
        timeout=60,
        check=False,
    )
    out = result.stdout + result.stderr
    assert "/uv run" in out, f"`uv` 未解析成绝对路径 (cron 下会 No such file): {out[:300]}"


def test_target_runs_under_minimal_cron_path() -> None:
    """端到端: 最小 PATH 下 `root-directory-governance` 真的跑起来。"""
    result = subprocess.run(
        ["make", "root-directory-governance"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=_minimal_env(),
        timeout=180,
        check=False,
    )
    out = result.stdout + result.stderr
    assert "No such file or directory" not in out, out[-300:]
    assert result.returncode == 0, out[-300:]


def test_uv_still_resolves_normally_when_on_path() -> None:
    """正控制: PATH 里有 uv 时解析到它 (回退分支不该抢在前面)。"""
    uv = subprocess.run(
        ["bash", "-lc", "command -v uv"],
        capture_output=True, text=True, timeout=30, check=False,
    ).stdout.strip()
    if not uv:
        return  # 本机没装 uv, 跳过正控制
    result = subprocess.run(
        ["make", "-n", "root-directory-governance"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    out = result.stdout + result.stderr
    assert uv in out, f"PATH 上有 uv 却没被用上: {out[:200]}"
