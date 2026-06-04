"""
Completeness sub-dimension for honesty scoring.

Measures coverage of technical debt disclosure across:
1. Code coverage: debt items vs problematic files
2. Key area coverage: critical zones (core/security/performance)
3. Historical issue coverage: disclosed vs hidden issues
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from git import InvalidGitRepositoryError, Repo
except ImportError:
    Repo = None
    InvalidGitRepositoryError = Exception


@dataclass
class CompletenessResult:
    """Completeness assessment result."""

    score: float  # Overall completeness score (0-10)
    code_coverage: float  # Code coverage sub-score (0-10)
    key_area_coverage: float  # Key area coverage sub-score (0-10)
    history_coverage: float  # Historical issue coverage sub-score (0-10)

    # Metadata
    debt_files_count: int
    problematic_files_count: int
    key_areas_covered: list[str]
    disclosed_issues: int
    hidden_issues: int


def calculate_completeness(
    project_path: str = ".",
    debt_files: Optional[list[str]] = None,
    disclosed_issues: Optional[list[str]] = None,
) -> CompletenessResult:
    """Calculate completeness score for technical debt disclosure.

    Formula:
        completeness = 0.40 × code_coverage + 0.30 × key_area + 0.30 × history

    Args:
        project_path: Path to project root
        debt_files: List of files referenced in debt items (optional)
        disclosed_issues: List of disclosed issue IDs (optional)

    Returns:
        CompletenessResult object

    Examples:
        >>> result = calculate_completeness(".", debt_files=["src/main.py"])
        >>> result.score  # 0-10 score
        7.5
    """
    # Default to empty lists if None
    debt_files = debt_files or []
    disclosed_issues = disclosed_issues or []

    # 1. Calculate code coverage
    problematic_files = _identify_problematic_files(project_path)
    debt_file_count = len(set(debt_files))
    problematic_count = len(problematic_files)

    if problematic_count > 0:
        code_cov = round((debt_file_count / problematic_count) * 10, 2)
    else:
        code_cov = 10.0  # No problematic files = perfect coverage

    # Cap at 10.0 (debt files may exceed problematic files)
    code_cov = min(10.0, code_cov)

    # 2. Calculate key area coverage
    key_areas = _identify_covered_key_areas(project_path, debt_files)
    key_area_count = len(key_areas)

    if key_area_count >= 3:
        key_area_score = 10.0
    elif key_area_count == 2:
        key_area_score = 6.0
    elif key_area_count == 1:
        key_area_score = 3.0
    else:
        key_area_score = 0.0

    # 3. Calculate historical issue coverage
    hidden_count = _count_hidden_issues(project_path, disclosed_issues)
    disclosed_count = len(disclosed_issues)
    total_issues = disclosed_count + hidden_count

    if total_issues > 0:
        history_cov = round((disclosed_count / total_issues) * 10, 2)
    else:
        history_cov = 10.0  # No historical issues = perfect coverage

    # 4. Calculate weighted completeness score
    completeness_score = round(0.40 * code_cov + 0.30 * key_area_score + 0.30 * history_cov, 2)

    return CompletenessResult(
        score=completeness_score,
        code_coverage=code_cov,
        key_area_coverage=key_area_score,
        history_coverage=history_cov,
        debt_files_count=debt_file_count,
        problematic_files_count=problematic_count,
        key_areas_covered=key_areas,
        disclosed_issues=disclosed_count,
        hidden_issues=hidden_count,
    )


def _identify_problematic_files(project_path: str) -> set[str]:
    """Identify problematic files using heuristics.

    Heuristics:
    1. High churn rate: frequently modified files (top 20%)
    2. Large files: > 500 lines (complexity proxy)
    3. TODO/FIXME markers: technical debt indicators

    Args:
        project_path: Project root path

    Returns:
        Set of relative file paths
    """
    problematic = set()
    project_root = Path(project_path).resolve()

    # Heuristic 1: High churn files via Git
    try:
        if Repo:
            repo = Repo(project_path)
            churn_files = _get_high_churn_files(repo, threshold_percentile=80)
            problematic.update(churn_files)
    except (InvalidGitRepositoryError, Exception):
        pass  # Git not available or not a repo

    # Heuristic 2: Large files + Heuristic 3: TODO/FIXME markers
    for root, _, files in os.walk(project_path):
        root_path = Path(root)

        # Skip hidden directories and common ignore patterns
        if any(part.startswith(".") for part in root_path.parts):
            continue
        if any(part in ["node_modules", "__pycache__", "venv", "dist", "build"] for part in root_path.parts):
            continue

        for file in files:
            # Only check source code files
            if not _is_source_file(file):
                continue

            file_path = root_path / file
            try:
                relative_path = file_path.relative_to(project_root)

                # Check file size
                lines = file_path.read_text(errors="ignore").splitlines()
                line_count = len(lines)

                # Large file heuristic
                if line_count > 500:
                    problematic.add(str(relative_path))
                    continue

                # TODO/FIXME marker heuristic
                content = "\n".join(lines)
                if "TODO" in content or "FIXME" in content or "XXX" in content:
                    problematic.add(str(relative_path))

            except Exception:
                continue  # Skip files with read errors

    return problematic


def _get_high_churn_files(repo: "Repo", threshold_percentile: int = 80) -> set[str]:
    """Get files with high churn rate (top X percentile).

    Args:
        repo: GitPython Repo object
        threshold_percentile: Percentile threshold (default 80 = top 20%)

    Returns:
        Set of high-churn file paths
    """
    from collections import defaultdict

    churn_count = defaultdict(int)

    # Count commits per file (last 6 months)
    try:
        commits = list(repo.iter_commits("HEAD", max_count=200))

        for commit in commits:
            # Skip merge commits
            if len(commit.parents) > 1:
                continue

            # Count changed files
            try:
                for item in commit.stats.files.keys():
                    churn_count[item] += 1
            except Exception:
                continue

    except Exception:
        return set()  # Git analysis failed

    if not churn_count:
        return set()

    # Calculate threshold
    churn_values = sorted(churn_count.values())
    percentile_index = int(len(churn_values) * threshold_percentile / 100)
    threshold = churn_values[percentile_index] if percentile_index < len(churn_values) else 0

    # Return files above threshold
    return {file for file, count in churn_count.items() if count >= threshold}


def _identify_covered_key_areas(project_path: str, debt_files: list[str]) -> list[str]:
    """Identify which key areas are covered by debt items.

    Key areas:
    1. Core business logic: src/core/, lib/core/, business/, domain/
    2. Security: auth/, security/, crypto/, session/
    3. Performance: cache/, optimize/, perf/, index/

    Args:
        project_path: Project root path
        debt_files: List of debt item file paths

    Returns:
        List of covered area names (["core", "security", "performance"])
    """
    covered = []

    # Normalize debt file paths
    debt_set = {Path(f).as_posix().lower() for f in debt_files}

    # Check core business logic
    core_patterns = ["src/core/", "lib/core/", "/business/", "/domain/", "/model/"]
    if any(any(pattern in path for pattern in core_patterns) for path in debt_set):
        covered.append("core")

    # Check security
    security_patterns = ["/auth/", "/security/", "/crypto/", "/session/", "/permission/"]
    if any(any(pattern in path for pattern in security_patterns) for path in debt_set):
        covered.append("security")

    # Check performance
    perf_patterns = ["/cache/", "/optimize/", "/perf/", "/index/", "/query/"]
    if any(any(pattern in path for pattern in perf_patterns) for path in debt_set):
        covered.append("performance")

    return covered


def _count_hidden_issues(project_path: str, disclosed_issues: list[str]) -> int:
    """Count hidden issues (closed issues not disclosed as debt).

    Note: This is a simplified implementation. Real implementation would:
    - Query GitHub/GitLab API for closed issues
    - Cross-reference with disclosed issue list
    - Count the gap

    For now, returns a placeholder estimate.

    Args:
        project_path: Project root path
        disclosed_issues: List of disclosed issue IDs

    Returns:
        Estimated hidden issue count
    """
    # Placeholder: estimate 20% of disclosed issues are hidden
    # Real implementation would query issue tracker API
    disclosed_count = len(disclosed_issues)
    estimated_hidden = max(0, int(disclosed_count * 0.2))

    return estimated_hidden


def _is_source_file(filename: str) -> bool:
    """Check if file is a source code file.

    Args:
        filename: File name

    Returns:
        True if source file
    """
    source_exts = {
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".java",
        ".cpp",
        ".c",
        ".h",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".swift",
        ".kt",
        ".scala",
        ".cs",
    }
    return any(filename.endswith(ext) for ext in source_exts)
