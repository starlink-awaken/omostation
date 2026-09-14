"""GitHub connector — issues, PRs, and repository management via gh CLI.

Uses subprocess calls to `gh` (GitHub CLI) for all operations.
No additional authentication needed — relies on existing gh auth session.
"""

from __future__ import annotations

import json
import logging
import subprocess
from typing import Any

from iris.base import BaseConnector, SyncResult
from iris.models import Article, Bookmark, KnowledgeArtifact

logger = logging.getLogger(__name__)

_GH_BIN = "gh"


def _gh_json(args: list[str], timeout: int = 30) -> Any:
    """Run a `gh` command that returns JSON and parse the output.

    Args:
        args: List of CLI arguments (excluding 'gh' itself).
        timeout: Timeout in seconds for the subprocess call.

    Returns:
        Parsed JSON (list or dict), or None on failure.
    """
    try:
        result = subprocess.run(
            [_GH_BIN] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            logger.debug("gh %s failed: %s", " ".join(args), stderr)
            return None
        if not result.stdout.strip():
            return None
        return json.loads(result.stdout)
    except FileNotFoundError:
        logger.debug("gh CLI not found")
        return None
    except json.JSONDecodeError as e:
        logger.warning("gh JSON parse error: %s", e)
        return None
    except subprocess.TimeoutExpired:
        logger.warning("gh command timed out: %s", " ".join(args))
        return None
    except Exception as e:
        logger.warning("gh command error: %s", e)
        return None


def _gh_text(args: list[str], timeout: int = 30) -> str | None:
    """Run a `gh` command and return stdout text.

    Args:
        args: List of CLI arguments (excluding 'gh' itself).
        timeout: Timeout in seconds.

    Returns:
        Stripped stdout text, or None on failure.
    """
    try:
        result = subprocess.run(
            [_GH_BIN] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None


def _issue_to_article(item: dict, repo: str) -> Article:
    """Convert a gh issue JSON object to an Article."""
    number = item["number"]
    author = item.get("author", {}) or {}
    author_login = author.get("login", "") if isinstance(author, dict) else ""
    return Article(
        id=f"github/issue/{repo}#{number}",
        title=item.get("title", ""),
        content=item.get("body", "") or "",
        url=item.get("url", ""),
        author=author_login,
        platform="github",
        created_at=item.get("createdAt", ""),
        updated_at=item.get("updatedAt", ""),
    )


def _pr_to_article(item: dict, repo: str) -> Article:
    """Convert a gh PR JSON object to an Article."""
    number = item["number"]
    author = item.get("author", {}) or {}
    author_login = author.get("login", "") if isinstance(author, dict) else ""
    return Article(
        id=f"github/pr/{repo}#{number}",
        title=item.get("title", ""),
        content=item.get("body", "") or "",
        url=item.get("url", ""),
        author=author_login,
        platform="github",
        created_at=item.get("createdAt", ""),
        updated_at=item.get("updatedAt", ""),
    )


def _repo_to_bookmark(item: dict) -> Bookmark:
    """Convert a gh repo JSON object to a Bookmark."""
    owner = item.get("owner", {}) or {}
    owner_login = owner.get("login", "") if isinstance(owner, dict) else ""
    name = item.get("name", "")
    full_name = f"{owner_login}/{name}" if owner_login and name else name
    return Bookmark(
        id=f"github/repo/{full_name}",
        title=name,
        url=item.get("url", ""),
        description=item.get("description", "") or "",
        platform="github",
        created_at=item.get("createdAt", ""),
        updated_at=item.get("updatedAt", ""),
    )


def _get_owner_repo_from_id(item_id: str) -> tuple[str, str]:
    """Extract owner/repo from an ID of the form 'owner/repo'.

    Returns:
        Tuple of (owner, repo).
    """
    parts = item_id.split("/")
    if len(parts) >= 2:
        return parts[0], parts[1]
    return parts[0], ""


class GitHubConnector(BaseConnector):
    """Connector for GitHub via the `gh` CLI.

    All operations use subprocess calls to `gh`, which must be installed
    and authenticated. No additional auth configuration is needed.
    """

    name = "github"
    display_name = "GitHub"

    def __init__(self) -> None:
        self._available: bool | None = None

    # ── Availability ──────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Check if gh CLI is installed and functional.

        Returns:
            True if `gh --version` succeeds.
        """
        if self._available is not None:
            return self._available
        try:
            result = subprocess.run(
                [_GH_BIN, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self._available = result.returncode == 0
        except FileNotFoundError:
            self._available = False
        except Exception:
            self._available = False
        return self._available

    # ── BaseConnector interface ───────────────────────────────────────

    def list_items(
        self,
        limit: int = 20,
        cursor: str | None = None,
        tag: str | None = None,
        folder: str | None = None,
        subdir: str | None = None,
        chat_id: str | None = None,
    ) -> list[KnowledgeArtifact]:
        """Return a mixed list of recent issues, PRs, and repos (stars).

        Samples a few items of each type to provide a diverse feed.

        Args:
            limit: Total number of items to return.
            cursor: Not used (pagination not supported for mixed feeds).

        Returns:
            List of Article and Bookmark artifacts.
        """
        # Allocate ~40% to issues, ~40% to PRs, ~20% to repos
        issue_limit = max(3, int(limit * 0.4))
        pr_limit = max(3, int(limit * 0.4))
        repo_limit = max(2, limit - issue_limit - pr_limit)

        artifacts: list[KnowledgeArtifact] = []

        # Recent issues across all repos
        issues_data = _gh_json(
            [
                "issue",
                "list",
                "--limit",
                str(issue_limit),
                "--json",
                "number,title,body,url,author,createdAt,updatedAt,state,repository",
            ]
        )
        if isinstance(issues_data, list):
            for item in issues_data:
                repo_info = item.get("repository", {}) or {}
                repo_name = repo_info.get("nameWithOwner", "") if isinstance(repo_info, dict) else ""
                artifacts.append(_issue_to_article(item, repo_name))

        # Recent PRs across all repos
        prs_data = _gh_json(
            [
                "pr",
                "list",
                "--limit",
                str(pr_limit),
                "--json",
                "number,title,body,url,author,createdAt,updatedAt,state,repository",
            ]
        )
        if isinstance(prs_data, list):
            for item in prs_data:
                repo_info = item.get("repository", {}) or {}
                repo_name = repo_info.get("nameWithOwner", "") if isinstance(repo_info, dict) else ""
                artifacts.append(_pr_to_article(item, repo_name))

        # Recent repos (acts as "starred" / bookmarked)
        repos_data = _gh_json(
            ["repo", "list", "--limit", str(repo_limit), "--json", "name,owner,url,description,createdAt,updatedAt"]
        )
        if isinstance(repos_data, list):
            for item in repos_data:
                artifacts.append(_repo_to_bookmark(item))

        return artifacts[:limit]

    def get_item(self, id: str) -> KnowledgeArtifact | None:
        """Get a single GitHub item by ID.

        Supported ID formats:
        - ``repo:owner/repo`` — fetch repository details
        - ``issue:owner/repo:number`` — fetch a specific issue
        - ``pr:owner/repo:number`` — fetch a specific PR

        Args:
            id: Item identifier with type prefix.

        Returns:
            An Article or Bookmark, or None if not found.
        """
        if id.startswith("repo:"):
            full_name = id[len("repo:") :]
            data = _gh_json(
                ["repo", "view", full_name, "--json", "name,owner,url,description,createdAt,updatedAt,isFork"]
            )
            if isinstance(data, dict):
                return _repo_to_bookmark(data)
            return None

        if id.startswith("issue:"):
            rest = id[len("issue:") :]
            # rest = "owner/repo:number"
            try:
                owner_repo, number = rest.rsplit(":", 1)
            except ValueError:
                return None
            data = _gh_json(
                [
                    "issue",
                    "view",
                    number,
                    "--repo",
                    owner_repo,
                    "--json",
                    "number,title,body,url,author,createdAt,updatedAt,state",
                ]
            )
            if isinstance(data, dict):
                return _issue_to_article(data, owner_repo)
            return None

        if id.startswith("pr:"):
            rest = id[len("pr:") :]
            try:
                owner_repo, number = rest.rsplit(":", 1)
            except ValueError:
                return None
            data = _gh_json(
                [
                    "pr",
                    "view",
                    number,
                    "--repo",
                    owner_repo,
                    "--json",
                    "number,title,body,url,author,createdAt,updatedAt,state",
                ]
            )
            if isinstance(data, dict):
                return _pr_to_article(data, owner_repo)
            return None

        logger.debug("Unknown get_item id format: %s", id)
        return None

    def search(self, query: str, limit: int = 10) -> list[KnowledgeArtifact]:
        """Search GitHub issues, PRs, and repositories.

        Searches are performed in order: issues → PRs → repos,
        with the limit distributed across all three.

        Args:
            query: Free-text search query.
            limit: Maximum number of results to return.

        Returns:
            List of matching KnowledgeArtifacts.
        """
        artifacts: list[KnowledgeArtifact] = []

        # Search issues
        issue_limit = max(3, limit // 3)
        issues = _gh_json(
            [
                "search",
                "issues",
                query,
                "--limit",
                str(issue_limit),
                "--json",
                "number,title,body,url,author,createdAt,updatedAt,state,repository",
            ]
        )
        if isinstance(issues, list):
            for item in issues:
                repo_info = item.get("repository", {}) or {}
                repo_name = repo_info.get("nameWithOwner", "") if isinstance(repo_info, dict) else ""
                artifacts.append(_issue_to_article(item, repo_name))

        # Search PRs
        pr_limit = max(3, limit // 3)
        prs = _gh_json(
            [
                "search",
                "prs",
                query,
                "--limit",
                str(pr_limit),
                "--json",
                "number,title,body,url,author,createdAt,updatedAt,state,repository",
            ]
        )
        if isinstance(prs, list):
            for item in prs:
                repo_info = item.get("repository", {}) or {}
                repo_name = repo_info.get("nameWithOwner", "") if isinstance(repo_info, dict) else ""
                artifacts.append(_pr_to_article(item, repo_name))

        # Fill remaining with repos
        repo_limit = max(2, limit - len(artifacts))
        repos = _gh_json(
            [
                "search",
                "repos",
                query,
                "--limit",
                str(repo_limit),
                "--json",
                "name,owner,url,description,createdAt,updatedAt",
            ]
        )
        if isinstance(repos, list):
            for item in repos:
                artifacts.append(_repo_to_bookmark(item))

        return artifacts[:limit]

    def sync(self, dry_run: bool = False) -> SyncResult:
        """Scan all accessible repositories for new issues and PRs.

        Iterates over all repos visible to the authenticated user and
        fetches open issues and PRs for each.

        Args:
            dry_run: If True, report what would be synced without
                     fetching item details.

        Returns:
            SyncResult with count of items found.
        """
        repos = _gh_json(["repo", "list", "--limit", "100", "--json", "name,owner"])
        if not isinstance(repos, list):
            return SyncResult(
                connector_name=self.name,
                success=False,
                errors=["Failed to list repositories"],
                message="Could not retrieve repository list from GitHub",
            )

        total_found = 0
        errors: list[str] = []

        for repo_item in repos[:50]:  # Limit to 50 repos for performance
            owner_info = repo_item.get("owner", {}) or {}
            owner = owner_info.get("login", "") if isinstance(owner_info, dict) else ""
            repo_name = repo_item.get("name", "")
            owner_repo = f"{owner}/{repo_name}" if owner and repo_name else ""

            if not owner_repo:
                continue

            if dry_run:
                total_found += 1
                continue

            # Fetch open issues
            try:
                issues = _gh_json(
                    [
                        "issue",
                        "list",
                        "--repo",
                        owner_repo,
                        "--state",
                        "open",
                        "--limit",
                        "50",
                        "--json",
                        "number,title",
                    ]
                )
                if isinstance(issues, list):
                    total_found += len(issues)
            except Exception as e:
                errors.append(f"{owner_repo} issues: {e}")

            # Fetch open PRs
            try:
                prs = _gh_json(
                    [
                        "pr",
                        "list",
                        "--repo",
                        owner_repo,
                        "--state",
                        "open",
                        "--limit",
                        "50",
                        "--json",
                        "number,title",
                    ]
                )
                if isinstance(prs, list):
                    total_found += len(prs)
            except Exception as e:
                errors.append(f"{owner_repo} prs: {e}")

        status = "dry_run" if dry_run else "success"
        return SyncResult(
            connector_name=self.name,
            items_found=total_found,
            success=len(errors) == 0,
            errors=errors,
            message=f"Scanned repos, found {total_found} open issues/PRs [{status}]",
        )

    def status(self) -> dict[str, Any]:
        """Return connector health and configuration status.

        Returns:
            Dict with keys: available, authenticated, gh_version,
            user, repo_count, issue_count, pr_count, etc.
        """
        available = self.is_available()
        result: dict[str, Any] = {
            "available": available,
            "authenticated": False,
            "gh_version": "",
            "user": "",
            "repo_count": 0,
            "issue_count": 0,
            "pr_count": 0,
        }

        if not available:
            result["error"] = "gh CLI not found or not functional"
            return result

        # Version
        version = _gh_text(["--version"])
        if version:
            result["gh_version"] = version.split("\n")[0] if "\n" in version else version

        # Auth status
        auth_text = _gh_text(["auth", "status"])
        result["authenticated"] = auth_text is not None and "✓ Logged in" in auth_text
        if auth_text:
            for line in auth_text.split("\n"):
                if "account" in line.lower():
                    result["user"] = line.strip()

        # Count repos
        repos = _gh_json(["repo", "list", "--limit", "100", "--json", "name"])
        if isinstance(repos, list):
            result["repo_count"] = len(repos)

        # Note: gh CLI doesn't provide aggregate issue/PR counts
        # across all repos in a single call. We leave these as 0
        # for performance; individual repo queries can be done on demand.
        result["issue_count"] = 0
        result["pr_count"] = 0

        return result

    # ── GitHub-specific operations ────────────────────────────────────

    def list_repos(self, limit: int = 20) -> list[Bookmark]:
        """List the most recently active repositories.

        Args:
            limit: Maximum number of repositories to return.

        Returns:
            List of Bookmark artifacts representing repos.
        """
        data = _gh_json(
            ["repo", "list", "--limit", str(limit), "--json", "name,owner,url,description,createdAt,updatedAt"]
        )
        if not isinstance(data, list):
            return []
        return [_repo_to_bookmark(item) for item in data]

    def list_issues(self, owner_repo: str, limit: int = 20) -> list[Article]:
        """List issues for a specific repository.

        Args:
            owner_repo: Repository in ``owner/name`` format.
            limit: Maximum number of issues to return.

        Returns:
            List of Article artifacts.
        """
        data = _gh_json(
            [
                "issue",
                "list",
                "--repo",
                owner_repo,
                "--limit",
                str(limit),
                "--json",
                "number,title,body,url,author,createdAt,updatedAt,state",
            ]
        )
        if not isinstance(data, list):
            return []
        return [_issue_to_article(item, owner_repo) for item in data]

    def list_prs(self, owner_repo: str, limit: int = 20) -> list[Article]:
        """List pull requests for a specific repository.

        Args:
            owner_repo: Repository in ``owner/name`` format.
            limit: Maximum number of PRs to return.

        Returns:
            List of Article artifacts.
        """
        data = _gh_json(
            [
                "pr",
                "list",
                "--repo",
                owner_repo,
                "--limit",
                str(limit),
                "--json",
                "number,title,body,url,author,createdAt,updatedAt,state",
            ]
        )
        if not isinstance(data, list):
            return []
        return [_pr_to_article(item, owner_repo) for item in data]
