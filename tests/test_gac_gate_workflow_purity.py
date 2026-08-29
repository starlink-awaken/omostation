"""Purity contract for the existing gac-gate merge-admission workflow."""

from pathlib import Path
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "gac-gate.yml"


def _steps() -> list[dict]:
    payload = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return payload["jobs"]["gac-gate"]["steps"]


def _step(name: str) -> dict:
    matches = [item for item in _steps() if item.get("name") == name]
    assert len(matches) == 1, (name, matches)
    return matches[0]


def test_main_push_concurrency_is_scoped_to_immutable_sha() -> None:
    payload = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    concurrency = payload["concurrency"]

    assert concurrency["group"] == (
        "${{ github.workflow }}-"
        "${{ github.event_name == 'push' && github.sha || github.ref }}"
    )
    assert concurrency["cancel-in-progress"] is True


def test_strict_gate_step_is_blocking() -> None:
    strict = _step("gac-local-gate (strict)")

    assert strict.get("continue-on-error", False) is False
    assert strict["run"] == "python3 bin/gac/gac-local-gate.py --strict"


def test_blocking_path_never_mutates_checkout() -> None:
    steps = _steps()
    names = [item.get("name") for item in steps]
    start = names.index("immutable checkout precondition")
    end = names.index("immutable checkout postcondition")
    assert start < end

    forbidden = (
        "sync-submodule-pointers.sh",
        "git add",
        "project-layer-index.py --write",
        "gac-export-agents.py",
        "GAC_M1_SYNC_WRITE",
    )
    violations = {
        str(item.get("name")): [token for token in forbidden if token in str(item.get("run", ""))]
        for item in steps[start : end + 1]
    }
    assert not {name: tokens for name, tokens in violations.items() if tokens}


def test_reachability_and_generators_are_check_only() -> None:
    reachability = _step("PASW — 子模块指针可达性前置检查")
    projections = _step("generated projection drift checks")

    assert reachability["run"] == (
        "python3 bin/ssot/submodule-reachability-gate.py "
        "--source head --fetch --require-main"
    )
    assert reachability.get("continue-on-error", False) is False
    assert "project-layer-index.py --check" in projections["run"]
    assert "gac-drift.py" in projections["run"]


def test_clean_tree_is_checked_before_and_after_blocking_path() -> None:
    pre = _step("immutable checkout precondition")["run"]
    post = _step("immutable checkout postcondition")["run"]

    for command in (
        "git diff --exit-code",
        "git diff --cached --exit-code",
        'test -z "$(git status --porcelain)"',
    ):
        assert command in pre
        assert command in post
    assert _step("immutable checkout postcondition").get("if") == "always()"


def test_evidence_freshness_never_generates_missing_reports() -> None:
    freshness = _step(
        "CR-X2-EVIDENCE-FRESHNESS — 证据新鲜度检查 (advisory)"
    )
    run = freshness["run"]

    assert freshness.get("continue-on-error") is True
    assert "compgen -G '.omo/_delivery/evidence-smoke/*.json'" in run
    assert "check-evidence-freshness.py --json" in run
    assert "SKIP evidence freshness" in run


def test_immutable_guard_rejects_tracked_staged_and_untracked_changes(
    tmp_path: Path,
) -> None:
    guard = _step("immutable checkout precondition")["run"]

    for mutation in ("clean", "tracked", "staged", "untracked"):
        repo = tmp_path / mutation
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "gate@example.invalid"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.name", "Gate Test"],
            check=True,
        )
        tracked = repo / "tracked.txt"
        tracked.write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "base"], check=True)
        if mutation == "tracked":
            tracked.write_text("changed\n", encoding="utf-8")
        elif mutation == "staged":
            tracked.write_text("changed\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
        elif mutation == "untracked":
            (repo / "new.txt").write_text("new\n", encoding="utf-8")

        result = subprocess.run(
            ["bash", "-eu", "-c", guard],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        assert (result.returncode == 0) is (mutation == "clean"), mutation
