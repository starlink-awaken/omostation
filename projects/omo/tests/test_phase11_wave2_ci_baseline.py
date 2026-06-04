from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_kairon_makefile_uses_python3_and_propagates_test_failures() -> None:
    makefile = (REPO_ROOT / "projects" / "kairon" / "Makefile").read_text(encoding="utf-8")

    assert "python3 -m pytest" in makefile
    assert "python -m pytest" not in makefile
    assert "fail=1" in makefile
    assert "test $$fail -eq 0" in makefile


def test_phase11_ci_workflow_bootstraps_uv_and_runs_kairon_test_target() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "phase11-ci.yml").read_text(encoding="utf-8")

    assert "name: Phase 11 CI" in workflow
    assert "astral-sh/setup-uv@v3" in workflow
    assert "uv sync --all-packages" in workflow
    assert "make kairon-test" in workflow
