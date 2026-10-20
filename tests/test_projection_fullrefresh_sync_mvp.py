"""Real temporary Git pins; external collect/identity and slow shell are seams."""
import importlib.util
import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / "bin/panorama/projection-full-refresh.py"
    spec = importlib.util.spec_from_file_location("sync_mvp_driver", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    real_run = subprocess.run
    monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "file")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    def git(root, *args):
        result = real_run(["git", *args], cwd=root, capture_output=True, text=True, check=True)
        return result.stdout.strip()

    child = tmp_path / "child-source"; child.mkdir()
    git(child, "init", "-b", "main")
    git(child, "config", "user.email", "fixture@example.invalid")
    git(child, "config", "user.name", "Fixture")
    (child / "file").write_text("original child")
    git(child, "add", "."); git(child, "commit", "-m", "child base")
    origin = tmp_path / "parent-source"; origin.mkdir()
    git(origin, "init", "-b", "main")
    git(origin, "config", "user.email", "fixture@example.invalid")
    git(origin, "config", "user.name", "Fixture")
    (origin / "file").write_text("original root")
    (origin / ".gitignore").write_text("ignored\n__pycache__/\n")
    # Real pinned repository and committed gitlink, without invoking the slow
    # git-submodule shell wrapper that this delivery is explicitly avoiding.
    git(tmp_path, "clone", str(child), str(origin / "child"))
    (origin / ".gitmodules").write_text(
        f'[submodule "child"]\n\tpath = child\n\turl = {child}\n')
    git(origin, "update-index", "--add", "--cacheinfo",
        "160000," + git(child, "rev-parse", "HEAD") + ",child")
    git(origin, "add", "."); git(origin, "commit", "-m", "root base")
    checkout = tmp_path / "publisher"
    git(tmp_path, "clone", str(origin), str(checkout))
    git(tmp_path, "clone", str(child), str(checkout / "child"))
    module.CHECKOUT = checkout; module.DEPLOY_DIR = tmp_path / "deploy"
    module.LOCK_PATH = tmp_path / "runtime/lock"; module.LOG_PATH = tmp_path / "runtime/log"
    monkeypatch.setattr(module, "ledger_db_path", lambda: tmp_path / "ledger.sqlite3")
    monkeypatch.setattr(module, "task_state_root", lambda: tmp_path / "authority")
    calls = []; transport = {"fetch_fail": False, "wrong_origin": False}

    def external_run(cmd, *args, **kwargs):
        calls.append((list(cmd), kwargs))
        if "get-url" in cmd:
            return subprocess.CompletedProcess(cmd, 0,
                "https://invalid.example/other.git\n" if transport["wrong_origin"] else module.CLONE_URL + "\n", "")
        if cmd[:2] == ["git", "fetch"] and transport["fetch_fail"]:
            return subprocess.CompletedProcess(cmd, 1, "", "real transport failure fixture")
        if cmd[:3] == ["git", "submodule", "sync"]:
            # Keep the emitted fallback sequence observable, but execute the
            # real sandbox's one-child configuration directly, not the shell
            # wrapper whose pathological startup latency is the subject here.
            return real_run(["git", "config", "submodule.child.url", str(child)],
                            cwd=checkout, capture_output=True, text=True)
        if cmd[:3] == ["git", "submodule", "update"]:
            pin = git(checkout, "rev-parse", "HEAD:child")
            return real_run(["git", "checkout", "--detach", pin], cwd=checkout / "child",
                            capture_output=True, text=True)
        if cmd[:3] == ["git", "submodule", "foreach"]:
            # Mirror the real deepen without depending on the sandbox's remote
            # transport: the emitted depth is what these tests assert on. A
            # failure injection point models the flaky TLS observed on the host.
            if transport.get("deepen_fail_times", 0) > 0:
                transport["deepen_fail_times"] -= 1
                return subprocess.CompletedProcess(cmd, 128, "", "SSL_ERROR_SYSCALL")
            return real_run(["git", "-C", str(checkout / "child"), "rev-parse", "HEAD"],
                            capture_output=True, text=True)
        if any(str(x).endswith("panorama-collect.py") for x in cmd):
            return subprocess.CompletedProcess(cmd, 0, "fixture collection complete", "")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", external_run)
    return module, checkout, origin, child, calls, transport, git


def expensive(calls):
    return [cmd for cmd, _ in calls if cmd[:2] in (
        ["git", "reset"], ["git", "clean"], ["git", "submodule"])
        and cmd != ["git", "clean", "-ndx"]]


