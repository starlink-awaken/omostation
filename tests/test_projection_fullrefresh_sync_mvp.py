"""Real temporary Git pins; external collect/identity and slow shell are seams."""
import importlib.util
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
        if any(str(x).endswith("panorama-collect.py") for x in cmd):
            return subprocess.CompletedProcess(cmd, 0, "fixture collection complete", "")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", external_run)
    return module, checkout, origin, child, calls, transport, git


def expensive(calls):
    return [cmd for cmd, _ in calls if cmd[:2] in (
        ["git", "reset"], ["git", "clean"], ["git", "submodule"])
        and cmd != ["git", "clean", "-ndx"]]


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
        ["git", "submodule", "update", "--init", "--depth", "1"]]
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
