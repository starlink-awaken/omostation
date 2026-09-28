"""Purity contract for the existing gac-gate merge-admission workflow."""

import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "gac-gate.yml"

#: 承载 required check 的 job（branch protection 的 context 就是这个名字）。
REQUIRED_JOB = "gac-gate"
#: E2 第二批 (2026-09-28) 起，纯 advisory 步骤搬到这个并行 job —— 见文件末尾注释。
ADVISORY_JOB = "gac-gate-aux"

#: 会被执行的治理命令（相对仓根的 `bin/...`）。真门禁步骤都长这样；
#: checkout/setup-python/setup-uv/pip install 不含它，故不被当作门禁步骤。
GATE_COMMAND = re.compile(r"\bbin/\S+")


def _jobs() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]


def _steps(job: str = REQUIRED_JOB) -> list[dict]:
    return _jobs()[job]["steps"]


def _step(name: str, job: str = REQUIRED_JOB) -> dict:
    matches = [item for item in _steps(job) if item.get("name") == name]
    assert len(matches) == 1, (job, name, matches)
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

    # --require-main 已在 #4209 (2026-09-22) 移除: 跨仓 PR 模式下子模块指针指向
    # 尚未合并的子仓分支是合法状态, require-main 会误杀。用例同步到现状。
    assert reachability["run"] == (
        "python3 bin/ssot/submodule-reachability-gate.py "
        "--source head --fetch"
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
    freshness = _step("CR-X2-EVIDENCE-FRESHNESS — 证据新鲜度检查 (advisory)", job=ADVISORY_JOB)
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


def test_no_blocking_step_lives_outside_the_required_gate_job() -> None:
    """可搬走的是 advisory，绝不是门禁步骤。

    E2 第二批 (2026-09-28) 把 28 个 advisory 步搬到并行的 `gac-gate-aux`。这一步之所以安全，
    **仅仅**因为它们全是 `continue-on-error: true`。若有人把任一门禁步骤（会执行 `bin/...` 的
    阻塞步骤）放进别的 job，`gac-gate` 就会在那些检查沉默的情况下变绿 —— required check 形同
    虚设。这条测试是那次搬迁的安全边界，也是它的负控制。
    """
    offenders = {
        job: [
            step.get("name") or step.get("uses")
            for step in (spec.get("steps") or [])
            if GATE_COMMAND.search(str(step.get("run", ""))) and not step.get("continue-on-error", False)
        ]
        for job, spec in _jobs().items()
        if job != REQUIRED_JOB
    }

    assert not {job: names for job, names in offenders.items() if names}


def test_advisory_job_still_runs_every_moved_step() -> None:
    """搬迁不能顺手丢步骤：原 28 个 advisory 步应逐个出现在 aux job 里。"""
    steps = _steps(ADVISORY_JOB)
    setup, moved = steps[:4], steps[4:]

    assert [s.get("uses") or s.get("name") for s in setup][0] == "actions/checkout@v4"
    assert len(moved) == 28, [step.get("name") for step in moved][:5]
    assert all(step.get("continue-on-error", False) is True for step in moved)
    named = {step.get("name") for step in moved}
    assert "CR-X2-EVIDENCE-FRESHNESS — 证据新鲜度检查 (advisory)" in named
    assert "mof-check (L0 约束对齐验证, advisory)" in named
    # 搬迁后不得在 required job 里留副本（否则白占临界路径）
    assert not [step for step in _steps() if step.get("continue-on-error", False)]