def test_alignment_preserves_real_root_and_child_indexes(sandbox, monkeypatch):
    mod, checkout, _, _, _, _, git = sandbox
    # Prove the old probe really writes stat-cache updates, regardless of the
    # caller's optional-lock setting. Resolve indexes through Git for .git files.
    monkeypatch.setenv("GIT_OPTIONAL_LOCKS", "1")
    target = git(checkout, "rev-parse", "HEAD")
    roots = (checkout, checkout / "child")
    indexes = [Path(git(root, "rev-parse", "--path-format=absolute", "--git-path", "index"))
               for root in roots]

    def snapshot():
        return [(index.read_bytes(), index.stat().st_mtime_ns) for index in indexes]

    def invalidate_stat_cache():
        for root in roots:
            path = root / "file"
            contents = path.read_bytes()
            before = path.stat()
            os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns - 2_000_000_000))
            assert path.stat().st_mtime_ns != before.st_mtime_ns
            assert path.read_bytes() == contents

    invalidate_stat_cache()
    before = snapshot()
    for root in roots:
        result = mod.run(["git", "status", "--porcelain", "--untracked-files=all",
                          "--ignore-submodules=none"], cwd=root, timeout=5)
        assert result.returncode == 0 and result.stdout == ""
    refreshed = snapshot()
    for previous, current in zip(before, refreshed):
        assert current[0] != previous[0], "negative control did not refresh index bytes"
        assert current[1] != previous[1], "negative control did not write the index"

    invalidate_stat_cache()
    before = snapshot()
    aligned, details = mod.checkout_alignment(checkout, target)
    # No ordinary Git command may refresh either index before this comparison.
    after = snapshot()
    assert aligned is True and details["reason"] == "exact_clean_pins"
    assert details["checked_modules"] == ["child"]
    assert after == before


@pytest.mark.parametrize("inherited", [None, "0", "1"])
def test_optional_locks_override_is_scoped_to_alignment(sandbox, monkeypatch, inherited):
    mod, checkout, origin, _, calls, _, git = sandbox
    if inherited is None:
        monkeypatch.delenv("GIT_OPTIONAL_LOCKS", raising=False)
    else:
        monkeypatch.setenv("GIT_OPTIONAL_LOCKS", inherited)
    (origin / "file").write_text("actual new upstream")
    git(origin, "add", "file"); git(origin, "commit", "-m", "advance")
    assert mod.main() == 0
    assert expensive(calls)
    probes = [(cmd, kwargs) for cmd, kwargs in calls
              if cmd[:2] in (["git", "status"], ["git", "ls-tree"], ["git", "for-each-ref"])
              or cmd == ["git", "clean", "-ndx"]]
    assert probes
    for cmd, kwargs in probes:
        assert kwargs["env"]["GIT_OPTIONAL_LOCKS"] == "0"
        assert kwargs["timeout"] == 5
        if cmd[1] == "status":
            assert "--ignore-submodules=none" in cmd
    for cmd, kwargs in calls:
        if cmd in expensive(calls) or cmd[:2] == ["git", "fetch"]:
            assert kwargs["env"].get("GIT_OPTIONAL_LOCKS") == inherited
    assert os.environ.get("GIT_OPTIONAL_LOCKS") == inherited


