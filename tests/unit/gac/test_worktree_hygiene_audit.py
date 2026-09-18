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


class TestCronParity:
    """A4 registry pattern 静态 parity：registry ↔ Makefile ↔ script 不可漂移。

    不碰 live crontab（CI runner 上 crontab 为空），只校验声明面一致性：
    退役链路必须 dry-run-first（无 --execute），N=14 天阈值必须显式声明，
    registry 新增条目在安装前必须保持 proposed/declared_only（否则
    scheduler-compile --check 会报 drift）。
    """

    REPO_ROOT = Path(__file__).resolve().parents[3]

    def _recipe_lines(self, target: str) -> list[str]:
        lines = (self.REPO_ROOT / "Makefile").read_text(encoding="utf-8").splitlines()
        recipe: list[str] = []
        in_target = False
        for ln in lines:
            if in_target:
                if ln.startswith("\t"):
                    recipe.append(ln)
                else:
                    break
            elif ln.startswith(target + ":"):
                in_target = True
        return recipe

    def _registry_block(self, job_name: str) -> str:
        text = (self.REPO_ROOT / ".omo" / "cron" / "registry.yaml").read_text(encoding="utf-8")
        start = text.find(f"- name: {job_name}")
        assert start != -1, f"registry 缺少条目 {job_name}"
        nxt = text.find("\n  - name: ", start)
        return text[start:nxt if nxt != -1 else len(text)]

    def test_retire_target_is_dry_run_first(self):
        recipe = self._recipe_lines("worktree-hygiene-retire")
        assert recipe, "Makefile 缺少 worktree-hygiene-retire 目标"
        body = "\n".join(recipe)
        assert "worktree-hygiene-audit.py" in body
        assert "--stale-days 14" in body, "退役阈值必须显式声明 N=14"
        assert "--execute" not in body, "退役步骤必须 dry-run-first，禁止 --execute"

    def test_daily_target_is_dry_run_first(self):
        recipe = self._recipe_lines("worktree-hygiene")
        assert recipe, "Makefile 缺少 worktree-hygiene 目标"
        body = "\n".join(recipe)
        assert "worktree-hygiene-audit.py" in body
        assert "--execute" not in body, "日检必须 dry-run-first，禁止 --execute"

    def test_registry_retire_entry_is_proposed(self):
        block = self._registry_block("worktree-retire-14d-weekly")
        assert "make worktree-hygiene-retire" in block
        assert "status: proposed" in block
        assert "reality: declared_only" in block

    def test_registry_daily_entry_links_makefile_target(self):
        block = self._registry_block("worktree-hygiene-daily")
        assert "make worktree-hygiene" in block
        assert self._recipe_lines("worktree-hygiene"), "registry 引用的 make 目标不存在"

    def test_script_default_threshold_untouched(self):
        assert wha.STALE_DAYS == 2, "脚本默认阈值被改动会静默改变日检行为，须显式评审"
