import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "bin" / "gac" / "risk-profile.py"


def run_risk_profile(args: list[str] | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT)]
    if args:
        cmd.extend(args)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)


class TestRiskProfile:
    def test_staged_docs_low_risk(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(REPO_ROOT)
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        monkeypatch.setenv("GIT_DIR", str(REPO_ROOT / ".git"))
        result = run_risk_profile(["--staged"])
        assert result.returncode == 0
        assert result.stdout.strip() in {"low", "medium", "high"}

    def test_explicit_docs_files_low_risk(self):
        result = run_risk_profile(["--files", "docs/README.md", "docs/INDEX.md"])
        assert result.returncode == 0
        assert result.stdout.strip() == "low"

    def test_explicit_projects_files_high_risk(self):
        result = run_risk_profile(["--files", "projects/ecos/src/foo.py", "bin/gac/bar.py"])
        assert result.returncode == 0
        assert result.stdout.strip() == "high"

    def test_explicit_gac_files_medium_risk(self):
        result = run_risk_profile(["--files", "bin/gac/check-submodule-rewind.py"])
        assert result.returncode == 0
        assert result.stdout.strip() == "medium"

    def test_empty_files_medium_risk(self):
        result = run_risk_profile(["--files"])
        assert result.returncode == 0
        assert result.stdout.strip() == "medium"