def test_real_clean_same_oid_fetches_then_skips_expensive_alignment(sandbox):
    mod, checkout, origin, child, calls, _, git = sandbox
    assert mod.main() == 0
    assert ["git", "fetch", "--no-recurse-submodules", "origin",
            "+refs/heads/main:refs/remotes/origin/main"] in [cmd for cmd, _ in calls]
    assert expensive(calls) == []
    assert git(checkout, "rev-parse", "HEAD") == git(origin, "rev-parse", "HEAD")
    assert '"route": "unchanged"' in mod.LOG_PATH.read_text()
    child_calls = [kwargs for cmd, kwargs in calls if any(str(x).endswith("panorama-collect.py") for x in cmd)]
    assert child_calls[0]["env"]["OMOSTATION_STATE_ROOT"].endswith("authority")
    assert child_calls[0]["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
    for cmd, kwargs in calls:
        if cmd[0] == "git":
            assert kwargs["env"]["GIT_NO_REPLACE_OBJECTS"] == "1"
            assert kwargs["env"]["GIT_NO_LAZY_FETCH"] == "1"
            assert kwargs["env"]["PYTHONDONTWRITEBYTECODE"] == "1"


def test_real_upstream_change_runs_original_alignment_and_new_target(sandbox):
    mod, checkout, origin, _, calls, _, git = sandbox
    (origin / "file").write_text("actual new upstream")
    git(origin, "add", "file"); git(origin, "commit", "-m", "advance")
    assert mod.main() == 0
    assert expensive(calls) == [["git", "reset", "--hard", "origin/main"],
        ["git", "clean", "-fdx"], ["git", "submodule", "sync", "--recursive"],
        ["git", "submodule", "update", "--init", "--depth",
         str(mod.SUBMODULE_HISTORY_DEPTH)],
        ["git", "submodule", "foreach", "--quiet",
         f"git fetch --depth {mod.SUBMODULE_HISTORY_DEPTH} origin"]]
    assert git(checkout, "rev-parse", "HEAD") == git(origin, "rev-parse", "HEAD")
    assert (checkout / "file").read_text() == "actual new upstream"


@pytest.mark.parametrize("residue", ["untracked", "ignored", "__pycache__/cache.pyc"])
def test_real_untracked_and_ignored_residue_cannot_take_fast_path(sandbox, residue):
    mod, checkout, _, _, calls, _, _ = sandbox
    path = checkout / residue; path.parent.mkdir(parents=True, exist_ok=True); path.write_text("residue")
    assert mod.main() == 0
    assert expensive(calls)
    assert not path.exists()
    calls.clear()
    assert mod.main() == 0
    assert expensive(calls) == []


@pytest.mark.parametrize("change", ["root_dirty", "child_dirty", "child_wrong_pin", "missing_child"])
def test_real_checkout_and_child_drift_reject_alignment(sandbox, change):
    mod, checkout, _, child, _, _, git = sandbox
    target = git(checkout, "rev-parse", "HEAD")
    if change == "root_dirty": (checkout / "file").write_text("dirty")
    elif change == "child_dirty": (checkout / "child/file").write_text("dirty child")
    elif change == "child_wrong_pin":
        git(checkout / "child", "config", "user.email", "fixture@example.invalid")
        git(checkout / "child", "config", "user.name", "Fixture")
        (checkout / "child/file").write_text("new child")
        git(checkout / "child", "add", "file"); git(checkout / "child", "commit", "-m", "wrong pin")
    else: (checkout / "child/.git").rename(checkout / "child/.git-retained")
    aligned, details = mod.checkout_alignment(checkout, target)
    assert aligned is False and details["reason"] != "exact_clean_pins"


@pytest.mark.parametrize("failure", ["fetch_fail", "wrong_origin"])
def test_transport_failure_never_uses_cached_main_as_fresh(sandbox, failure):
    mod, _, _, _, calls, transport, _ = sandbox
    transport[failure] = True
    assert mod.main() == 1
    assert not any(any(str(x).endswith("panorama-collect.py") for x in cmd) for cmd, _ in calls)
    assert expensive(calls) == []


def test_replace_refs_and_upward_git_root_are_rejected(sandbox, tmp_path):
    mod, checkout, _, _, _, _, git = sandbox
    head = git(checkout, "rev-parse", "HEAD")
    git(checkout, "update-ref", "refs/replace/" + "a" * 40, head)
    aligned, details = mod.checkout_alignment(checkout, head)
    assert aligned is False and details["reason"] == "replace_refs_present"
    nested = checkout / "not-a-checkout"; nested.mkdir()
    aligned, details = mod.checkout_alignment(nested, head)
    assert aligned is False and details["reason"] == "checkout_top_mismatch"


def test_invalid_target_oid_is_not_a_warm_success(sandbox):
    mod, checkout, _, _, _, _, _ = sandbox
    for target in ("", "a" * 8, "g" * 40):
        assert mod.checkout_alignment(checkout, target)[0] is False


def test_real_remote_main_deletion_cannot_reuse_cached_tracking_ref(sandbox):
    mod, checkout, origin, _, calls, _, git = sandbox
    cached = git(checkout, "rev-parse", "refs/remotes/origin/main")
    git(origin, "update-ref", "-d", "refs/heads/main")
    assert mod.main() == 1
    assert git(checkout, "rev-parse", "refs/remotes/origin/main") == cached
    assert not any(any(str(x).endswith("panorama-collect.py") for x in cmd) for cmd, _ in calls)


# A8 (OMO 外部执行事务) 的判据是
#   git -C projects/omo merge-base --is-ancestor <omo PR #173 merge> HEAD
# 对象不在本地时该判据结构性不可判, 与 pin 是否正确无关。depth 1 的检出正是如此,
# 于是生产里 A8 永远 ABSENT (2026-10-20 实证: publisher 检出的 projects/omo 只有
# 1 个 commit, 5e1f7eae 不在本地)。下面的断言钉住修复形状: 不许退回 depth 1。
A8_OMO_MERGE_DISTANCE_AT_2026_10_20 = 60


def test_submodule_history_depth_covers_the_a8_ancestry_check(sandbox):
    mod = sandbox[0]
    assert isinstance(mod.SUBMODULE_HISTORY_DEPTH, int)
    assert mod.SUBMODULE_HISTORY_DEPTH >= A8_OMO_MERGE_DISTANCE_AT_2026_10_20, (
        "A8 的 merge-base --is-ancestor 判据需要这段历史; pin 前移后需重新测量并上调"
    )


def test_real_upstream_change_does_not_emit_a_depth_one_submodule_update(sandbox):
    """depth 1 是 A8 永久 ABSENT 的直接成因; 任何回退都该让这条断言变红。"""
    mod, _, origin, _, calls, _, git = sandbox
    (origin / "file").write_text("another upstream advance")
    git(origin, "add", "file"); git(origin, "commit", "-m", "advance again")
    assert mod.main() == 0
    for cmd in (cmd for cmd, _ in calls if cmd[:3] == ["git", "submodule", "update"]):
        depth = int(cmd[cmd.index("--depth") + 1])
        assert depth > 1, f"depth 1 无法评估 A8 的祖先判据: {cmd}"
        assert depth == mod.SUBMODULE_HISTORY_DEPTH


def test_real_upstream_change_widens_submodule_history(sandbox):
    """`--depth` 加不出历史: 已存在的浅子模块重跑 update 仍是 1 个 commit。

    所以 publisher 必须显式 fetch, 否则 A8 的祖先判据在生产里永不可判。
    """
    mod, _, origin, _, calls, _, git = sandbox
    (origin / "file").write_text("history widening advance")
    git(origin, "add", "file"); git(origin, "commit", "-m", "advance for history")
    assert mod.main() == 0
    deepens = [cmd for cmd, _ in calls if cmd[:3] == ["git", "submodule", "foreach"]]
    assert deepens, "publisher 必须显式加深深子模块历史"
    for cmd in deepens:
        script = cmd[-1]
        assert script == f"git fetch --depth {mod.SUBMODULE_HISTORY_DEPTH} origin", cmd


def test_real_submodule_history_deepen_retries_a_flaky_network(sandbox):
    """一次 sweep 是 16 个子模块各取一次, 网络抖动下单次尝试几乎必然失败。

    本机实测 (2026-10-20) 连 github.com 的 TLS 握手约 1/3 概率 SSL_ERROR_SYSCALL,
    于是 1-(2/3)^16 ≈ 99.7% 的 sweep 会失败 —— 不重试就等于没有修。
    """
    mod, _, origin, _, calls, transport, git = sandbox
    (origin / "file").write_text("flaky network advance")
    git(origin, "add", "file"); git(origin, "commit", "-m", "advance for flaky")
    transport["deepen_fail_times"] = mod.SUBMODULE_DEEPEN_ATTEMPTS - 1
    assert mod.main() == 0
    deepens = [cmd for cmd, _ in calls if cmd[:3] == ["git", "submodule", "foreach"]]
    assert len(deepens) == mod.SUBMODULE_DEEPEN_ATTEMPTS, deepens
    assert transport["deepen_fail_times"] == 0


def test_real_submodule_history_deepen_fails_closed_when_retries_are_exhausted(sandbox):
    """重试不是掩盖: 用尽后必须仍然 fail-closed。"""
    mod, _, origin, _, calls, transport, git = sandbox
    (origin / "file").write_text("permanently flaky advance")
    git(origin, "add", "file"); git(origin, "commit", "-m", "advance for permanent flake")
    transport["deepen_fail_times"] = mod.SUBMODULE_DEEPEN_ATTEMPTS + 5
    assert mod.main() == 1
    deepens = [cmd for cmd, _ in calls if cmd[:3] == ["git", "submodule", "foreach"]]
    assert len(deepens) == mod.SUBMODULE_DEEPEN_ATTEMPTS, deepens
    assert '"event": "failed"' in mod.LOG_PATH.read_text()
