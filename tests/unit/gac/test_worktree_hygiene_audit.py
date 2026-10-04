"""Unit tests for bin/gac/worktree-hygiene-audit.py."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[3] / "bin" / "gac" / "worktree-hygiene-audit.py"
_spec = importlib.util.spec_from_file_location("worktree_hygiene_audit", _MODULE_PATH)
wha = importlib.util.module_from_spec(_spec)
sys.modules["worktree_hygiene_audit"] = wha
_spec.loader.exec_module(wha)  # type: ignore[union-attr]


def _completed(rc: int = 0, stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout=stdout, stderr="")


class FakeGit:
    """Scripted stand-in for ``wha._run`` covering the git surface the audit uses.

    Records every ``(cmd, cwd)`` it is handed. Asserting on that record is the
    point of the repo-aware ancestry fix: the audit must ask each repo its own
    ancestry question, so *where* a command ran is part of the contract, not an
    implementation detail.

    ``cwd`` equal to ``wt_path`` is the superproject; anything below it is a
    submodule checkout (which, for a real worktree, has its own gitdir and its
    own remote-tracking refs).
    """

    def __init__(
        self,
        wt_path: Path | None = None,
        *,
        dirty: int = 0,
        upstream: str = "origin/feature",
        super_has_origin_main: bool = True,
        super_merged: bool = True,
        submodule_status: str = "",
        sub_has_origin_main: bool = True,
        sub_head_resolves: bool = True,
        sub_git_dir: Path | None = None,
        sub_merged: bool = True,
    ) -> None:
        self.wt_path = Path(wt_path) if wt_path is not None else None
        self.dirty = dirty
        self.upstream = upstream
        self.super_has_origin_main = super_has_origin_main
        self.super_merged = super_merged
        self.submodule_status = submodule_status
        self.sub_has_origin_main = sub_has_origin_main
        self.sub_head_resolves = sub_head_resolves
        self.sub_git_dir = sub_git_dir
        self.sub_merged = sub_merged
        self.calls: list[tuple[list[str], Path | None]] = []

    def __call__(
        self,
        cmd: list[str],
        cwd: Path | None = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append((list(cmd), cwd))
        in_submodule = cwd is not None and Path(cwd) != self.wt_path
        if cmd[:2] == ["git", "status"]:
            return _completed(0, "\n".join(" M file" for _ in range(self.dirty)))
        if cmd[:2] == ["git", "rev-parse"]:
            ref = cmd[-1]
            if ref == "HEAD@{upstream}":
                return _completed(0, self.upstream + "\n") if self.upstream else _completed(1)
            if ref == "HEAD" and cmd[-2] == "--git-path":
                # Only reached on the unresolvable-HEAD diagnosis path.
                return _completed(0, f"{self.sub_git_dir / 'HEAD'}\n") if self.sub_git_dir else _completed(128)
            if ref == "HEAD":
                return _completed(0, "a" * 40 + "\n") if self.sub_head_resolves else _completed(1)
        if cmd[:2] == ["git", "submodule"]:
            return _completed(0, self.submodule_status)
        if cmd[:2] == ["git", "merge-base"]:
            # Real exit codes: 0 ancestor, 1 not an ancestor, 128 a side unresolvable.
            if in_submodule:
                if not (self.sub_head_resolves and self.sub_has_origin_main):
                    return _completed(128)
                return _completed(0 if self.sub_merged else 1)
            if not self.super_has_origin_main:
                return _completed(128)
            return _completed(0 if self.super_merged else 1)
        raise AssertionError(f"unexpected git command: {cmd} (cwd={cwd})")

    def cwds_for(self, *prefix: str) -> list[Path | None]:
        return [cwd for cmd, cwd in self.calls if tuple(cmd[: len(prefix)]) == prefix]


@contextmanager
def _fake_worktree(fake: FakeGit, sub_checkout: bool = True):
    """Real temp tree so path-existence logic in the submodule probe is exercised.

    Also materialises the submodule's gitdir with a HEAD file, because the
    unresolvable-HEAD diagnosis reads that file directly (git itself refuses to
    resolve `refs/heads/.invalid` as a refname).
    """
    with tempfile.TemporaryDirectory(prefix="wt-hygiene-") as td:
        wt = Path(td)
        if sub_checkout:
            sub = wt / "projects" / "knowledge" / "kairon"
            sub.mkdir(parents=True)
            (sub / ".git").write_text("gitdir: ../../../../.git/modules/kairon\n")
            git_dir = wt / "fake-submodule-gitdir"
            git_dir.mkdir()
            (git_dir / "HEAD").write_text("ref: refs/heads/.invalid\n")
            fake.sub_git_dir = git_dir
        fake.wt_path = wt
        with mock.patch.object(wha, "_run", fake):
            yield wt


def _wt_entry(wt: Path) -> dict[str, str]:
    return {"path": str(wt), "branch": "work/feature", "head": "b" * 40}


_KAIRON_MERGED = " " + "c" * 40 + " projects/knowledge/kairon (remotes/origin/HEAD)"
_KAIRON_UNMERGED = "+" + "c" * 40 + " projects/knowledge/kairon (remotes/origin/main-13-gc0ffee)"
_KAIRON_UNINITIALIZED = "-" + "c" * 40 + " projects/knowledge/kairon"


def _categorize(fake: FakeGit, *, mtime_days: float = 0.1, sub_checkout: bool = True) -> wha.WorktreeInfo:
    with _fake_worktree(fake, sub_checkout=sub_checkout) as wt:
        with mock.patch.object(wha, "_mtime_days", return_value=mtime_days):
            return wha._categorize_worktree(_wt_entry(wt))


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
        return text[start : nxt if nxt != -1 else len(text)]

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


class TestRepoAwareAncestry:
    """Ancestry must be decided by the repo that owns the worktree, not WORKSPACE."""

    def test_ancestry_command_runs_in_the_worktree_not_the_superproject(self):
        wt = Path("/tmp/ws-ancestry-probe")
        assert wt != wha.WORKSPACE, "fixture must not be the superproject"
        fake = FakeGit(wt, super_merged=True)
        with mock.patch.object(wha, "_run", fake):
            assert wha._is_merged_to_origin_main("b" * 40, wt) is True
        cwds = fake.cwds_for("git", "merge-base")
        assert cwds, "no merge-base invocation was recorded"
        assert all(cwd == wt for cwd in cwds), f"ancestry evaluated outside the worktree: {cwds}"

    def test_unmerged_head_reports_false(self):
        wt = Path("/tmp/ws-ancestry-unmerged")
        fake = FakeGit(wt, super_merged=False)
        with mock.patch.object(wha, "_run", fake):
            assert wha._is_merged_to_origin_main("b" * 40, wt) is False

    def test_missing_origin_main_is_not_merged(self):
        """Unknown must never read as merged: merge-base exits 128 without origin/main."""
        wt = Path("/tmp/ws-ancestry-no-ref")
        fake = FakeGit(wt, super_has_origin_main=False, super_merged=True)
        with mock.patch.object(wha, "_run", fake):
            assert wha._is_merged_to_origin_main("b" * 40, wt) is False

    def test_empty_head_is_not_merged_and_runs_nothing(self):
        fake = FakeGit(Path("/tmp/ws-ancestry-empty"))
        with mock.patch.object(wha, "_run", fake):
            assert wha._is_merged_to_origin_main("", Path("/tmp/ws-ancestry-empty")) is False
        assert fake.calls == []


class TestSubmoduleGate:
    """Regression lock for the incident: unpushed submodule commits read as merged.

    A worktree whose superproject HEAD really is merged, and whose tree is
    otherwise clean, still holds real work if a submodule checkout sits on
    commits that were never pushed. That must not be `safe_to_remove`.
    """

    def test_unmerged_submodule_is_unsafe_even_when_superproject_merged_and_clean(self):
        info = _categorize(FakeGit(dirty=0, super_merged=True, submodule_status=_KAIRON_UNMERGED, sub_merged=False))
        assert info.merged_to_origin_main is True
        assert info.dirty == 0
        assert info.category == "unmerged_submodule"
        assert "unmerged_submodule" in wha.UNSAFE_WORKTREE_CATEGORIES
        assert "kairon" in info.reason
        assert "not in its origin/main" in info.reason

    def test_submodule_without_origin_main_ref_is_unsafe(self):
        info = _categorize(FakeGit(submodule_status=_KAIRON_MERGED, sub_has_origin_main=False))
        assert info.category == "unmerged_submodule"
        assert "origin/main" in info.reason

    def test_unresolved_submodule_head_is_unsafe_and_shows_head_file(self):
        """Half-initialized clones report a *matching* status flag; only HEAD tells the truth."""
        info = _categorize(FakeGit(submodule_status=_KAIRON_MERGED, sub_head_resolves=False))
        assert info.category == "unmerged_submodule"
        assert "unresolvable HEAD" in info.reason
        assert "refs/heads/.invalid" in info.reason

    def test_dirty_worktree_with_unpushed_submodule_is_not_blamed_on_uncommitted_changes(self):
        """The gitlink dirtiness is a symptom; unpushed history is the finding."""
        info = _categorize(FakeGit(dirty=1, super_merged=True, submodule_status=_KAIRON_UNMERGED, sub_merged=False))
        assert info.category == "unmerged_submodule"
        assert "uncommitted changes" not in info.reason

    def test_uninitialized_submodule_is_skipped_and_tree_stays_safe(self):
        """`-` prefix means no local commits to lose — must not crash, must not block."""
        fake = FakeGit(submodule_status=_KAIRON_UNINITIALIZED)
        info = _categorize(fake, sub_checkout=False)
        assert info.category == "safe_to_remove"
        assert not any(cwd != fake.wt_path for cwd in fake.cwds_for("git", "merge-base"))

    def test_merged_submodule_leaves_worktree_safe(self):
        info = _categorize(FakeGit(submodule_status=_KAIRON_MERGED, sub_merged=True))
        assert info.category == "safe_to_remove"

    def test_submodule_probe_reads_this_worktree_only(self):
        fake = FakeGit(submodule_status=_KAIRON_MERGED, sub_merged=True)
        _categorize(fake)
        wt = fake.wt_path
        assert fake.cwds_for("git", "submodule") == [wt]
        assert set(fake.cwds_for("git", "merge-base")) == {wt, wt / "projects" / "knowledge" / "kairon"}

    def test_merged_submodule_costs_one_subprocess(self):
        """Happy path: a single merge-base per submodule, diagnosis only on a gap."""
        fake = FakeGit(submodule_status=_KAIRON_MERGED, sub_merged=True)
        _categorize(fake)
        sub = fake.wt_path / "projects" / "knowledge" / "kairon"
        assert [cmd for cmd, cwd in fake.calls if cwd == sub] == [
            ["git", "merge-base", "--is-ancestor", "HEAD", "origin/main"]
        ]

    def test_unmerged_superproject_skips_the_submodule_probe(self):
        """The probe can only change a merged verdict, so it must not run otherwise."""
        fake = FakeGit(super_merged=False, submodule_status=_KAIRON_UNMERGED, sub_merged=False)
        info = _categorize(fake, mtime_days=5.0)
        assert info.category == "stale_clean"
        assert fake.cwds_for("git", "submodule") == []


class TestSafeToRemoveConjunction:
    """safe_to_remove == clean AND superproject merged AND no unmerged submodule."""

    def test_safe_to_remove_requires_clean_and_merged(self):
        assert _categorize(FakeGit(dirty=0, super_merged=True)).category == "safe_to_remove"

    def test_not_safe_when_superproject_unmerged(self):
        info = _categorize(FakeGit(dirty=0, super_merged=False))
        assert info.category == "active"
        assert info.category not in wha.UNSAFE_WORKTREE_CATEGORIES

    def test_not_safe_when_dirty(self):
        info = _categorize(FakeGit(dirty=2, super_merged=True))
        assert info.category == "merged_with_dirty"
        assert info.category in wha.UNSAFE_WORKTREE_CATEGORIES

    def test_unsafe_categories_cannot_be_auto_cleaned(self):
        assert "unmerged_submodule" in wha.UNSAFE_WORKTREE_CATEGORIES
        assert "safe_to_remove" not in wha.UNSAFE_WORKTREE_CATEGORIES
        assert wha.UNSAFE_WORKTREE_CATEGORIES.isdisjoint(wha.AUTO_DIR_CATEGORIES)
        assert wha.UNSAFE_WORKTREE_CATEGORIES.isdisjoint(wha.UNSAFE_DIR_CATEGORIES)


class TestPreExistingCategoryMeanings:
    """The submodule gate must not silently re-label the existing categories."""

    @pytest.mark.parametrize(
        ("dirty", "super_merged", "submodule_status", "sub_merged", "mtime_days", "expected"),
        [
            pytest.param(3, True, _KAIRON_MERGED, True, 0.1, "merged_with_dirty", id="merged_with_dirty"),
            pytest.param(0, False, "", True, 5.0, "stale_clean", id="stale_clean"),
            pytest.param(3, False, "", True, 5.0, "stale_dirty", id="stale_dirty"),
            pytest.param(1, False, "", True, 0.1, "active", id="active"),
            # A stale worktree with unpushed submodules stays `stale_*` (already unsafe):
            # the new category only speaks for superproject-merged worktrees.
            pytest.param(0, False, _KAIRON_UNMERGED, False, 5.0, "stale_clean", id="no_hijack_of_stale"),
        ],
    )
    def test_category_unchanged(self, dirty, super_merged, submodule_status, sub_merged, mtime_days, expected):
        fake = FakeGit(dirty=dirty, super_merged=super_merged, submodule_status=submodule_status, sub_merged=sub_merged)
        info = _categorize(fake, mtime_days=mtime_days)
        assert info.category == expected
        assert info.dirty == dirty
