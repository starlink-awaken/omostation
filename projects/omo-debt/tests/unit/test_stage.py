"""Unit tests for stage identification module."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from git import Repo

from omo_debt.core.stage import (
    get_normalization_factor,
    get_stage_weights,
    identify_project_stage,
)


class TestStageIdentification:
    """Test cases for identify_project_stage function."""

    def create_test_repo_with_commits(self, commit_count: int, months_back: int = 6) -> Path:
        """Helper to create a test Git repository with N commits over M months."""
        tmpdir = Path(tempfile.mkdtemp())
        repo = Repo.init(tmpdir)

        # Create commits spread over the time period
        end_date = datetime.now()
        days_back = months_back * 30

        for i in range(commit_count):
            # Spread commits evenly over the time period
            days_offset = (i * days_back) // commit_count
            commit_date = end_date - timedelta(days=days_offset)

            # Create a file and commit (use relative path to avoid GitPython issue)
            file_path = tmpdir / f"file_{i}.txt"
            file_path.write_text(f"Content {i}")

            repo.index.add([f"file_{i}.txt"])
            # GitPython expects date as string in format "seconds offset"
            timestamp_str = f"{int(commit_date.timestamp())} +0000"
            repo.index.commit(
                f"Commit {i}",
                author_date=timestamp_str,
                commit_date=timestamp_str,
            )

        return tmpdir

    def test_rapid_evolution_stage(self):
        """Test rapid evolution stage identification (>30 commits/month)."""
        # Create repo with 224 commits over 6 months (37.3/month, like gbrain)
        repo_path = self.create_test_repo_with_commits(224, months_back=6)

        stage_info = identify_project_stage(repo_path, months=6)

        assert stage_info.stage == "rapid_evolution"
        assert stage_info.monthly_avg > 30
        assert stage_info.total_commits == 224
        assert stage_info.confidence in ["high", "medium"]

    def test_stable_growth_stage(self):
        """Test stable growth stage identification (10-30 commits/month)."""
        # Create repo with 137 commits over 6 months (22.8/month, like omostation)
        repo_path = self.create_test_repo_with_commits(137, months_back=6)

        stage_info = identify_project_stage(repo_path, months=6)

        assert stage_info.stage == "stable_growth"
        assert 10 <= stage_info.monthly_avg <= 30
        assert stage_info.total_commits == 137

    def test_maintenance_stage(self):
        """Test maintenance stage identification (<10 commits/month)."""
        # Create repo with 3 commits over 6 months (0.5/month, like docs-archive)
        repo_path = self.create_test_repo_with_commits(3, months_back=6)

        stage_info = identify_project_stage(repo_path, months=6)

        assert stage_info.stage == "maintenance"
        assert stage_info.monthly_avg < 10
        assert stage_info.total_commits == 3

    def test_boundary_rapid_to_stable(self):
        """Test boundary case: 30-33 commits/month (medium confidence)."""
        # Create repo with 186 commits over 6 months (31/month)
        repo_path = self.create_test_repo_with_commits(186, months_back=6)

        stage_info = identify_project_stage(repo_path, months=6)

        assert stage_info.stage == "rapid_evolution"
        assert 27 <= stage_info.monthly_avg <= 33
        # Should have medium confidence due to boundary proximity
        assert stage_info.confidence == "medium"

    def test_boundary_stable_to_maintenance(self):
        """Test boundary case: 7-13 commits/month (medium confidence)."""
        # Create repo with 60 commits over 6 months (10/month)
        repo_path = self.create_test_repo_with_commits(60, months_back=6)

        stage_info = identify_project_stage(repo_path, months=6)

        assert stage_info.stage == "stable_growth"
        assert 7 <= stage_info.monthly_avg <= 13
        # Should have medium confidence due to boundary proximity
        assert stage_info.confidence == "medium"

    def test_low_confidence_few_commits(self):
        """Test low confidence when total commits < 10."""
        repo_path = self.create_test_repo_with_commits(5, months_back=6)

        stage_info = identify_project_stage(repo_path, months=6)

        assert stage_info.confidence == "low"
        assert stage_info.total_commits < 10

    def test_invalid_months(self):
        """Test error handling for invalid months parameter."""
        repo_path = self.create_test_repo_with_commits(10)

        with pytest.raises(ValueError, match="months must be >= 1"):
            identify_project_stage(repo_path, months=0)

    def test_nonexistent_path(self):
        """Test error handling for nonexistent path."""
        with pytest.raises(FileNotFoundError):
            identify_project_stage("/nonexistent/path")

    def test_non_git_repo(self):
        """Test error handling for non-Git repository."""
        tmpdir = Path(tempfile.mkdtemp())

        with pytest.raises(Exception):  # InvalidGitRepositoryError
            identify_project_stage(tmpdir)

    def test_stage_info_to_dict(self):
        """Test StageInfo.to_dict() method."""
        repo_path = self.create_test_repo_with_commits(100, months_back=6)
        stage_info = identify_project_stage(repo_path)

        result = stage_info.to_dict()

        assert "monthly_avg" in result
        assert "stage" in result
        assert "confidence" in result
        assert "total_commits" in result
        assert "threshold" in result
        assert "recommendation" in result
        assert "归一化系数" in result["recommendation"]


class TestStageWeights:
    """Test cases for get_stage_weights function."""

    def test_rapid_evolution_weights(self):
        """Test weights for rapid evolution stage."""
        w_impact, w_freq, w_cost = get_stage_weights("rapid_evolution")

        assert w_impact == 0.35
        assert w_freq == 0.40  # Highest frequency weight
        assert w_cost == 0.25
        assert w_impact + w_freq + w_cost == 1.0

    def test_stable_growth_weights(self):
        """Test weights for stable growth stage."""
        w_impact, w_freq, w_cost = get_stage_weights("stable_growth")

        assert w_impact == 0.40
        assert w_freq == 0.30
        assert w_cost == 0.30
        assert w_impact + w_freq + w_cost == 1.0

    def test_maintenance_weights(self):
        """Test weights for maintenance stage."""
        w_impact, w_freq, w_cost = get_stage_weights("maintenance")

        assert w_impact == 0.50  # Highest impact weight
        assert w_freq == 0.20  # Lowest frequency weight
        assert w_cost == 0.30
        assert w_impact + w_freq + w_cost == 1.0


class TestNormalizationFactors:
    """Test cases for get_normalization_factor function."""

    def test_rapid_evolution_factor(self):
        """Test normalization factor for rapid evolution."""
        factor = get_normalization_factor("rapid_evolution")
        assert factor == 1.0

    def test_stable_growth_factor(self):
        """Test normalization factor for stable growth."""
        factor = get_normalization_factor("stable_growth")
        assert factor == 1.1

    def test_maintenance_factor(self):
        """Test normalization factor for maintenance."""
        factor = get_normalization_factor("maintenance")
        assert factor == 1.2

    def test_factor_progression(self):
        """Test that normalization factors increase with project maturity."""
        rapid = get_normalization_factor("rapid_evolution")
        stable = get_normalization_factor("stable_growth")
        maint = get_normalization_factor("maintenance")

        assert rapid < stable < maint
        # Verify 10% increments
        assert abs(stable - rapid - 0.1) < 0.001
        assert abs(maint - stable - 0.1) < 0.001
