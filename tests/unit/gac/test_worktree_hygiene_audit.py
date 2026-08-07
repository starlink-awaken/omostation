"""Unit tests for bin/gac/worktree-hygiene-audit.py."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path
from unittest import mock

_MODULE_PATH = Path(__file__).resolve().parents[3] / "bin" / "gac" / "worktree-hygiene-audit.py"
_spec = importlib.util.spec_from_file_location("worktree_hygiene_audit", _MODULE_PATH)
wha = importlib.util.module_from_spec(_spec)
sys.modules["worktree_hygiene_audit"] = wha
_spec.loader.exec_module(wha)  # type: ignore[union-attr]


class TestCategorizeWorktree:
    def test_safe_to_remove_when_clean_and_merged(self):
        wt = {"path": "/tmp/ws-foo", "branch": "work/foo", "head": "abc123"}
        with mock.patch.object(wha, "_worktree_status", return_value=(0, "origin/work/foo")):
            with mock.patch.object(wha, "_is_merged_to_origin_main", return_value=True):
                with mock.patch.object(wha, "_mtime_days", return_value=0.5):
                    info = wha._categorize_worktree(wt)
        assert info.category == "safe_to_remove"
        assert info.dirty == 0
        assert info.merged_to_origin_main is True

    def test_stale_dirty_when_dirty_and_old(self):
        wt = {"path": "/tmp/ws-bar", "branch": "work/bar", "head": "def456"}
        with mock.patch.object(wha, "_worktree_status", return_value=(3, "none")):
            with mock.patch.object(wha, "_is_merged_to_origin_main", return_value=False):
                with mock.patch.object(wha, "_mtime_days", return_value=5.0):
                    info = wha._categorize_worktree(wt)
        assert info.category == "stale_dirty"
        assert info.dirty == 3

    def test_active_when_dirty_but_recent(self):
        wt = {"path": "/tmp/ws-baz", "branch": "work/baz", "head": "ghi789"}
        with mock.patch.object(wha, "_worktree_status", return_value=(1, "origin/work/baz")):
            with mock.patch.object(wha, "_is_merged_to_origin_main", return_value=False):
                with mock.patch.object(wha, "_mtime_days", return_value=0.1):
                    info = wha._categorize_worktree(wt)
        assert info.category == "active"


class TestUnregisteredDirInfo:
    def test_empty_abandoned(self):
        with tempfile.TemporaryDirectory(prefix="ws-empty-") as td:
            info = wha._unregistered_dir_info(Path(td))
        assert info.category == "empty_abandoned"
        assert info.file_count == 0

    def test_log_only_abandoned(self):
        with tempfile.TemporaryDirectory(prefix="ws-log-") as td:
            (Path(td) / "watch_stdout.log").write_text("log")
            (Path(td) / "watch_stderr.log").write_text("err")
            info = wha._unregistered_dir_info(Path(td))
        assert info.category == "log_only_abandoned"
        assert info.file_count == 2

    def test_needs_review_with_files(self):
        with tempfile.TemporaryDirectory(prefix="ws-files-") as td:
            (Path(td) / "foo.txt").write_text("data")
            info = wha._unregistered_dir_info(Path(td))
        assert info.category == "needs_review"
        assert info.file_count == 1


class TestIsRegistered:
    def test_resolves_paths(self):
        registered = {str(Path("/tmp/ws-foo").resolve())}
        assert wha._is_registered(Path("/tmp/ws-foo"), registered) is True
        assert wha._is_registered(Path("/tmp/ws-bar"), registered) is False


class TestSummaryCounts:
    def test_counts_group_by_category(self):
        wts = [
            wha.WorktreeInfo("/a", "work/a", "h1", 0, True, 0.0, "o/a", "safe_to_remove", ""),
            wha.WorktreeInfo("/b", "work/b", "h2", 0, False, 5.0, "o/b", "stale_clean", ""),
        ]
        dirs = [
            wha.UnregisteredDirInfo("/c", 0, False, "", 0, "empty_abandoned", ""),
            wha.UnregisteredDirInfo("/d", 2, False, "", 0, "needs_review", ""),
        ]
        counts = wha._summary_counts(wts, dirs)
        assert counts["total_worktrees"] == 2
        assert counts["worktrees"]["safe_to_remove"] == 1
        assert counts["worktrees"]["stale_clean"] == 1
        assert counts["total_unregistered_dirs"] == 2
        assert counts["unregistered_dirs"]["empty_abandoned"] == 1
        assert counts["unregistered_dirs"]["needs_review"] == 1
