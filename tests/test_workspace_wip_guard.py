"""workspace-wip-guard — 共享主工作区脏态快照/检测/恢复回归测试.

对应 2026-09-17 实证: 主工作区未提交改动被并发会话的分支切换/reset 静默丢失,
且提交时可能裹入他人暂存内容.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "wip_guard", ROOT / "bin/gac/workspace-wip-guard.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["wip_guard"] = module
    spec.loader.exec_module(module)
    return module


def _repo(tmp_path: Path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    (tmp_path / "a.md").write_text("original\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "init"], check=True)
    return tmp_path


def _wire(mod, root: Path):
    mod._ROOT = root
    mod.SNAPSHOT_DIR = root / "runtime" / "wip-snapshots"
    return root


def test_snapshot_skips_clean_workspace(tmp_path):
    mod = _load()
    _wire(mod, _repo(tmp_path))
    result = mod.snapshot(reason="t", quiet=True)
    assert result["ok"] is True and result.get("skipped") is True
    assert result["reason"] == "clean_workspace"


def test_snapshot_captures_modified_and_untracked(tmp_path):
    mod = _load()
    root = _wire(mod, _repo(tmp_path))
    (root / "a.md").write_text("IMPORTANT\n", encoding="utf-8")
    (root / "new.md").write_text("untracked work\n", encoding="utf-8")

    result = mod.snapshot(reason="t", quiet=True)
    assert result["files"] == 2
    snap = mod.SNAPSHOT_DIR / result["snapshot"]
    manifest = json.loads((snap / "manifest.json").read_text(encoding="utf-8"))
    paths = {f["path"] for f in manifest["files"]}
    assert paths == {"a.md", "new.md"}
    assert manifest["schema"] == "wip-snapshot/v1"


def test_restore_recovers_lost_changes_end_to_end(tmp_path):
    """端到端: 快照 → 灾难(丢改动+删文件) → dry-run → force 恢复."""
    mod = _load()
    root = _wire(mod, _repo(tmp_path))
    (root / "a.md").write_text("IMPORTANT WORK\n", encoding="utf-8")
    (root / "c.md").write_text("new file\n", encoding="utf-8")
    snap_id = mod.snapshot(reason="t", quiet=True)["snapshot"]

    # 灾难
    (root / "a.md").write_text("original\n", encoding="utf-8")
    (root / "c.md").unlink()

    dry = mod.restore(snap_id)
    assert dry["dry_run"] is True and dry["restored"] == 2
    assert (root / "c.md").exists() is False  # dry-run 不写

    mod.restore(snap_id, force=True)
    assert (root / "a.md").read_text(encoding="utf-8").strip() == "IMPORTANT WORK"
    assert (root / "c.md").read_text(encoding="utf-8").strip() == "new file"


def test_restore_idempotent_when_no_difference(tmp_path):
    mod = _load()
    root = _wire(mod, _repo(tmp_path))
    (root / "a.md").write_text("X\n", encoding="utf-8")
    snap_id = mod.snapshot(reason="t", quiet=True)["snapshot"]
    result = mod.restore(snap_id, force=True)
    assert result["restored"] == 0


def test_retention_prunes_old_snapshots(tmp_path, monkeypatch):
    mod = _load()
    root = _wire(mod, _repo(tmp_path))
    monkeypatch.setattr(mod, "KEEP", 3)
    (root / "a.md").write_text("dirty\n", encoding="utf-8")
    for i in range(5):
        # 手工造 5 个快照目录 (避免依赖时间戳精度)
        d = mod.SNAPSHOT_DIR / f"2026010{i}T000000Z"
        d.mkdir(parents=True)
        (d / "manifest.json").write_text(json.dumps({"files": [], "reason": "x"}))
    mod.snapshot(reason="t", quiet=True)
    remaining = sorted(p.name for p in mod.SNAPSHOT_DIR.glob("*/"))
    assert len(remaining) <= 3 + 1  # KEEP=3 + 本次新增
    assert not (mod.SNAPSHOT_DIR / "20260100T000000Z").exists()


def test_check_flags_over_threshold(tmp_path, monkeypatch):
    mod = _load()
    root = _wire(mod, _repo(tmp_path))
    monkeypatch.setattr(mod, "DIRTY_WARN_THRESHOLD", 0)
    (root / "a.md").write_text("dirty\n", encoding="utf-8")
    assert mod.check() == 1

    monkeypatch.setattr(mod, "DIRTY_WARN_THRESHOLD", 99)
    assert mod.check() == 0


def test_non_main_workspace_is_skipped(tmp_path, monkeypatch):
    """worktree (git-dir != git-common-dir) 不做守卫."""
    mod = _load()
    _wire(mod, _repo(tmp_path))
    monkeypatch.setattr(mod, "is_main_workspace", lambda: False)
    assert mod.snapshot(reason="t", quiet=True)["skipped"] is True
    assert mod.check() == 0
