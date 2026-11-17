"""zhixing-host-sync 必须报出「源真值来自哪棵树」。

债条目 ZHIXING-PUBLISH-EFFECT-PROVENANCE 障碍①: `check`/`plan` 拿**运行它的树**
当源真值, 而共享主检出可能任意陈旧 (实测 `~/Workspace` 落后 origin/main 数百个提交)
—— 此时源与运行根**同为旧版**, 逐文件比对自然 `in_sync`, 读数看起来像「已同步」。
2026-11-10 一次发布里, 回答「线上生效了没有」连续误判四次, 根因就是这条。

本文件自造 git 仓, 不读 host 状态。
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "bin/gac/zhixing-host-sync.py"

_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def _load():
    spec = importlib.util.spec_from_file_location("zhs_provenance", TOOL)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["zhs_provenance"] = mod
    spec.loader.exec_module(mod)
    return mod


def _git(repo: Path, *a: str) -> subprocess.CompletedProcess:
    env = {**os.environ, **_ENV}
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, env=env, check=False)


@pytest.fixture
def stale_tree(tmp_path: Path) -> dict[str, object]:
    """一棵**落后 origin/main** 的检出 (复刻陈旧的共享主树)。"""
    mod = _load()
    origin = tmp_path / "origin.git"
    origin.mkdir()
    _git(origin, "init", "-q", "--bare", "-b", "main")

    seed = tmp_path / "seed"
    seed.mkdir()
    _git(seed, "init", "-q", "-b", "main")
    (seed / "a.txt").write_text("1", encoding="utf-8")
    _git(seed, "add", "a.txt")
    _git(seed, "commit", "-q", "-m", "c1")
    c1 = _git(seed, "rev-parse", "HEAD").stdout.strip()
    _git(seed, "remote", "add", "origin", str(origin))
    _git(seed, "push", "-q", "origin", "main")

    (seed / "b.txt").write_text("2", encoding="utf-8")
    _git(seed, "add", "b.txt")
    _git(seed, "commit", "-q", "-m", "c2")
    c2 = _git(seed, "rev-parse", "HEAD").stdout.strip()
    _git(seed, "push", "-q", "origin", "main")

    tree = tmp_path / "tree"
    _git(tmp_path, "clone", "-q", str(origin), str(tree))
    _git(tree, "checkout", "-q", "--detach", c1)
    return {"mod": mod, "tree": tree, "c1": c1, "c2": c2, "tmp": tmp_path}


def test_probe_reports_stale_source_tree(stale_tree, monkeypatch):
    """落后 origin/main 的树必须被点名 —— 否则 in_sync 是假安心。"""
    mod = stale_tree["mod"]
    monkeypatch.setattr(mod, "_ROOT", stale_tree["tree"])
    probe = mod.source_tree_probe()
    assert probe["root"] == str(stale_tree["tree"])
    assert probe["head"] == stale_tree["c1"]
    assert probe["origin_main"] == stale_tree["c2"]
    assert probe["behind_origin_main"] == 1
    assert probe["stale"] is True, "落后 origin/main 的源树必须标 stale"


def test_probe_not_stale_when_head_is_origin_main(stale_tree, monkeypatch):
    mod = stale_tree["mod"]
    _git(stale_tree["tree"], "checkout", "-q", "--detach", stale_tree["c2"])
    monkeypatch.setattr(mod, "_ROOT", stale_tree["tree"])
    probe = mod.source_tree_probe()
    assert probe["behind_origin_main"] == 0
    assert probe["stale"] is False


def test_probe_degrades_to_null_outside_git(stale_tree, monkeypatch, tmp_path):
    """非 git 目录: 报 null 而不是抛异常 —— 探针是诊断, 不能成为新的崩溃点。"""
    mod = stale_tree["mod"]
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.setattr(mod, "_ROOT", plain)
    probe = mod.source_tree_probe()
    assert probe["head"] is None
    assert probe["behind_origin_main"] is None
    assert probe["stale"] is None


def test_status_reports_source_tree(stale_tree, monkeypatch):
    """`status` 的 JSON 里必须带 source_tree —— 这是读者判断 in_sync 可不可信的依据。"""
    mod = stale_tree["mod"]
    monkeypatch.setattr(mod, "_ROOT", stale_tree["tree"])
    monkeypatch.setattr(mod, "HOST_DIR", stale_tree["tree"] / "bin/panorama/assets/host")
    dash = stale_tree["tmp"] / "dash"
    dash.mkdir()
    monkeypatch.setattr(mod, "DASHBOARD_DIR", dash)
    result = mod.status(dashboard_dir=dash)
    assert "source_tree" in result, "status 必须报源树, 否则 in_sync 无法判读"
    assert result["source_tree"]["stale"] is True


def test_asset_plan_reports_source_tree(stale_tree, monkeypatch):
    mod = stale_tree["mod"]
    host = stale_tree["tree"] / "bin/panorama/assets/host"
    host.mkdir(parents=True)
    # 任一登记资产: 内容存在即可, 本条只关心 source_tree 字段
    name, repo_name = mod.HOST_FILES[0]
    (host / repo_name).write_text("x", encoding="utf-8")
    runtime = stale_tree["tmp"] / "runtime"
    runtime.mkdir()
    (runtime / name).write_text("x", encoding="utf-8")
    monkeypatch.setattr(mod, "_ROOT", stale_tree["tree"])
    planned = mod._asset_plan(runtime, [name], host)
    assert planned["ok"] is True, planned
    assert planned["source_tree"]["stale"] is True, "plan 必须报源树陈旧, 否则 in_sync 是假安心"
