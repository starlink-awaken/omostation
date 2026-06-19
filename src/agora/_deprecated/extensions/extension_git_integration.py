from __future__ import annotations

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Prime'
Layer: L3
Domain: D-Gateway
Summary: 'Extension Git Integration - Clone, sync and version extensions from Git repos'
Tags: [extension, git, vcs, version-control, sync]
Authority: organs/D-Gateway/AGENTS.md
---
"""


# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Gateway_Organ ≡ Extension_Git_Integration
# 内涵 ≝ {Clone, Pull, Checkout, Tag, Branch}
# 外延 ≝ {g | g ∈ D-Gateway ∧ manages(g, Git_Extension)}
# 功能 ⊢ {Git_Clone, Version_Resolution, Auto_Update, Manifest_Validation}
# =============================================================================
import logging  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

_log = logging.getLogger(__name__)


@dataclass
class GitSource:
    """Git source specification."""

    url: str
    ref: str = "main"  # branch, tag, or commit
    subdir: str | None = None  # subdirectory within repo
    auth_token: str | None = None


@dataclass
class GitCloneResult:
    """Result of git clone operation."""

    success: bool
    local_path: Path | None = None
    commit_hash: str | None = None
    version_tag: str | None = None
    manifest: dict | None = None
    error: str | None = None


@dataclass
class GitSyncResult:
    """Result of git sync operation."""

    success: bool
    updated: bool = False
    previous_commit: str | None = None
    new_commit: str | None = None
    changes: list[str] | None = None
    error: str | None = None


class ExtensionGitIntegration:
    """
    Extension Git Integration - Clone, sync and version extensions from Git repos.

    Architecture Compliance:
    - Located in D-Gateway (L3) ✅
    - Uses subprocess for git operations ✅
    - Validates manifest after clone ✅
    - Supports semantic versioning tags ✅

    Features:
    - Clone from any Git repository
    - Checkout specific refs (branch/tag/commit)
    - Auto-detect semantic version tags
    - Sync with upstream changes
    - Subdirectory support for monorepos
    """

    DEFAULT_CLONE_DIR = Path("config/extensions/git_sources")
    SEMVER_PATTERN = re.compile(
        r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:-(?P<prerelease>[\w.]+))?(?:\+(?P<build>[\w.]+))?$"
    )

    def __init__(
        self,
        clone_dir: Path | None = None,
        git_executable: str = "git",
    ) -> None:

        self.clone_dir = clone_dir or self.DEFAULT_CLONE_DIR
        self.clone_dir.mkdir(parents=True, exist_ok=True)
        self.git_executable = git_executable

        # Verify git is available
        if not self._check_git():
            _log.warning("Git executable not found: %s", git_executable)

        _log.info("ExtensionGitIntegration initialized: %s", self.clone_dir)

    def _check_git(self) -> bool:
        """Check if git executable is available."""
        try:
            result = subprocess.run(
                [self.git_executable, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (OSError, subprocess.SubprocessError, ValueError):
            return False

    def _run_git(
        self, args: list[str], cwd: Path | None = None, env: dict | None = None
    ) -> tuple[int, str, str]:
        """Run git command."""
        cmd = [self.git_executable] + args

        # Prepare environment
        run_env = os.environ.copy()
        if env:
            run_env.update(env)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=cwd,
                env=run_env,
                timeout=60,
            )
            return result.returncode, result.stdout, result.stderr

        except subprocess.TimeoutExpired:
            return -1, "", "Timeout"
        except (OSError, subprocess.SubprocessError, ValueError) as e:
            return -1, "", str(e)

    # =====================================================================
    # Clone Operations
    # =====================================================================

    def clone(
        self, source: GitSource, target_name: str | None = None
    ) -> GitCloneResult:
        """
        Clone an extension from Git repository.

        Args:
            source: Git source specification
            target_name: Local name for the clone (default: derived from URL)

        Returns:
            GitCloneResult
        """
        if not self._check_git():
            return GitCloneResult(
                success=False,
                error="Git not available",
            )

        # Determine target directory
        if target_name is None:
            target_name = self._derive_name_from_url(source.url)

        target_path = self.clone_dir / target_name

        # Check if already exists
        if target_path.exists():
            return GitCloneResult(
                success=False,
                error=f"Target already exists: {target_path}",
            )

        # Create temp directory for initial clone
        temp_dir = Path(tempfile.mkdtemp(prefix=f"git_clone_{target_name}_"))

        try:
            # Clone with minimal history
            clone_args = [
                "clone",
                "--depth",
                "1",
                "--single-branch",
                "--branch",
                source.ref,
                source.url,
                str(temp_dir),
            ]

            # Add auth if token provided
            env = None
            if source.auth_token:
                env = self._setup_git_auth(source.url, source.auth_token)

            returncode, stdout, stderr = self._run_git(clone_args, env=env)

            if returncode != 0:
                return GitCloneResult(
                    success=False,
                    error=f"Clone failed: {stderr}",
                )

            # Get commit hash
            commit_hash = self._get_commit_hash(temp_dir)

            # Handle subdirectory if specified
            if source.subdir:
                source_dir = temp_dir / source.subdir
                if not source_dir.exists():
                    return GitCloneResult(
                        success=False,
                        error=f"Subdirectory not found: {source.subdir}",
                    )
            else:
                source_dir = temp_dir

            # Validate manifest
            manifest = self._read_manifest(source_dir)
            if not manifest:
                return GitCloneResult(
                    success=False,
                    error="No valid manifest.json found",
                )

            # Move to final location
            shutil.move(str(source_dir), str(target_path))

            # Store metadata
            self._store_git_metadata(target_path, source, commit_hash or "")

            # Detect version tag
            version_tag = self._detect_version_tag(target_path)

            return GitCloneResult(
                success=True,
                local_path=target_path,
                commit_hash=commit_hash,
                version_tag=version_tag,
                manifest=manifest,
            )

        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as e:
            _log.exception("Clone failed: %s", e)
            return GitCloneResult(
                success=False,
                error=str(e),
            )
        finally:
            # Cleanup temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    def clone_with_version(
        self,
        url: str,
        version_spec: str,
        target_name: str | None = None,
        auth_token: str | None = None,
    ) -> GitCloneResult:
        """
        Clone specific version using semantic versioning.

        Args:
            url: Git repository URL
            version_spec: Version specification (e.g., "^1.2.0", ">=2.0.0", "1.2.3")
            target_name: Local name
            auth_token: Authentication token

        Returns:
            GitCloneResult
        """
        # Create temp clone to list tags
        temp_dir = Path(tempfile.mkdtemp(prefix="git_version_check_"))

        try:
            # Shallow clone
            clone_args = ["clone", "--depth", "1", url, str(temp_dir)]
            env = self._setup_git_auth(url, auth_token) if auth_token else None

            returncode, _, stderr = self._run_git(clone_args, env=env)
            if returncode != 0:
                return GitCloneResult(
                    success=False,
                    error=f"Clone failed: {stderr}",
                )

            # Fetch all tags
            self._run_git(["fetch", "--tags", "--depth", "1"], cwd=temp_dir, env=env)

            # Get available versions
            versions = self._list_semver_tags(temp_dir)

            # Resolve version
            resolved_version = self._resolve_version(version_spec, versions)
            if not resolved_version:
                return GitCloneResult(
                    success=False,
                    error=f"Could not resolve version: {version_spec}",
                )

            # Now do proper clone with resolved version
            source = GitSource(
                url=url,
                ref=resolved_version,
                auth_token=auth_token,
            )

            return self.clone(source, target_name)

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    # =====================================================================
    # Sync Operations
    # =====================================================================

    def sync(self, target_name: str, auto_update: bool = False) -> GitSyncResult:
        """
        Sync extension with upstream repository.

        Args:
            target_name: Local extension name
            auto_update: Whether to automatically apply updates

        Returns:
            GitSyncResult
        """
        target_path = self.clone_dir / target_name

        if not target_path.exists():
            return GitSyncResult(
                success=False,
                error=f"Extension not found: {target_name}",
            )

        # Read metadata
        metadata = self._read_git_metadata(target_path)
        if not metadata:
            return GitSyncResult(
                success=False,
                error="No git metadata found",
            )

        # Get current commit
        previous_commit = self._get_commit_hash(target_path)

        try:
            # Fetch updates
            source = GitSource(
                url=metadata["url"],
                ref=metadata["ref"],
                auth_token=metadata.get("auth_token"),
            )
            env = (
                self._setup_git_auth(source.url, source.auth_token)
                if source.auth_token
                else None
            )

            returncode, _, stderr = self._run_git(
                ["fetch", "origin", source.ref],
                cwd=target_path,
                env=env,
            )

            if returncode != 0:
                return GitSyncResult(
                    success=False,
                    error=f"Fetch failed: {stderr}",
                )

            # Check for changes
            returncode, stdout, _ = self._run_git(
                ["rev-list", "HEAD..origin/" + source.ref, "--oneline"],
                cwd=target_path,
            )

            changes = stdout.strip().split("\n") if stdout.strip() else []

            if not changes or changes == [""]:
                return GitSyncResult(
                    success=True,
                    updated=False,
                )

            if not auto_update:
                return GitSyncResult(
                    success=True,
                    updated=False,
                    previous_commit=previous_commit,
                    changes=changes,
                )

            # Pull updates
            returncode, _, stderr = self._run_git(
                ["pull", "origin", source.ref],
                cwd=target_path,
                env=env,
            )

            if returncode != 0:
                return GitSyncResult(
                    success=False,
                    error=f"Pull failed: {stderr}",
                )

            new_commit = self._get_commit_hash(target_path)

            # Update metadata
            self._store_git_metadata(target_path, source, new_commit or "")

            return GitSyncResult(
                success=True,
                updated=True,
                previous_commit=previous_commit,
                new_commit=new_commit,
                changes=changes,
            )

        except (
            AttributeError,
            KeyError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as e:
            _log.exception("Sync failed: %s", e)
            return GitSyncResult(
                success=False,
                error=str(e),
            )

    def sync_all(self, auto_update: bool = False) -> dict[str, GitSyncResult]:
        """Sync all git-sourced extensions."""
        results = {}

        for item in self.clone_dir.iterdir():
            if item.is_dir() and (item / ".git").exists():
                results[item.name] = self.sync(item.name, auto_update)

        return results

    # =====================================================================
    # Version Management
    # =====================================================================

    def checkout_version(self, target_name: str, version: str) -> GitCloneResult:
        """Checkout specific version (tag or commit)."""
        target_path = self.clone_dir / target_name

        if not target_path.exists():
            return GitCloneResult(
                success=False,
                error=f"Extension not found: {target_name}",
            )

        try:
            # Try to checkout as tag first
            returncode, _, _ = self._run_git(
                ["checkout", f"tags/{version}"],
                cwd=target_path,
            )

            if returncode != 0:
                # Try as branch
                returncode, _, _ = self._run_git(
                    ["checkout", version],
                    cwd=target_path,
                )

                if returncode != 0:
                    # Try as commit
                    returncode, _, stderr = self._run_git(
                        ["checkout", version],
                        cwd=target_path,
                    )

                    if returncode != 0:
                        return GitCloneResult(
                            success=False,
                            error=f"Checkout failed: {stderr}",
                        )

            commit_hash = self._get_commit_hash(target_path)
            manifest = self._read_manifest(target_path)

            # Update metadata
            metadata = self._read_git_metadata(target_path)
            if metadata:
                source = GitSource(
                    url=metadata["url"],
                    ref=version,
                    auth_token=metadata.get("auth_token"),
                )
                self._store_git_metadata(target_path, source, commit_hash or "")

            return GitCloneResult(
                success=True,
                local_path=target_path,
                commit_hash=commit_hash,
                version_tag=version if self.SEMVER_PATTERN.match(version) else None,
                manifest=manifest,
            )

        except (
            AttributeError,
            KeyError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as e:
            return GitCloneResult(
                success=False,
                error=str(e),
            )

    def list_available_versions(self, target_name: str) -> list[str]:
        """List available semantic versions for extension."""
        target_path = self.clone_dir / target_name

        if not target_path.exists():
            return []

        return self._list_semver_tags(target_path)

    def get_current_version(self, target_name: str) -> str | None:
        """Get currently checked out version."""
        target_path = self.clone_dir / target_name

        if not target_path.exists():
            return None

        # Try to get tag
        returncode, stdout, _ = self._run_git(
            ["describe", "--tags", "--exact-match"],
            cwd=target_path,
        )

        if returncode == 0:
            return stdout.strip()

        # Fallback to commit hash
        return self._get_commit_hash(target_path)

    # =====================================================================
    # Utility Operations
    # =====================================================================

    def remove(self, target_name: str) -> bool:
        """Remove cloned extension."""
        target_path = self.clone_dir / target_name

        if not target_path.exists():
            return False

        shutil.rmtree(target_path)
        return True

    def list_cloned(self) -> list[dict[str, Any]]:
        """List all cloned extensions."""
        result = []

        for item in self.clone_dir.iterdir():
            if item.is_dir() and (item / ".git").exists():
                metadata = self._read_git_metadata(item)
                manifest = self._read_manifest(item)

                result.append(
                    {
                        "name": item.name,
                        "url": metadata.get("url") if metadata else None,
                        "ref": metadata.get("ref") if metadata else None,
                        "commit": self._get_commit_hash(item),
                        "version": self.get_current_version(item.name),
                        "manifest": manifest,
                    }
                )

        return result

    # =====================================================================
    # Helpers
    # =====================================================================

    def _derive_name_from_url(self, url: str) -> str:
        """Derive local name from Git URL."""
        # Remove protocol
        name = url.split("://")[-1]
        # Remove domain
        name = name.split("/")[-1]
        # Remove .git suffix
        if name.endswith(".git"):
            name = name[:-4]
        return name

    def _setup_git_auth(self, url: str, token: str) -> dict:
        """Setup git authentication environment."""
        env = os.environ.copy()

        if "github.com" in url:
            env["GIT_ASKPASS"] = "echo"
            env["GIT_USERNAME"] = token
            env["GIT_PASSWORD"] = "x-oauth-basic"  # noqa: S105
        elif "gitlab.com" in url:
            env["GIT_ASKPASS"] = "echo"
            env["GIT_USERNAME"] = "oauth2"
            env["GIT_PASSWORD"] = token

        return env

    def _get_commit_hash(self, repo_path: Path) -> str | None:
        """Get current commit hash."""
        returncode, stdout, _ = self._run_git(
            ["rev-parse", "HEAD"],
            cwd=repo_path,
        )
        return stdout.strip() if returncode == 0 else None

    def _read_manifest(self, path: Path) -> dict | None:
        """Read extension manifest."""
        import json

        manifest_file = path / "manifest.json"
        if not manifest_file.exists():
            return None

        try:
            with open(manifest_file, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def _store_git_metadata(
        self, path: Path, source: GitSource, commit_hash: str
    ) -> None:
        """Store git metadata."""
        import json

        metadata = {
            "url": source.url,
            "ref": source.ref,
            "subdir": source.subdir,
            "commit_hash": commit_hash,
            "cloned_at": time.time(),
        }

        # Don't store auth token in metadata

        metadata_file = path / ".git_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

    def _read_git_metadata(self, path: Path) -> dict | None:
        """Read git metadata."""
        import json

        metadata_file = path / ".git_metadata.json"
        if not metadata_file.exists():
            return None

        try:
            with open(metadata_file, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def _list_semver_tags(self, repo_path: Path) -> list[str]:
        """List semantic version tags."""
        returncode, stdout, _ = self._run_git(
            ["tag", "--list"],
            cwd=repo_path,
        )

        if returncode != 0:
            return []

        tags = []
        for line in stdout.strip().split("\n"):
            tag = line.strip()
            if self.SEMVER_PATTERN.match(tag):
                tags.append(tag)

        # Sort by semantic version
        return sorted(tags, key=self._semver_sort_key, reverse=True)

    def _detect_version_tag(self, repo_path: Path) -> str | None:
        """Detect current version tag."""
        returncode, stdout, _ = self._run_git(
            ["describe", "--tags", "--exact-match"],
            cwd=repo_path,
        )

        if returncode == 0:
            tag = stdout.strip()
            if self.SEMVER_PATTERN.match(tag):
                return tag

        return None

    def _semver_sort_key(self, version: str) -> tuple:
        """Sort key for semantic versions."""
        match = self.SEMVER_PATTERN.match(version)
        if not match:
            return (0, 0, 0, "", "")

        return (
            int(match.group("major")),
            int(match.group("minor")),
            int(match.group("patch")),
            match.group("prerelease") or "",
            match.group("build") or "",
        )

    def _resolve_version(self, spec: str, available: list[str]) -> str | None:
        """Resolve version specification to available version."""
        if not available:
            return None

        # Exact match
        if spec in available:
            return spec

        # Caret (^) - compatible with version
        if spec.startswith("^"):
            base_version = spec[1:]
            # Find highest compatible version
            for version in available:
                if self._is_compatible(base_version, version):
                    return version

        # Tilde (~) - approximately equivalent
        if spec.startswith("~"):
            base_version = spec[1:]
            for version in available:
                if self._is_approximate(base_version, version):
                    return version

        # Greater than/equal (>=)
        if spec.startswith(">="):
            min_version = spec[2:]
            for version in available:
                if self._compare_versions(version, min_version) >= 0:
                    return version

        # Default: return highest available
        return available[0]

    def _is_compatible(self, base: str, candidate: str) -> bool:
        """Check if candidate is compatible with base (^)."""
        base_match = self.SEMVER_PATTERN.match(base)
        cand_match = self.SEMVER_PATTERN.match(candidate)

        if not base_match or not cand_match:
            return False

        base_major = int(base_match.group("major"))
        cand_major = int(cand_match.group("major"))

        if cand_major != base_major:
            return False

        return self._compare_versions(candidate, base) >= 0

    def _is_approximate(self, base: str, candidate: str) -> bool:
        """Check if candidate is approximately equivalent (~)."""
        base_match = self.SEMVER_PATTERN.match(base)
        cand_match = self.SEMVER_PATTERN.match(candidate)

        if not base_match or not cand_match:
            return False

        return base_match.group("major") == cand_match.group(
            "major"
        ) and base_match.group("minor") == cand_match.group("minor")

    def _compare_versions(self, v1: str, v2: str) -> int:
        """Compare two versions. Returns -1, 0, or 1."""
        m1 = self.SEMVER_PATTERN.match(v1)
        m2 = self.SEMVER_PATTERN.match(v2)

        if not m1 or not m2:
            return 0

        for part in ["major", "minor", "patch"]:
            p1 = int(m1.group(part))
            p2 = int(m2.group(part))
            if p1 != p2:
                return 1 if p1 > p2 else -1

        return 0


# Singleton
_git_integration: ExtensionGitIntegration | None = None


def get_extension_git_integration() -> ExtensionGitIntegration:
    """Get singleton instance."""
    global _git_integration
    if _git_integration is None:
        _git_integration = ExtensionGitIntegration()
    return _git_integration
