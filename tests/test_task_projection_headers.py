"""任务投影头部悬挂引用检查 — 回归测试.

2026-09-19 实证: `.omo/tasks/*/bet-*.yaml` 头部写着"重跑
`python bin/plan/bet-to-task.py --apply`", 而该路径在 main 上从未存在
(生成器只以 bin/_archive/bet-to-task.py 入库) —— 照指示操作者必撞空。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "bin/gac/check-task-projection-headers.py"


def _load():
    spec = importlib.util.spec_from_file_location("task_proj_headers", TOOL)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["task_proj_headers"] = mod
    spec.loader.exec_module(mod)
    return mod


def _repo(tmp_path: Path) -> Path:
    """造一个最小仓库骨架: 有 bin/_archive/ 但无 bin/plan/."""
    (tmp_path / "bin" / "_archive").mkdir(parents=True)
    (tmp_path / "bin" / "_archive" / "bet-to-task.py").write_text("# archived\n")
    (tmp_path / "bin" / "plan").mkdir(parents=True)
    (tmp_path / "bin" / "plan" / "sync-planned-to-done.py").write_text("# active\n")
    (tmp_path / ".omo" / "tasks" / "done").mkdir(parents=True)
    return tmp_path


def _task(repo: Path, name: str, body: str) -> Path:
    p = repo / ".omo" / "tasks" / "done" / name
    p.write_text(body, encoding="utf-8")
    return p


# ── 核心: 命令上下文里的悬挂路径 ─────────────────────────


def test_flags_dangling_command_reference(tmp_path):
    repo = _repo(tmp_path)
    _task(repo, "a.yaml",
          "# AUTOGEN\n"
          "# 改台账后重跑: uv run --with pyyaml python bin/plan/bet-to-task.py --apply\n"
          "id: X\n")
    tool = _load()
    r = tool.scan(tasks_dir=repo / ".omo/tasks", root=repo)
    assert len(r["dangling"]) == 1
    d = r["dangling"][0]
    assert d["ref"] == "bin/plan/bet-to-task.py"
    assert d["line"] == 2


def test_passes_when_reference_exists(tmp_path):
    """指向真实存在的脚本 → 放行."""
    repo = _repo(tmp_path)
    _task(repo, "a.yaml", "# 对账: python3 bin/plan/sync-planned-to-done.py\nid: X\n")
    tool = _load()
    assert tool.scan(tasks_dir=repo / ".omo/tasks", root=repo)["dangling"] == []


def test_archived_path_is_valid_when_it_exists(tmp_path):
    """bin/_archive/ 下真实存在的路径不算悬挂 (归档≠失效)."""
    repo = _repo(tmp_path)
    _task(repo, "a.yaml", "# 生成器已归档: python3 bin/_archive/bet-to-task.py --help\nid: X\n")
    tool = _load()
    assert tool.scan(tasks_dir=repo / ".omo/tasks", root=repo)["dangling"] == []


# ── 误报防护 (v1 实测踩过的坑) ───────────────────────────


def test_prose_mention_not_flagged(tmp_path):
    """散文提及 (无解释器关键字) 不得判为悬挂引用.

    v1 初版把注释里任何 *.py 当路径 → 对 .omo/tasks/done/TASK-117310A1.yaml
    的散文注释 ("(omo/resident/cell.py)", "扫 cli.py 的命令路由表") 产生 6 处误报。
    """
    repo = _repo(tmp_path)
    _task(repo, "a.yaml",
          "# 关键细节: 物理上就在 (omo/resident/cell.py)\n"
          "# 需要扫 cli.py 的命令路由表, 而不是扫跨项目 import 图\n"
          "# workflow_mesh.py 本身是事件溯源状态机\n"
          "id: X\n")
    tool = _load()
    assert tool.scan(tasks_dir=repo / ".omo/tasks", root=repo)["dangling"] == []


def test_non_comment_line_not_scanned(tmp_path):
    """YAML 值里的路径不查 (只查注释头部)."""
    repo = _repo(tmp_path)
    _task(repo, "a.yaml", "id: X\nevidence: python3 bin/nope/gone.py\n")
    tool = _load()
    assert tool.scan(tasks_dir=repo / ".omo/tasks", root=repo)["dangling"] == []


def test_absolute_and_url_paths_skipped(tmp_path):
    repo = _repo(tmp_path)
    _task(repo, "a.yaml",
          "# 参考: python3 /usr/local/bin/thing.py\n"
          "# 文档: bash http://example.com/setup.sh\n"
          "id: X\n")
    tool = _load()
    assert tool.scan(tasks_dir=repo / ".omo/tasks", root=repo)["dangling"] == []


# ── 退出码与边界 ─────────────────────────────────────────


def test_main_exit_codes(tmp_path, monkeypatch):
    tool = _load()
    repo = _repo(tmp_path)
    monkeypatch.setattr(tool, "TASKS_DIR", repo / ".omo/tasks")
    monkeypatch.setattr(tool, "_ROOT", repo)

    _task(repo, "ok.yaml", "# 对账: python3 bin/plan/sync-planned-to-done.py\n")
    assert tool.main(["--json"]) == 0

    _task(repo, "bad.yaml", "# 重跑: python3 bin/plan/bet-to-task.py --apply\n")
    assert tool.main(["--json"]) == 1


def test_missing_tasks_dir_is_not_failure(tmp_path):
    tool = _load()
    r = tool.scan(tasks_dir=tmp_path / "nope", root=tmp_path)
    assert r["scanned"] == 0 and r["dangling"] == []


# ── 真实仓库 ─────────────────────────────────────────────


def test_real_repo_has_no_dangling_command_refs():
    """本仓必须干净 —— 这正是本 PR 修掉的那类残留."""
    tool = _load()
    r = tool.scan()
    assert r["dangling"] == [], (
        "任务投影头部存在悬挂引用: "
        + ", ".join(f"{d['file']}:{d['line']}→{d['ref']}" for d in r["dangling"])
    )
    assert r["scanned"] > 0
