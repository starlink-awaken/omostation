"""Submodule pointer automation — drift detection, auto-update, rollback.

Eliminates manual submodule pointer fixes by providing:
- Drift detection (compare root gitlink vs submodule remote HEAD)
- Auto-update (align root pointer to remote main)
- Rollback on failure (restore previous pointer if verification fails)
- Integrity verification (ensure updated pointer is reachable from remote)

Usage as library:
    from lib.submodule_auto import SubmoduleAutoManager
    mgr = SubmoduleAutoManager(repo_root=Path("."))
    report = mgr.detect_drift()
    result = mgr.auto_update(apply=True)

Usage as CLI:
    python3 -m lib.submodule_auto --check
    python3 -m lib.submodule_auto --fix --apply
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional


class DriftStatus(str, Enum):
    ALIGNED = "aligned"
    BEHIND = "behind"
    AHEAD = "ahead"
    DIVERGED = "DIVERGED"
    SKIP = "skip"
    UNVERIFIABLE = "unverifiable"
    ERROR = "error"


class UpdateResult(str, Enum):
    UPDATED = "updated"
    ALREADY_ALIGNED = "already_aligned"
    SKIPPED = "skipped"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class SubmoduleStatus:
    """Status of a single submodule pointer."""

    path: str
    drift_status: DriftStatus
    gitlink_sha: Optional[str] = None
    remote_sha: Optional[str] = None
    detail: Optional[str] = None
    update_result: Optional[UpdateResult] = None
    previous_sha: Optional[str] = None


@dataclass
class DriftReport:
    """Aggregated drift report for all submodules."""

    timestamp: float = field(default_factory=time.time)
    total: int = 0
    aligned: int = 0
    behind: int = 0
    ahead: int = 0
    diverged: int = 0
    skipped: int = 0
    unverifiable: int = 0
    error: int = 0
    submodules: list[SubmoduleStatus] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        return self.diverged > 0

    @property
    def has_stale(self) -> bool:
        return self.behind > 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["has_drift"] = self.has_drift
        d["has_stale"] = self.has_stale
        return d


@dataclass
class UpdateReport:
    """Report of an auto-update operation."""

    timestamp: float = field(default_factory=time.time)
    attempted: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    rolled_back: int = 0
    results: list[SubmoduleStatus] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class SubmoduleAutoManager:
    """Manages submodule pointer automation.

    Args:
        repo_root: Path to the git repository root.
        timeout: Timeout in seconds for git fetch operations.
        strict: If True, treat 'behind' status as drift.
    """

    def __init__(
        self,
        repo_root: Path,
        timeout: int = 30,
        strict: bool = False,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.timeout = timeout
        self.strict = strict

    # ── Git helpers ──────────────────────────────────────────────────────

    def _git_local_env_vars(self) -> frozenset[str]:
        """Return Git variables that must not cross repository boundaries."""
        result = subprocess.run(
            ["git", "rev-parse", "--local-env-vars"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        return frozenset(result.stdout.split())

    def _git_env(self, cwd: Optional[Path] = None) -> dict[str, str]:
        """Clear superproject-local Git state before entering a submodule."""
        env = os.environ.copy()
        if cwd is None or cwd.resolve() == self.repo_root.resolve():
            return env
        for name in self._git_local_env_vars():
            env.pop(name, None)
        return env

    def _git(self, *args: str, cwd: Optional[Path] = None) -> subprocess.CompletedProcess[str]:
        """Run a git command and return the CompletedProcess."""
        return subprocess.run(
            ["git", *args],
            cwd=cwd or self.repo_root,
            env=self._git_env(cwd),
            capture_output=True,
            text=True,
            check=False,
        )

    def _git_output(self, *args: str, cwd: Optional[Path] = None) -> str:
        """Run a git command and return stdout stripped."""
        result = self._git(*args, cwd=cwd)
        return result.stdout.strip()

    # ── Submodule discovery ──────────────────────────────────────────────

    def get_submodule_paths(self) -> list[str]:
        """Return list of submodule paths from .gitmodules."""
        output = self._git_output(
            "config",
            "--file",
            ".gitmodules",
            "--get-regexp",
            r"^submodule\..*\.path$",
        )
        if not output:
            return []
        return [line.split(maxsplit=1)[1] for line in output.splitlines() if line.strip()]

    # ── Pointer resolution ───────────────────────────────────────────────

    def get_gitlink_sha(self, sub_path: str, source: str = "index") -> Optional[str]:
        """Get the gitlink SHA from the root repository.

        Args:
            sub_path: Submodule path relative to repo root.
            source: One of 'index', 'head', 'worktree'.
        """
        if source == "worktree":
            sub_dir = self.repo_root / sub_path
            if not (sub_dir / ".git").exists() and not (sub_dir / ".git").is_file():
                return self.get_gitlink_sha(sub_path, "index")
            result = self._git("rev-parse", "HEAD", cwd=sub_dir)
            return result.stdout.strip() if result.returncode == 0 else None

        if source == "index":
            result = self._git("ls-files", "-s", "--", sub_path)
            if result.returncode != 0 or not result.stdout.strip():
                return None
            parts = result.stdout.split()
            return parts[1] if len(parts) >= 2 and parts[0] == "160000" else None

        # source == "head"
        # `git ls-tree` emits `<mode> <type> <object>\t<path>`; for a gitlink
        # type is `commit`, so the SHA is the third whitespace-separated token
        # of the pre-tab `meta` (not of the whole line, which also carries path).
        result = self._git("ls-tree", "HEAD", "--", sub_path)
        if not result.stdout.strip():
            return None
        meta, _sep, _name = result.stdout.partition("\t")
        parts = meta.split()
        if len(parts) >= 3 and parts[0] == "160000":
            return parts[2]
        return None

    def get_remote_main_sha(self, sub_path: str) -> Optional[str]:
        """Get the origin/main SHA from the submodule's remote."""
        sub_dir = self.repo_root / sub_path
        if not (sub_dir / ".git").exists() and not (sub_dir / ".git").is_file():
            return None
        try:
            subprocess.run(
                ["git", "fetch", "origin", "--quiet"],
                cwd=sub_dir,
                env=self._git_env(sub_dir),
                capture_output=True,
                check=False,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            pass
        sha = self._git_output("rev-parse", "origin/main", cwd=sub_dir)
        return sha if sha else None

    # ── Ancestry checks ──────────────────────────────────────────────────

    def is_ancestor(self, commit: str, ancestor: str, sub_path: str) -> bool:
        """Check if commit is an ancestor of ancestor in the submodule."""
        sub_dir = self.repo_root / sub_path
        result = self._git("merge-base", "--is-ancestor", commit, ancestor, cwd=sub_dir)
        return result.returncode == 0

    def _is_shallow(self, sub_path: str) -> bool:
        """Check if the submodule is a shallow clone."""
        sub_dir = self.repo_root / sub_path
        if (sub_dir / ".git").is_file():
            git_dir = (sub_dir / ".git").read_text().split("gitdir: ")[-1].strip()
            shallow = sub_dir / git_dir / "shallow"
        else:
            shallow = sub_dir / ".git" / "shallow"
        return shallow.exists()

    # ── Drift detection ──────────────────────────────────────────────────

    def check_drift_single(self, sub_path: str, source: str = "index") -> SubmoduleStatus:
        """Check drift for a single submodule."""
        gitlink = self.get_gitlink_sha(sub_path, source=source)
        if not gitlink:
            return SubmoduleStatus(
                path=sub_path,
                drift_status=DriftStatus.SKIP,
                detail="no gitlink found",
            )

        remote_sha = self.get_remote_main_sha(sub_path)
        if not remote_sha:
            return SubmoduleStatus(
                path=sub_path,
                drift_status=DriftStatus.SKIP,
                gitlink_sha=gitlink,
                detail="no origin/main",
            )

        if gitlink == remote_sha:
            return SubmoduleStatus(
                path=sub_path,
                drift_status=DriftStatus.ALIGNED,
                gitlink_sha=gitlink,
                remote_sha=remote_sha,
            )

        if self.is_ancestor(gitlink, remote_sha, sub_path):
            return SubmoduleStatus(
                path=sub_path,
                drift_status=DriftStatus.BEHIND,
                gitlink_sha=gitlink,
                remote_sha=remote_sha,
                detail="gitlink is ancestor of origin/main (stale but reachable)",
            )

        if self.is_ancestor(remote_sha, gitlink, sub_path):
            return SubmoduleStatus(
                path=sub_path,
                drift_status=DriftStatus.AHEAD,
                gitlink_sha=gitlink,
                remote_sha=remote_sha,
                detail="gitlink is ahead of origin/main (local has unpushed commits)",
            )

        if self._is_shallow(sub_path):
            return SubmoduleStatus(
                path=sub_path,
                drift_status=DriftStatus.UNVERIFIABLE,
                gitlink_sha=gitlink,
                remote_sha=remote_sha,
                detail="shallow clone — ancestry cannot be verified",
            )

        return SubmoduleStatus(
            path=sub_path,
            drift_status=DriftStatus.DIVERGED,
            gitlink_sha=gitlink,
            remote_sha=remote_sha,
            detail="gitlink NOT on origin/main — code may be invisible from root",
        )

    def detect_drift(self, source: str = "index") -> DriftReport:
        """Detect drift across all submodules.

        Args:
            source: Where to read gitlink from ('index', 'head', 'worktree').

        Returns:
            DriftReport with per-submodule status.
        """
        report = DriftReport()
        submodules = self.get_submodule_paths()

        for sub_path in sorted(submodules):
            status = self.check_drift_single(sub_path, source=source)
            report.submodules.append(status)
            report.total += 1

            if status.drift_status == DriftStatus.ALIGNED:
                report.aligned += 1
            elif status.drift_status == DriftStatus.BEHIND:
                report.behind += 1
            elif status.drift_status == DriftStatus.AHEAD:
                report.ahead += 1
            elif status.drift_status == DriftStatus.DIVERGED:
                report.diverged += 1
            elif status.drift_status == DriftStatus.SKIP:
                report.skipped += 1
            elif status.drift_status == DriftStatus.UNVERIFIABLE:
                report.unverifiable += 1
            elif status.drift_status == DriftStatus.ERROR:
                report.error += 1

        return report

    # ── Pointer update ───────────────────────────────────────────────────

    def update_pointer(self, sub_path: str, target_sha: str) -> bool:
        """Update the root gitlink to point to target_sha.

        Args:
            sub_path: Submodule path relative to repo root.
            target_sha: The commit SHA to point to.

        Returns:
            True if the update succeeded.
        """
        result = self._git(
            "update-index",
            "--cacheinfo",
            f"160000,{target_sha},{sub_path}",
        )
        if result.returncode != 0:
            return False

        # Also checkout the submodule to the target commit
        sub_dir = self.repo_root / sub_path
        result = self._git("checkout", "--detach", target_sha, cwd=sub_dir)
        return result.returncode == 0

    def restore_pointer(self, sub_path: str, sha: str) -> bool:
        """Restore a submodule pointer to a previous SHA (rollback).

        Args:
            sub_path: Submodule path relative to repo root.
            sha: The commit SHA to restore to.

        Returns:
            True if the restore succeeded.
        """
        return self.update_pointer(sub_path, sha)

    def verify_pointer(self, sub_path: str, expected_sha: str) -> bool:
        """Verify that a submodule pointer matches expected SHA.

        Args:
            sub_path: Submodule path relative to repo root.
            expected_sha: The expected commit SHA.

        Returns:
            True if the current gitlink matches expected_sha.
        """
        current = self.get_gitlink_sha(sub_path, source="index")
        return current == expected_sha

    def verify_reachable(self, sub_path: str, sha: str) -> bool:
        """Verify that a SHA is reachable from the submodule's remote.

        Args:
            sub_path: Submodule path relative to repo root.
            sha: The commit SHA to verify.

        Returns:
            True if the SHA is reachable from origin/main or origin/HEAD.
        """
        sub_dir = self.repo_root / sub_path
        # Check if the commit exists locally in the submodule
        result = self._git("cat-file", "-t", sha, cwd=sub_dir)
        if result.returncode != 0:
            return False
        # Check if it's an ancestor of origin/main
        remote_sha = self.get_remote_main_sha(sub_path)
        if not remote_sha:
            return False
        return self.is_ancestor(sha, remote_sha, sub_path) or sha == remote_sha

    # ── Auto-update ──────────────────────────────────────────────────────

    def auto_update(
        self,
        apply: bool = False,
        strict: bool = False,
    ) -> UpdateReport:
        """Auto-update stale or diverged submodule pointers.

        Args:
            apply: If True, actually update pointers. If False, dry-run.
            strict: If True, also update 'behind' (stale) pointers.

        Returns:
            UpdateReport with per-submodule results.
        """
        drift_report = self.detect_drift()
        update_report = UpdateReport()

        # Determine which submodules need updating
        targets = []
        for status in drift_report.submodules:
            if status.drift_status == DriftStatus.DIVERGED:
                targets.append(status)
            elif status.drift_status == DriftStatus.BEHIND and (strict or self.strict):
                targets.append(status)

        for status in targets:
            update_report.attempted += 1
            sub_path = status.path
            target_sha = status.remote_sha

            if not target_sha:
                status.update_result = UpdateResult.SKIPPED
                status.detail = "no remote SHA available"
                update_report.skipped += 1
                update_report.results.append(status)
                continue

            # Save previous SHA for rollback
            previous_sha = self.get_gitlink_sha(sub_path, source="index")
            status.previous_sha = previous_sha

            if not apply:
                status.update_result = UpdateResult.UPDATED
                status.detail = f"would update -> {target_sha[:12]}"
                update_report.updated += 1
                update_report.results.append(status)
                continue

            # Apply the update
            success = self.update_pointer(sub_path, target_sha)
            if not success:
                status.update_result = UpdateResult.FAILED
                status.detail = "update_pointer failed"
                update_report.failed += 1
                update_report.results.append(status)
                continue

            # Verify the update
            if not self.verify_pointer(sub_path, target_sha):
                # Rollback
                if previous_sha:
                    self.restore_pointer(sub_path, previous_sha)
                status.update_result = UpdateResult.ROLLED_BACK
                status.detail = "verification failed, rolled back"
                update_report.rolled_back += 1
                update_report.results.append(status)
                continue

            # Verify reachability
            if not self.verify_reachable(sub_path, target_sha):
                # Rollback
                if previous_sha:
                    self.restore_pointer(sub_path, previous_sha)
                status.update_result = UpdateResult.ROLLED_BACK
                status.detail = "reachability check failed, rolled back"
                update_report.rolled_back += 1
                update_report.results.append(status)
                continue

            status.update_result = UpdateResult.UPDATED
            status.detail = f"updated -> {target_sha[:12]}"
            update_report.updated += 1
            update_report.results.append(status)

        return update_report

    # ── Integrity check ──────────────────────────────────────────────────

    def check_integrity(self) -> DriftReport:
        """Run a full integrity check on all submodule pointers.

        This is a comprehensive check that verifies:
        1. All gitlinks are valid (point to existing commits)
        2. All gitlinks are reachable from submodule remotes
        3. No diverged pointers exist

        Returns:
            DriftReport with integrity status.
        """
        report = DriftReport()
        submodules = self.get_submodule_paths()

        for sub_path in sorted(submodules):
            gitlink = self.get_gitlink_sha(sub_path, source="index")
            if not gitlink:
                report.submodules.append(
                    SubmoduleStatus(
                        path=sub_path,
                        drift_status=DriftStatus.SKIP,
                        detail="no gitlink found",
                    )
                )
                report.skipped += 1
                report.total += 1
                continue

            # Verify the commit exists in the submodule
            sub_dir = self.repo_root / sub_path
            result = self._git("cat-file", "-t", gitlink, cwd=sub_dir)
            if result.returncode != 0:
                report.submodules.append(
                    SubmoduleStatus(
                        path=sub_path,
                        drift_status=DriftStatus.ERROR,
                        gitlink_sha=gitlink,
                        detail="gitlink commit not found in submodule",
                    )
                )
                report.error += 1
                report.total += 1
                continue

            # Check reachability from remote
            remote_sha = self.get_remote_main_sha(sub_path)
            if not remote_sha:
                report.submodules.append(
                    SubmoduleStatus(
                        path=sub_path,
                        drift_status=DriftStatus.SKIP,
                        gitlink_sha=gitlink,
                        detail="no origin/main available",
                    )
                )
                report.skipped += 1
                report.total += 1
                continue

            if gitlink == remote_sha:
                report.submodules.append(
                    SubmoduleStatus(
                        path=sub_path,
                        drift_status=DriftStatus.ALIGNED,
                        gitlink_sha=gitlink,
                        remote_sha=remote_sha,
                    )
                )
                report.aligned += 1
            elif self.is_ancestor(gitlink, remote_sha, sub_path):
                report.submodules.append(
                    SubmoduleStatus(
                        path=sub_path,
                        drift_status=DriftStatus.BEHIND,
                        gitlink_sha=gitlink,
                        remote_sha=remote_sha,
                        detail="stale but reachable",
                    )
                )
                report.behind += 1
            elif self.is_ancestor(remote_sha, gitlink, sub_path):
                report.submodules.append(
                    SubmoduleStatus(
                        path=sub_path,
                        drift_status=DriftStatus.AHEAD,
                        gitlink_sha=gitlink,
                        remote_sha=remote_sha,
                        detail="ahead of remote",
                    )
                )
                report.ahead += 1
            else:
                report.submodules.append(
                    SubmoduleStatus(
                        path=sub_path,
                        drift_status=DriftStatus.DIVERGED,
                        gitlink_sha=gitlink,
                        remote_sha=remote_sha,
                        detail="not on remote main",
                    )
                )
                report.diverged += 1

            report.total += 1

        return report


def main() -> int:
    """CLI entry point for submodule auto management."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Submodule pointer automation — drift detection, auto-update, rollback",
    )
    parser.add_argument("--check", action="store_true", help="Check for drift (read-only)")
    parser.add_argument("--fix", action="store_true", help="Show fix suggestions (dry-run)")
    parser.add_argument("--apply", action="store_true", help="Apply fixes (requires --fix)")
    parser.add_argument("--strict", action="store_true", help="Treat 'behind' as drift")
    parser.add_argument("--integrity", action="store_true", help="Run full integrity check")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--root", type=Path, default=None, help="Repository root")
    args = parser.parse_args()

    repo_root = args.root or Path(__file__).resolve().parents[1]
    mgr = SubmoduleAutoManager(repo_root=repo_root, strict=args.strict)

    if args.integrity:
        report = mgr.check_integrity()
        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            _print_drift_report(report)
        return 1 if report.has_drift else 0

    if args.fix:
        update_report = mgr.auto_update(apply=args.apply, strict=args.strict)
        if args.json:
            print(json.dumps(update_report.to_dict(), indent=2))
        else:
            _print_update_report(update_report, dry_run=not args.apply)
        return 0

    # Default: check
    report = mgr.detect_drift()
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        _print_drift_report(report)
    return 1 if report.has_drift else 0


def _print_drift_report(report: DriftReport) -> None:
    """Print a human-readable drift report."""
    print("== submodule drift report ==")
    for s in report.submodules:
        if s.drift_status == DriftStatus.ALIGNED:
            print(f"  OK {s.path}: {(s.gitlink_sha or '')[:12]}")
        elif s.drift_status == DriftStatus.BEHIND:
            print(f"  WARN {s.path}: {(s.gitlink_sha or '')[:12]} <- remote {(s.remote_sha or '')[:12]} (stale)")
        elif s.drift_status == DriftStatus.AHEAD:
            print(f"  OK {s.path}: {(s.gitlink_sha or '')[:12]} (ahead, non-blocking)")
        elif s.drift_status == DriftStatus.DIVERGED:
            print(f"  FAIL {s.path}: {(s.gitlink_sha or '')[:12]} NOT on remote {(s.remote_sha or '')[:12]}")
        elif s.drift_status == DriftStatus.SKIP:
            print(f"  SKIP {s.path}: {s.detail or 'skipped'}")
        elif s.drift_status == DriftStatus.UNVERIFIABLE:
            print(f"  OK {s.path}: {(s.gitlink_sha or '')[:12]} (shallow, unverifiable)")

    print(
        f"\n  Total: {report.total} | {report.aligned} aligned | "
        f"{report.behind} behind | {report.ahead} ahead | "
        f"{report.diverged} DIVERGED | {report.skipped} skipped"
    )

    if report.has_drift:
        print(f"\n  {report.diverged} DIVERGED — root pointer targets side branch!")
        print("  Run --fix for suggestions, --fix --apply to execute")


def _print_update_report(report: UpdateReport, dry_run: bool = True) -> None:
    """Print a human-readable update report."""
    mode = "DRY-RUN" if dry_run else "APPLIED"
    print(f"== submodule auto-update ({mode}) ==")
    for r in report.results:
        icon = {
            UpdateResult.UPDATED: "FIXED",
            UpdateResult.SKIPPED: "SKIP",
            UpdateResult.FAILED: "FAIL",
            UpdateResult.ROLLED_BACK: "ROLLBACK",
        }.get(r.update_result, "?")
        print(f"  {icon} {r.path}: {r.detail or ''}")

    print(
        f"\n  Attempted: {report.attempted} | Updated: {report.updated} | "
        f"Skipped: {report.skipped} | Failed: {report.failed} | "
        f"Rolled back: {report.rolled_back}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
