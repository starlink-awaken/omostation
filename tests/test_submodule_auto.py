"""Tests for lib.submodule_auto — drift detection, auto-update, rollback.

Tests use mocked git operations to avoid requiring actual git repositories.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase, main as unittest_main
from unittest.mock import patch, MagicMock, call

import sys

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from lib.submodule_auto import (
    SubmoduleAutoManager,
    DriftStatus,
    UpdateResult,
    DriftReport,
    UpdateReport,
    SubmoduleStatus,
)


class TestDriftStatus(TestCase):
    """Test DriftStatus enum."""

    def test_enum_values(self):
        assert DriftStatus.ALIGNED == "aligned"
        assert DriftStatus.BEHIND == "behind"
        assert DriftStatus.AHEAD == "ahead"
        assert DriftStatus.DIVERGED == "DIVERGED"
        assert DriftStatus.SKIP == "skip"
        assert DriftStatus.UNVERIFIABLE == "unverifiable"
        assert DriftStatus.ERROR == "error"


class TestDriftReport(TestCase):
    """Test DriftReport dataclass."""

    def test_empty_report(self):
        report = DriftReport()
        assert report.total == 0
        assert report.has_drift is False
        assert report.has_stale is False

    def test_report_with_drift(self):
        report = DriftReport(diverged=2, total=5)
        assert report.has_drift is True
        assert report.has_stale is False

    def test_report_with_stale(self):
        report = DriftReport(behind=3, total=5)
        assert report.has_drift is False
        assert report.has_stale is True

    def test_to_dict(self):
        report = DriftReport(total=2, aligned=1, diverged=1)
        d = report.to_dict()
        assert d["total"] == 2
        assert d["aligned"] == 1
        assert d["diverged"] == 1
        assert d["has_drift"] is True
        assert d["has_stale"] is False


class TestSubmoduleAutoManager(TestCase):
    """Test SubmoduleAutoManager with mocked git operations."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo_root = Path(self.tmpdir)
        self.mgr = SubmoduleAutoManager(repo_root=self.repo_root)

    def _mock_git_output(self, return_value: str):
        """Helper to mock _git_output."""
        return patch.object(self.mgr, '_git_output', return_value=return_value)

    def _mock_git(self, returncode: int = 0, stdout: str = ""):
        """Helper to mock _git."""
        mock_result = MagicMock()
        mock_result.returncode = returncode
        mock_result.stdout = stdout
        return patch.object(self.mgr, '_git', return_value=mock_result)

    # ── Submodule discovery ──────────────────────────────────────────────

    def test_get_submodule_paths(self):
        with self._mock_git_output("submodule.projects/kairon.path projects/kairon\nsubmodule.projects/gbrain.path projects/gbrain"):
            paths = self.mgr.get_submodule_paths()
            assert paths == ["projects/kairon", "projects/gbrain"]

    def test_get_submodule_paths_empty(self):
        with self._mock_git_output(""):
            paths = self.mgr.get_submodule_paths()
            assert paths == []

    # ── Gitlink resolution ───────────────────────────────────────────────

    def test_get_gitlink_sha_index(self):
        with self._mock_git(returncode=0, stdout="160000 abc123def456 0\tprojects/kairon"):
            sha = self.mgr.get_gitlink_sha("projects/kairon", source="index")
            assert sha == "abc123def456"

    def test_get_gitlink_sha_index_not_found(self):
        with self._mock_git(returncode=0, stdout=""):
            sha = self.mgr.get_gitlink_sha("projects/kairon", source="index")
            assert sha is None

    def test_get_gitlink_sha_head(self):
        # `git ls-tree` output format: `<mode> <type> <object>\t<path>`
        with self._mock_git(returncode=0, stdout="160000 commit abc123def456\tprojects/kairon"):
            sha = self.mgr.get_gitlink_sha("projects/kairon", source="head")
            assert sha == "abc123def456"

    def test_get_gitlink_sha_head_not_tree(self):
        with self._mock_git(returncode=0, stdout="100644 blob abc123def456\tREADME.md"):
            sha = self.mgr.get_gitlink_sha("projects/kairon", source="head")
            assert sha is None

    # ── Drift detection ──────────────────────────────────────────────────

    def test_check_drift_aligned(self):
        sha = "abc123def456789"
        with patch.object(self.mgr, 'get_gitlink_sha', return_value=sha), \
             patch.object(self.mgr, 'get_remote_main_sha', return_value=sha):
            status = self.mgr.check_drift_single("projects/kairon")
            assert status.drift_status == DriftStatus.ALIGNED
            assert status.gitlink_sha == sha
            assert status.remote_sha == sha

    def test_check_drift_behind(self):
        gitlink = "aaa111"
        remote = "bbb222"
        with patch.object(self.mgr, 'get_gitlink_sha', return_value=gitlink), \
             patch.object(self.mgr, 'get_remote_main_sha', return_value=remote), \
             patch.object(self.mgr, 'is_ancestor', side_effect=lambda c, a, p: c == gitlink and a == remote):
            status = self.mgr.check_drift_single("projects/kairon")
            assert status.drift_status == DriftStatus.BEHIND
            assert status.gitlink_sha == gitlink
            assert status.remote_sha == remote

    def test_check_drift_ahead(self):
        gitlink = "bbb222"
        remote = "aaa111"
        with patch.object(self.mgr, 'get_gitlink_sha', return_value=gitlink), \
             patch.object(self.mgr, 'get_remote_main_sha', return_value=remote), \
             patch.object(self.mgr, 'is_ancestor', side_effect=lambda c, a, p: c == remote and a == gitlink):
            status = self.mgr.check_drift_single("projects/kairon")
            assert status.drift_status == DriftStatus.AHEAD

    def test_check_drift_diverged(self):
        gitlink = "aaa111"
        remote = "bbb222"
        with patch.object(self.mgr, 'get_gitlink_sha', return_value=gitlink), \
             patch.object(self.mgr, 'get_remote_main_sha', return_value=remote), \
             patch.object(self.mgr, 'is_ancestor', return_value=False), \
             patch.object(self.mgr, '_is_shallow', return_value=False):
            status = self.mgr.check_drift_single("projects/kairon")
            assert status.drift_status == DriftStatus.DIVERGED

    def test_check_drift_skip_no_gitlink(self):
        with patch.object(self.mgr, 'get_gitlink_sha', return_value=None):
            status = self.mgr.check_drift_single("projects/kairon")
            assert status.drift_status == DriftStatus.SKIP

    def test_check_drift_skip_no_remote(self):
        with patch.object(self.mgr, 'get_gitlink_sha', return_value="abc123"), \
             patch.object(self.mgr, 'get_remote_main_sha', return_value=None):
            status = self.mgr.check_drift_single("projects/kairon")
            assert status.drift_status == DriftStatus.SKIP

    def test_check_drift_unverifiable_shallow(self):
        gitlink = "aaa111"
        remote = "bbb222"
        with patch.object(self.mgr, 'get_gitlink_sha', return_value=gitlink), \
             patch.object(self.mgr, 'get_remote_main_sha', return_value=remote), \
             patch.object(self.mgr, 'is_ancestor', return_value=False), \
             patch.object(self.mgr, '_is_shallow', return_value=True):
            status = self.mgr.check_drift_single("projects/kairon")
            assert status.drift_status == DriftStatus.UNVERIFIABLE

    # ── Detect drift (aggregate) ─────────────────────────────────────────

    def test_detect_drift_all_aligned(self):
        with patch.object(self.mgr, 'get_submodule_paths', return_value=["projects/kairon", "projects/gbrain"]), \
             patch.object(self.mgr, 'check_drift_single', return_value=SubmoduleStatus(
                 path="test", drift_status=DriftStatus.ALIGNED, gitlink_sha="abc", remote_sha="abc")):
            report = self.mgr.detect_drift()
            assert report.total == 2
            assert report.aligned == 2
            assert report.has_drift is False

    def test_detect_drift_with_diverged(self):
        def mock_check(path, source="index"):
            if path == "projects/kairon":
                return SubmoduleStatus(path=path, drift_status=DriftStatus.DIVERGED,
                                       gitlink_sha="aaa", remote_sha="bbb")
            return SubmoduleStatus(path=path, drift_status=DriftStatus.ALIGNED,
                                   gitlink_sha="abc", remote_sha="abc")

        with patch.object(self.mgr, 'get_submodule_paths', return_value=["projects/kairon", "projects/gbrain"]), \
             patch.object(self.mgr, 'check_drift_single', side_effect=mock_check):
            report = self.mgr.detect_drift()
            assert report.total == 2
            assert report.diverged == 1
            assert report.aligned == 1
            assert report.has_drift is True

    # ── Pointer update ───────────────────────────────────────────────────

    def test_update_pointer_success(self):
        with self._mock_git(returncode=0), \
             patch.object(self.mgr, '_git_output', return_value=""):
            result = self.mgr.update_pointer("projects/kairon", "abc123")
            assert result is True

    def test_update_pointer_fail_update_index(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch.object(self.mgr, '_git', return_value=mock_result):
            result = self.mgr.update_pointer("projects/kairon", "abc123")
            assert result is False

    def test_restore_pointer(self):
        with patch.object(self.mgr, 'update_pointer', return_value=True) as mock_update:
            result = self.mgr.restore_pointer("projects/kairon", "old_sha")
            assert result is True
            mock_update.assert_called_once_with("projects/kairon", "old_sha")

    def test_verify_pointer_match(self):
        with patch.object(self.mgr, 'get_gitlink_sha', return_value="abc123"):
            assert self.mgr.verify_pointer("projects/kairon", "abc123") is True

    def test_verify_pointer_mismatch(self):
        with patch.object(self.mgr, 'get_gitlink_sha', return_value="abc123"):
            assert self.mgr.verify_pointer("projects/kairon", "def456") is False

    def test_verify_reachable(self):
        with patch.object(self.mgr, '_git', return_value=MagicMock(returncode=0)), \
             patch.object(self.mgr, 'get_remote_main_sha', return_value="remote_sha"), \
             patch.object(self.mgr, 'is_ancestor', return_value=True):
            assert self.mgr.verify_reachable("projects/kairon", "abc123") is True

    def test_verify_reachable_fail_no_remote(self):
        with patch.object(self.mgr, '_git', return_value=MagicMock(returncode=0)), \
             patch.object(self.mgr, 'get_remote_main_sha', return_value=None):
            assert self.mgr.verify_reachable("projects/kairon", "abc123") is False

    # ── Auto-update ──────────────────────────────────────────────────────

    def test_auto_update_no_targets(self):
        with patch.object(self.mgr, 'detect_drift', return_value=DriftReport(
            total=2, aligned=2, submodules=[
                SubmoduleStatus(path="p1", drift_status=DriftStatus.ALIGNED),
                SubmoduleStatus(path="p2", drift_status=DriftStatus.ALIGNED),
            ])):
            report = self.mgr.auto_update(apply=True)
            assert report.attempted == 0
            assert report.updated == 0

    def test_auto_update_dry_run(self):
        with patch.object(self.mgr, 'detect_drift', return_value=DriftReport(
            total=1, diverged=1, submodules=[
                SubmoduleStatus(path="projects/kairon", drift_status=DriftStatus.DIVERGED,
                               gitlink_sha="aaa", remote_sha="bbb"),
            ])):
            report = self.mgr.auto_update(apply=False)
            assert report.attempted == 1
            assert report.updated == 1
            assert report.results[0].update_result == UpdateResult.UPDATED

    def test_auto_update_apply_success(self):
        with patch.object(self.mgr, 'detect_drift', return_value=DriftReport(
            total=1, diverged=1, submodules=[
                SubmoduleStatus(path="projects/kairon", drift_status=DriftStatus.DIVERGED,
                               gitlink_sha="aaa", remote_sha="bbb"),
            ])), \
             patch.object(self.mgr, 'get_gitlink_sha', return_value="aaa"), \
             patch.object(self.mgr, 'update_pointer', return_value=True), \
             patch.object(self.mgr, 'verify_pointer', return_value=True), \
             patch.object(self.mgr, 'verify_reachable', return_value=True):
            report = self.mgr.auto_update(apply=True)
            assert report.attempted == 1
            assert report.updated == 1
            assert report.results[0].update_result == UpdateResult.UPDATED

    def test_auto_update_apply_rollback_on_verify_fail(self):
        with patch.object(self.mgr, 'detect_drift', return_value=DriftReport(
            total=1, diverged=1, submodules=[
                SubmoduleStatus(path="projects/kairon", drift_status=DriftStatus.DIVERGED,
                               gitlink_sha="aaa", remote_sha="bbb"),
            ])), \
             patch.object(self.mgr, 'get_gitlink_sha', return_value="aaa"), \
             patch.object(self.mgr, 'update_pointer', return_value=True), \
             patch.object(self.mgr, 'verify_pointer', return_value=False), \
             patch.object(self.mgr, 'restore_pointer', return_value=True) as mock_restore:
            report = self.mgr.auto_update(apply=True)
            assert report.attempted == 1
            assert report.rolled_back == 1
            assert report.results[0].update_result == UpdateResult.ROLLED_BACK
            mock_restore.assert_called_once_with("projects/kairon", "aaa")

    def test_auto_update_apply_rollback_on_reachability_fail(self):
        with patch.object(self.mgr, 'detect_drift', return_value=DriftReport(
            total=1, diverged=1, submodules=[
                SubmoduleStatus(path="projects/kairon", drift_status=DriftStatus.DIVERGED,
                               gitlink_sha="aaa", remote_sha="bbb"),
            ])), \
             patch.object(self.mgr, 'get_gitlink_sha', return_value="aaa"), \
             patch.object(self.mgr, 'update_pointer', return_value=True), \
             patch.object(self.mgr, 'verify_pointer', return_value=True), \
             patch.object(self.mgr, 'verify_reachable', return_value=False), \
             patch.object(self.mgr, 'restore_pointer', return_value=True) as mock_restore:
            report = self.mgr.auto_update(apply=True)
            assert report.attempted == 1
            assert report.rolled_back == 1
            mock_restore.assert_called_once_with("projects/kairon", "aaa")

    def test_auto_update_apply_fail_update(self):
        with patch.object(self.mgr, 'detect_drift', return_value=DriftReport(
            total=1, diverged=1, submodules=[
                SubmoduleStatus(path="projects/kairon", drift_status=DriftStatus.DIVERGED,
                               gitlink_sha="aaa", remote_sha="bbb"),
            ])), \
             patch.object(self.mgr, 'get_gitlink_sha', return_value="aaa"), \
             patch.object(self.mgr, 'update_pointer', return_value=False):
            report = self.mgr.auto_update(apply=True)
            assert report.attempted == 1
            assert report.failed == 1
            assert report.results[0].update_result == UpdateResult.FAILED

    def test_auto_update_strict_mode(self):
        """In strict mode, behind submodules should also be updated."""
        with patch.object(self.mgr, 'detect_drift', return_value=DriftReport(
            total=1, behind=1, submodules=[
                SubmoduleStatus(path="projects/kairon", drift_status=DriftStatus.BEHIND,
                               gitlink_sha="aaa", remote_sha="bbb"),
            ])), \
             patch.object(self.mgr, 'get_gitlink_sha', return_value="aaa"), \
             patch.object(self.mgr, 'update_pointer', return_value=True), \
             patch.object(self.mgr, 'verify_pointer', return_value=True), \
             patch.object(self.mgr, 'verify_reachable', return_value=True):
            report = self.mgr.auto_update(apply=True, strict=True)
            assert report.attempted == 1
            assert report.updated == 1

    def test_auto_update_no_strict_skips_behind(self):
        """Without strict mode, behind submodules should be skipped."""
        with patch.object(self.mgr, 'detect_drift', return_value=DriftReport(
            total=1, behind=1, submodules=[
                SubmoduleStatus(path="projects/kairon", drift_status=DriftStatus.BEHIND,
                               gitlink_sha="aaa", remote_sha="bbb"),
            ])):
            report = self.mgr.auto_update(apply=True, strict=False)
            assert report.attempted == 0

    # ── Integrity check ──────────────────────────────────────────────────

    def test_check_integrity_all_aligned(self):
        with patch.object(self.mgr, 'get_submodule_paths', return_value=["projects/kairon"]), \
             patch.object(self.mgr, 'get_gitlink_sha', return_value="abc123"), \
             patch.object(self.mgr, '_git', return_value=MagicMock(returncode=0)), \
             patch.object(self.mgr, 'get_remote_main_sha', return_value="abc123"):
            report = self.mgr.check_integrity()
            assert report.total == 1
            assert report.aligned == 1

    def test_check_integrity_error_no_gitlink(self):
        with patch.object(self.mgr, 'get_submodule_paths', return_value=["projects/kairon"]), \
             patch.object(self.mgr, 'get_gitlink_sha', return_value=None):
            report = self.mgr.check_integrity()
            assert report.total == 1
            assert report.skipped == 1

    def test_check_integrity_error_commit_not_found(self):
        with patch.object(self.mgr, 'get_submodule_paths', return_value=["projects/kairon"]), \
             patch.object(self.mgr, 'get_gitlink_sha', return_value="abc123"), \
             patch.object(self.mgr, '_git', return_value=MagicMock(returncode=1)):
            report = self.mgr.check_integrity()
            assert report.total == 1
            assert report.error == 1


class TestUpdateReport(TestCase):
    """Test UpdateReport dataclass."""

    def test_empty_report(self):
        report = UpdateReport()
        assert report.attempted == 0
        assert report.updated == 0
        assert report.failed == 0
        assert report.rolled_back == 0

    def test_to_dict(self):
        report = UpdateReport(attempted=3, updated=2, failed=1)
        d = report.to_dict()
        assert d["attempted"] == 3
        assert d["updated"] == 2
        assert d["failed"] == 1


class TestSubmoduleStatus(TestCase):
    """Test SubmoduleStatus dataclass."""

    def test_basic_status(self):
        status = SubmoduleStatus(
            path="projects/kairon",
            drift_status=DriftStatus.ALIGNED,
            gitlink_sha="abc123",
            remote_sha="abc123",
        )
        assert status.path == "projects/kairon"
        assert status.drift_status == DriftStatus.ALIGNED
        assert status.update_result is None

    def test_status_with_update_result(self):
        status = SubmoduleStatus(
            path="projects/kairon",
            drift_status=DriftStatus.DIVERGED,
            update_result=UpdateResult.UPDATED,
            previous_sha="old_sha",
        )
        assert status.update_result == UpdateResult.UPDATED
        assert status.previous_sha == "old_sha"


if __name__ == "__main__":
    unittest_main()
