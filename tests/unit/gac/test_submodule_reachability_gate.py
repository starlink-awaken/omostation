from __future__ import annotations

import importlib.util
import subprocess
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin" / "ssot" / "submodule-reachability-gate.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("submodule_reachability_gate", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_worktree_source_falls_back_to_index_for_uninitialized_submodule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    module.WORKSPACE = tmp_path
    (tmp_path / "projects" / "runtime").mkdir(parents=True)
    expected = "1206c68abb7a1904808750cee42aa6136fb686cf"

    def fake_run(cmd: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        assert cmd[:3] == ["git", "ls-files", "-s"]
        return subprocess.CompletedProcess(cmd, 0, f"160000 {expected} 0\tprojects/runtime\n", "")

    monkeypatch.setattr(module, "run", fake_run)

    assert module.gitlink_sha("projects/runtime", "worktree") == expected


@pytest.mark.parametrize(
    ("source", "current_sha", "expected"),
    [
        ("head", "a" * 40, set()),
        ("index", "b" * 40, {"projects/runtime"}),
        ("worktree", "c" * 40, {"projects/runtime"}),
    ],
)
def test_changed_submodules_compares_the_selected_source(
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    current_sha: str,
    expected: set[str],
) -> None:
    module = _load_module()
    base_sha = "a" * 40
    monkeypatch.setattr(module, "submodule_paths", lambda: ["projects/runtime"])
    monkeypatch.setattr(
        module,
        "gitlink_sha",
        lambda path, selected_source: (
            current_sha
            if (path, selected_source) == ("projects/runtime", source)
            else pytest.fail("unexpected gitlink lookup")
        ),
    )

    def fake_run(cmd: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        if cmd[:4] == ["git", "rev-parse", "--verify", "--quiet"]:
            return subprocess.CompletedProcess(cmd, 0, base_sha + "\n", "")
        if cmd == ["git", "ls-tree", "origin/main", "--", "projects/runtime"]:
            return subprocess.CompletedProcess(
                cmd,
                0,
                f"160000 commit {base_sha}\tprojects/runtime\n",
                "",
            )
        pytest.fail(f"unexpected command: {cmd}")

    monkeypatch.setattr(module, "run", fake_run)

    assert module.changed_submodules("origin/main", source) == expected


def test_remote_contains_accepts_uninitialized_submodule_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    module.WORKSPACE = tmp_path
    (tmp_path / "projects" / "runtime").mkdir(parents=True)
    monkeypatch.setattr(
        module,
        "run",
        lambda *_args, **_kwargs: pytest.fail("must not run git inside an uninitialized submodule"),
    )

    ok, detail = module.remote_contains("projects/runtime", "deadbeef", fetch=False)

    assert ok is True
    assert "not initialized" in detail


def test_remote_contains_rejects_feature_only_commit_when_main_is_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    module.WORKSPACE = tmp_path
    submodule = tmp_path / "projects" / "runtime"
    (submodule / ".git").mkdir(parents=True)
    sha = "a" * 40

    def fake_run(cmd: list[str], *, cwd: Path = tmp_path, check: bool = False) -> subprocess.CompletedProcess[str]:
        del check
        if cmd == ["git", "rev-parse", "--is-inside-work-tree"]:
            return subprocess.CompletedProcess(cmd, 0, "true\n", "")
        if cmd == ["git", "branch", "-r", "--contains", sha]:
            return subprocess.CompletedProcess(cmd, 0, "  origin/agent/personal-feature\n", "")
        if cmd == [
            "git",
            "merge-base",
            "--is-ancestor",
            sha,
            "refs/remotes/origin/main",
        ]:
            return subprocess.CompletedProcess(cmd, 1, "", "")
        pytest.fail(f"unexpected command in {cwd}: {cmd}")

    monkeypatch.setattr(module, "run", fake_run)

    ok, detail = module.remote_contains("projects/runtime", sha, fetch=False, require_main=True)

    assert ok is False
    assert detail == "not contained in refs/remotes/origin/main"


def test_remote_contains_accepts_main_ancestor_when_main_is_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    module.WORKSPACE = tmp_path
    submodule = tmp_path / "projects" / "runtime"
    (submodule / ".git").mkdir(parents=True)
    sha = "b" * 40

    def fake_run(cmd: list[str], *, cwd: Path = tmp_path, check: bool = False) -> subprocess.CompletedProcess[str]:
        del check
        if cmd == ["git", "rev-parse", "--is-inside-work-tree"]:
            return subprocess.CompletedProcess(cmd, 0, "true\n", "")
        if cmd == [
            "git",
            "merge-base",
            "--is-ancestor",
            sha,
            "refs/remotes/origin/main",
        ]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        pytest.fail(f"unexpected command in {cwd}: {cmd}")

    monkeypatch.setattr(module, "run", fake_run)

    ok, detail = module.remote_contains("projects/runtime", sha, fetch=False, require_main=True)

    assert ok is True
    assert detail == "refs/remotes/origin/main"


def test_remote_contains_reports_main_ancestry_query_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()
    module.WORKSPACE = tmp_path
    submodule = tmp_path / "projects" / "runtime"
    (submodule / ".git").mkdir(parents=True)
    sha = "c" * 40

    def fake_run(cmd: list[str], *, cwd: Path = tmp_path, check: bool = False) -> subprocess.CompletedProcess[str]:
        del check
        if cmd == ["git", "rev-parse", "--is-inside-work-tree"]:
            return subprocess.CompletedProcess(cmd, 0, "true\n", "")
        if cmd == [
            "git",
            "merge-base",
            "--is-ancestor",
            sha,
            "refs/remotes/origin/main",
        ]:
            return subprocess.CompletedProcess(cmd, 128, "", "fatal: bad revision")
        pytest.fail(f"unexpected command in {cwd}: {cmd}")

    monkeypatch.setattr(module, "run", fake_run)

    ok, detail = module.remote_contains("projects/runtime", sha, fetch=False, require_main=True)

    assert ok is False
    assert detail == "main ancestry query failed: fatal: bad revision"


def test_run_returns_timeout_rc_instead_of_hanging(tmp_path: Path) -> None:
    """A wedged subprocess must come back bounded — this is the 40-min push stall fix."""
    module = _load_module()

    result = module.run(["sleep", "30"], cwd=tmp_path, timeout=0.2)

    assert result.returncode == module.TIMEOUT_RC
    assert "timed out" in result.stderr


@pytest.mark.parametrize("require_main", [False, True])
def test_fetch_is_called_with_a_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, require_main: bool
) -> None:
    """The bound has to reach the subprocess, not just exist as a constant."""
    module = _load_module()
    module.WORKSPACE = tmp_path
    submodule = tmp_path / "projects" / "runtime"
    (submodule / ".git").mkdir(parents=True)
    captured: dict[str, object] = {}

    def fake_run(
        cmd: list[str], *, cwd: Path = tmp_path, check: bool = False, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        del cwd, check
        if cmd[:2] == ["git", "fetch"]:
            captured.update(kwargs)
            return subprocess.CompletedProcess(cmd, module.TIMEOUT_RC, "", "timed out after 120.0s")
        if cmd == ["git", "rev-parse", "--is-inside-work-tree"]:
            return subprocess.CompletedProcess(cmd, 0, "true\n", "")
        if cmd == ["git", "rev-parse", "--is-shallow-repository"]:
            return subprocess.CompletedProcess(cmd, 0, "false\n", "")
        pytest.fail(f"unexpected command: {cmd}")

    monkeypatch.setattr(module, "run", fake_run)

    module.remote_contains("projects/runtime", "d" * 40, fetch=True, require_main=require_main)

    assert isinstance(captured.get("timeout"), float)
    assert captured["timeout"] > 0


def test_fetch_timeout_is_unverified_not_unreachable_locally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An inconclusive network is not a verdict: the local push must not be blocked by it."""
    module = _load_module()
    module.WORKSPACE = tmp_path
    submodule = tmp_path / "projects" / "runtime"
    (submodule / ".git").mkdir(parents=True)

    def fake_run(
        cmd: list[str], *, cwd: Path = tmp_path, check: bool = False, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        del cwd, check
        if cmd[:2] == ["git", "fetch"]:
            return subprocess.CompletedProcess(cmd, module.TIMEOUT_RC, "", "timed out after 120.0s")
        if cmd == ["git", "rev-parse", "--is-inside-work-tree"]:
            return subprocess.CompletedProcess(cmd, 0, "true\n", "")
        if cmd == ["git", "rev-parse", "--is-shallow-repository"]:
            return subprocess.CompletedProcess(cmd, 0, "false\n", "")
        pytest.fail(f"unexpected command: {cmd}")

    monkeypatch.setattr(module, "run", fake_run)

    ok, detail = module.remote_contains("projects/runtime", "d" * 40, fetch=True)

    assert ok is True
    assert detail.startswith(module.UNVERIFIED_PREFIX)
    assert "timed out" in detail


def test_fetch_timeout_still_blocks_when_main_ancestry_is_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CI runs with require_main and has no lower layer to fall back on — stay strict."""
    module = _load_module()
    module.WORKSPACE = tmp_path
    submodule = tmp_path / "projects" / "runtime"
    (submodule / ".git").mkdir(parents=True)

    def fake_run(
        cmd: list[str], *, cwd: Path = tmp_path, check: bool = False, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        del cwd, check
        if cmd[:2] == ["git", "fetch"]:
            return subprocess.CompletedProcess(cmd, module.TIMEOUT_RC, "", "timed out after 120.0s")
        if cmd == ["git", "rev-parse", "--is-inside-work-tree"]:
            return subprocess.CompletedProcess(cmd, 0, "true\n", "")
        if cmd == ["git", "rev-parse", "--is-shallow-repository"]:
            return subprocess.CompletedProcess(cmd, 0, "false\n", "")
        pytest.fail(f"unexpected command: {cmd}")

    monkeypatch.setattr(module, "run", fake_run)

    ok, detail = module.remote_contains("projects/runtime", "d" * 40, fetch=True, require_main=True)

    assert ok is False
    assert "cannot verify origin/main ancestry" in detail


def test_check_reports_unverified_count_so_degradation_is_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    module.WORKSPACE = tmp_path
    monkeypatch.setattr(module, "submodule_paths", lambda: ["projects/runtime"])
    monkeypatch.setattr(module, "gitlink_sha", lambda *_args: "e" * 40)
    monkeypatch.setattr(
        module,
        "remote_contains",
        lambda *_args, **_kwargs: (True, f"{module.UNVERIFIED_PREFIX}fetch timed out"),
    )

    report = module.check("head", fetch=True)

    assert report["ok"] is True
    assert report["unverified"] == 1


def test_exhausted_network_budget_stops_touching_the_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Past the budget, degrade by declaration — measured 8 pointless git spawns."""
    module = _load_module()
    module.WORKSPACE = tmp_path
    submodule = tmp_path / "projects" / "runtime"
    (submodule / ".git").mkdir(parents=True)
    module._NETWORK_DEADLINE = time.monotonic() - 1

    def fake_run(
        cmd: list[str], *, cwd: Path = tmp_path, check: bool = False, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        del cwd, check
        if cmd == ["git", "rev-parse", "--is-inside-work-tree"]:
            return subprocess.CompletedProcess(cmd, 0, "true\n", "")
        pytest.fail(f"must not spawn git once the network budget is gone: {cmd}")

    monkeypatch.setattr(module, "run", fake_run)

    ok, detail = module.remote_contains("projects/runtime", "f" * 40, fetch=True)

    assert ok is True
    assert detail.startswith(module.UNVERIFIED_PREFIX)
    assert "network budget exhausted" in detail


# ── 子模块并发 (E2-A): 并发只改墙钟, 不改结论 ──────────────────────────────


def _fake_submodules(module: object, monkeypatch: pytest.MonkeyPatch, count: int = 8) -> list[str]:
    """把模块伪装成有 `count` 个已登记子模块 (不碰真实 repo/网络)。"""
    paths = [f"projects/sub{i:02d}" for i in range(count)]
    monkeypatch.setattr(module, "submodule_paths", lambda: list(paths))
    monkeypatch.setattr(module, "gitlink_sha", lambda _path, _source: "0" * 39 + "1")
    return paths


def test_pasw_jobs_env_override_and_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()

    monkeypatch.setenv("PASW_JOBS", "1")
    assert module._pasw_jobs(16) == 1  # 一键回退串行

    monkeypatch.setenv("PASW_JOBS", "6")
    assert module._pasw_jobs(16) == 6

    monkeypatch.setenv("PASW_JOBS", "99")
    assert module._pasw_jobs(3) == 3  # 不超过待检子模块数, 不空转线程

    monkeypatch.setenv("PASW_JOBS", "bogus")
    assert 1 <= module._pasw_jobs(16) <= module.DEFAULT_PASW_JOBS

    monkeypatch.delenv("PASW_JOBS", raising=False)
    assert 1 <= module._pasw_jobs(16) <= module.DEFAULT_PASW_JOBS

    assert module._pasw_jobs(0) == 1


def test_parallel_check_is_identical_to_serial(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """并发版必须与串行版**完全相等**(顺序/内容/计数), 否则 report 会漂移。"""
    module = _load_module()
    module.WORKSPACE = tmp_path
    paths = _fake_submodules(module, monkeypatch)

    def fake_remote_contains(path: str, _sha: str, *, fetch: bool, require_main: bool = False) -> tuple[bool, str]:
        del fetch, require_main
        index = int(path[-2:])
        if index % 4 == 3:
            return False, "not contained in fetched origin branches"
        if index % 4 == 2:
            return True, f"{module.UNVERIFIED_PREFIX}fetch timed out"
        return True, "origin/main"

    monkeypatch.setattr(module, "remote_contains", fake_remote_contains)

    monkeypatch.setenv("PASW_JOBS", "1")
    serial = module.check("head", fetch=True)
    monkeypatch.setenv("PASW_JOBS", "4")
    parallel = module.check("head", fetch=True)

    assert parallel == serial
    # 正控制: 样本确实覆盖了三种结论, 否则「相等」是空洞的真
    assert [item["path"] for item in parallel["findings"]] == paths
    assert parallel["checked"] == len(paths)
    assert len(parallel["failures"]) == 2
    assert parallel["unverified"] == 2


def test_parallel_order_survives_out_of_order_completion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """index 归位: 先提交的可能后完成, findings 仍按原序 —— 这是不破契约的关键。"""
    module = _load_module()
    module.WORKSPACE = tmp_path
    paths = _fake_submodules(module, monkeypatch)
    completed: list[str] = []

    def fake_remote_contains(path: str, _sha: str, *, fetch: bool, require_main: bool = False) -> tuple[bool, str]:
        del fetch, require_main
        if path == paths[0]:
            time.sleep(0.25)  # 第一个最后完成
        completed.append(path)
        return True, "origin/main"

    monkeypatch.setattr(module, "remote_contains", fake_remote_contains)
    monkeypatch.setenv("PASW_JOBS", str(len(paths)))

    report = module.check("head", fetch=True)

    # 正控制: 完成顺序确实乱序(否则下面的顺序断言无意义)
    assert completed[-1] == paths[0]
    assert [item["path"] for item in report["findings"]] == paths


def test_parallel_path_uses_worker_threads_and_jobs_one_degrades_to_serial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    module.WORKSPACE = tmp_path
    _fake_submodules(module, monkeypatch)
    main_thread = threading.main_thread().name
    seen: list[str] = []

    def fake_remote_contains(_path: str, _sha: str, *, fetch: bool, require_main: bool = False) -> tuple[bool, str]:
        del fetch, require_main
        seen.append(threading.current_thread().name)
        return True, "origin/main"

    monkeypatch.setattr(module, "remote_contains", fake_remote_contains)

    monkeypatch.setenv("PASW_JOBS", "4")
    module.check("head", fetch=True)
    assert seen and all(name != main_thread for name in seen)  # 并发路径真的进池

    seen.clear()
    monkeypatch.setenv("PASW_JOBS", "1")
    module.check("head", fetch=True)
    assert set(seen) == {main_thread}  # 回归串行: 全在主线程


def test_skip_and_incremental_filters_survive_the_parallel_refactor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """过滤逻辑被重排过, 必须仍然: skip 计数 / only_paths 子集 / 空集早退。"""
    module = _load_module()
    module.WORKSPACE = tmp_path
    paths = _fake_submodules(module, monkeypatch)
    monkeypatch.setattr(module, "remote_contains", lambda *_a, **_k: (True, "origin/main"))

    skipped = module.check("head", fetch=False, skip_paths={paths[7]})
    assert skipped["skipped"] == 1
    assert [item["path"] for item in skipped["findings"]] == paths[:7]

    subset = {"projects/sub02", "projects/sub05"}
    incremental = module.check("head", fetch=False, only_paths=subset)
    assert incremental["checked"] == 2
    assert [item["path"] for item in incremental["findings"]] == ["projects/sub02", "projects/sub05"]

    empty = module.check("head", fetch=False, only_paths=set())
    assert empty["mode"] == "incremental-empty"
    assert empty["findings"] == []
