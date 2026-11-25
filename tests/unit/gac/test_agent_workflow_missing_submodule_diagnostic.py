"""`bin/agent-workflow.py` 在依赖子模块不可用时必须给可读诊断，而不是裸 traceback。

门禁里 8 个 `agent-workflow-*` check 都执行这个脚本。子模块未检出时旧行为是
模块级 `from omo.workflow import ...` 抛 ModuleNotFoundError —— stdout 为空、
stderr 是 traceback，**与真回归同形**（`tests/test_agent_workflow.py` 两处守卫的
docstring 记的就是这个现象）。这里钉住三种形态：目录缺席、只有空目录（半初始化）、
包就位。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "bin" / "agent-workflow.py"


def _bare_workspace(tmp_path: Path) -> Path:
    """一棵只有该脚本、没有任何子模块 src 的树（WORKSPACE 由 __file__ 解析）。"""
    root = tmp_path / "ws"
    (root / "bin").mkdir(parents=True)
    shutil.copy2(SCRIPT, root / "bin" / "agent-workflow.py")
    return root


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "bin/agent-workflow.py", "lint"],
        cwd=root,
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=60,
    )


def test_absent_src_dir_is_readable_not_traceback(tmp_path):
    result = _run(_bare_workspace(tmp_path))
    assert result.returncode == 2
    assert result.stdout == ""
    assert "projects/omo/src 未检出" in result.stderr
    assert "git submodule update --init projects/omo" in result.stderr
    assert "Traceback" not in result.stderr


def test_half_initialized_empty_src_dir_is_also_reported(tmp_path):
    """目录在、包不在（claim 快速路径 / 半初始化）同样要报，不能只判 is_dir。"""
    root = _bare_workspace(tmp_path)
    (root / "projects" / "omo" / "src").mkdir(parents=True)

    result = _run(root)
    assert result.returncode == 2
    assert "projects/omo/src 未检出" in result.stderr
    assert "Traceback" not in result.stderr


def test_omo_present_without_ecos_still_proceeds(tmp_path):
    """反向判据：`projects/ecos` 是**可选**依赖。

    CI 的 interface-check 树正是「有 omo、无 ecos」—— 一视同仁会让 `status`
    这类命令无故 exit 2（实测把 test_agent_workflow.py 的
    test_worktree_status_and_closeout_read_through_canonical_anchor 弄红）。
    """
    root = _bare_workspace(tmp_path)
    pkg = root / "projects" / "omo" / "src" / "omo"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")

    result = _run(root)
    assert "未检出" not in result.stderr, "可选依赖缺席不该触发该诊断"
    assert result.returncode != 2
