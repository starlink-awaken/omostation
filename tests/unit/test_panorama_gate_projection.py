import importlib.util
import json

import pytest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"


def _module():
    spec = importlib.util.spec_from_file_location("panorama_gate_projection", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_collect_gates_preserves_partial_results_when_wrapper_exits_nonzero(
    tmp_path, monkeypatch
) -> None:
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    payload = {
        "all_ok": False,
        "gates": [
            {"gate": "A1 Workflow/Git", "ok": True, "exit_code": 0, "output": "PASS"},
            {"gate": "A2 Resident/Host", "ok": False, "exit_code": 1, "output": "non-zero: ['stale_beats']"},
        ],
    }
    monkeypatch.setattr(module, "run", lambda command, timeout=120: (1, json.dumps(payload)))
    monkeypatch.setattr(module, "collect_a6_gate", lambda: {"id": "A6", "verdict": "PASS"})
    monkeypatch.setattr(module, "collect_a7_gate", lambda: {"id": "A7", "verdict": "NOT_ADMITTED"})
    monkeypatch.setattr(module, "collect_a8_gate", lambda: {"id": "A8", "verdict": "PASS"})
    monkeypatch.setattr(module, "collect_a9_gate", lambda payload=None, **kwargs: {"id": "A9", "verdict": "PASS"})
    monkeypatch.setattr(module, "collect_rf0_gate", lambda: {"id": "RF0", "verdict": "NOT_ADMITTED"})

    gates = {gate["id"]: gate for gate in module.collect_gates()}

    assert gates["A1"]["verdict"] == "PASS"
    assert gates["A1"]["live"] is True
    assert gates["A2"]["verdict"] == "FAIL"
    assert gates["A2"]["live"] is True
    assert "stale_beats" in gates["A2"]["detail"]


def test_collect_gates_fails_closed_on_invalid_health_payload(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "run", lambda command, timeout=120: (1, "not-json"))
    monkeypatch.setattr(module, "collect_a6_gate", lambda: {"id": "A6", "verdict": "PASS"})
    monkeypatch.setattr(module, "collect_a7_gate", lambda: {"id": "A7", "verdict": "NOT_ADMITTED"})
    monkeypatch.setattr(module, "collect_a8_gate", lambda: {"id": "A8", "verdict": "PASS"})
    monkeypatch.setattr(module, "collect_a9_gate", lambda payload=None, **kwargs: {"id": "A9", "verdict": "PASS"})
    monkeypatch.setattr(module, "collect_rf0_gate", lambda: {"id": "RF0", "verdict": "NOT_ADMITTED"})

    gates = {gate["id"]: gate for gate in module.collect_gates()}

    assert [gates[gid]["verdict"] for gid in ("A1", "A2", "A3", "A4", "A5")] == ["FAIL"] * 5
    assert all(gates[gid]["live"] is False for gid in ("A1", "A2", "A3", "A4", "A5"))


def test_collect_gates_passes_runtime_and_code_roots(tmp_path, monkeypatch) -> None:
    module = _module()
    runtime_root = tmp_path / "runtime"
    code_root = tmp_path / "code"
    monkeypatch.setattr(module, "ROOT", runtime_root)
    monkeypatch.setattr(module, "CODE_ROOT", code_root)
    seen = {}

    def fake_run(command, timeout=120):
        seen["command"] = command
        payload = {
            "all_ok": True,
            "workspace": str(runtime_root),
            "code_root": str(code_root),
            "gates": [
                {"gate": "A1 Workflow/Git", "ok": True, "exit_code": 0, "output": "PASS"},
                {"gate": "A2 Resident/Host", "ok": True, "exit_code": 0, "output": "all technical checks pass"},
                {"gate": "A3 Governance Python", "ok": True, "exit_code": 0, "output": "PASS"},
                {"gate": "A4 Scheduler", "ok": True, "exit_code": 0, "output": "{}"},
                {"gate": "A5 Reference/Launchd", "ok": True, "exit_code": 0, "output": "all technical checks pass"},
            ],
        }
        return 0, json.dumps(payload)

    monkeypatch.setattr(module, "run", fake_run)
    monkeypatch.setattr(module, "collect_a6_gate", lambda: {"id": "A6", "verdict": "PASS"})
    monkeypatch.setattr(module, "collect_a7_gate", lambda: {"id": "A7", "verdict": "NOT_ADMITTED"})
    monkeypatch.setattr(module, "collect_a8_gate", lambda: {"id": "A8", "verdict": "PASS"})
    monkeypatch.setattr(module, "collect_a9_gate", lambda payload=None, **kwargs: {"id": "A9", "verdict": "PASS"})
    monkeypatch.setattr(module, "collect_rf0_gate", lambda: {"id": "RF0", "verdict": "NOT_ADMITTED"})

    gates = module.collect_gates()
    command = seen["command"]

    assert command[command.index("--workspace") + 1] == str(runtime_root)
    assert command[command.index("--code-root") + 1] == str(code_root)
    assert [gate["verdict"] for gate in gates[:5]] == ["PASS"] * 5


def test_admission_verifiers_use_code_root_but_runtime_root_cwd(
    tmp_path, monkeypatch
) -> None:
    module = _module()
    runtime_root = tmp_path / "runtime"
    code_root = tmp_path / "code"
    verifier_dir = code_root / "bin/gac"
    verifier_dir.mkdir(parents=True)
    for name in (
        "ruflo-rf0-verify.py", "orca-r0-verify.py", "multica-as0-verify.py",
    ):
        (verifier_dir / name).touch()
    monkeypatch.setattr(module, "ROOT", runtime_root)
    monkeypatch.setattr(module, "CODE_ROOT", code_root)
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs.get("cwd")))
        report = {
            "ruflo-rf0-verify.py": {
                "ok": True,
                "checks": {
                    "binary": True, "doctor": True, "daemon_stopped": True,
                    "workers_off": True, "no_second_queue": True,
                    "cross_agent_dependency_zero": True,
                },
                "version": "3.42.2",
                "doctor_summary": {"passed": 13, "warnings": 0},
            },
            "orca-r0-verify.py": {
                "ok": True, "runtime_ready": True,
                "probes": {"passed": 6, "total": 6},
                "r0_transactions": {"accepted": 1, "transactions": [{"ok": True}]},
                "trust": {"write_argv_guard": {"ok": True}},
            },
            "multica-as0-verify.py": {
                "ok": True,
                "api": {"passed": 30, "total": 30},
                "topology": {"passed": 7, "total": 7},
                "trust": {"passed": 3, "total": 3},
            },
        }[Path(command[1]).name]
        return type("Completed", (), {"stdout": json.dumps(report)})()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    reports = [
        module.collect_rf0_gate(),
        module.collect_a6_gate(),
        module.collect_a7_gate(),
    ]

    assert all(report["verdict"] == "PASS" for report in reports)
    assert len(calls) == 3
    for command, cwd in calls:
        assert command[1].startswith(str(code_root / "bin/gac/"))
        assert cwd == runtime_root


def test_multica_gate_budgets_full_readonly_matrix_and_bypasses_hosts(
    tmp_path, monkeypatch
) -> None:
    module = _module()
    runtime_root = tmp_path / "runtime"
    code_root = tmp_path / "code"
    verifier = code_root / "bin/gac/multica-as0-verify.py"
    verifier.parent.mkdir(parents=True)
    verifier.touch()
    monkeypatch.setattr(module, "ROOT", runtime_root)
    monkeypatch.setattr(module, "CODE_ROOT", code_root)
    monkeypatch.setenv("NO_PROXY", "internal.example")
    monkeypatch.setenv("no_proxy", "internal.example")
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        seen.update(kwargs)
        return type(
            "Completed",
            (),
            {
                "stdout": json.dumps({
                    "ok": True,
                    "api": {"passed": 30, "total": 30},
                    "topology": {"passed": 7, "total": 7},
                    "trust": {"passed": 3, "total": 3},
                })
            },
        )()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    report = module.collect_a7_gate()

    assert report["verdict"] == "PASS"
    assert module.MULTICA_AS0_TIMEOUT_S >= 240
    assert seen["timeout"] == module.MULTICA_AS0_TIMEOUT_S
    assert seen["cwd"] == runtime_root
    for key in ("NO_PROXY", "no_proxy"):
        hosts = seen["env"][key].split(",")
        assert "internal.example" in hosts
        assert "multica.ai" in hosts
        assert ".multica.ai" in hosts


HEALTH_SOURCES = [SCRIPT, ROOT / "bin/panorama/assets/host/panorama-collect-main.py.asset"]


def _health_git(root, *args):
    import os
    import subprocess

    result = subprocess.run(
        ["git", "--no-replace-objects", "-C", str(root), *args],
        capture_output=True, text=True, timeout=10,
        env=dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GIT_NO_LAZY_FETCH="1"),
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _health_fixture(tmp_path, monkeypatch, source, *, shallow=False):
    import ast
    import datetime
    import os
    import re
    import subprocess
    import sys
    import time

    bare, seed, code = (tmp_path / name for name in ("remote.git", "seed", "code"))
    for path in (bare, seed):
        path.mkdir()
    _health_git(bare, "init", "--bare", "--initial-branch=main")
    _health_git(seed, "init", "--initial-branch=main")
    _health_git(seed, "config", "user.name", "Fixture")
    _health_git(seed, "config", "user.email", "fixture@example.invalid")
    (seed / "tracked.txt").write_text("initial\n")
    _health_git(seed, "add", "tracked.txt")
    _health_git(seed, "commit", "-m", "initial")
    _health_git(seed, "remote", "add", "origin", str(bare))
    _health_git(seed, "push", "origin", "main")
    clone_args = ["clone", *( ["--depth=1"] if shallow else []), bare.as_uri(), str(code)]
    _health_git(tmp_path, *clone_args)
    _health_git(code, "config", "user.name", "Fixture")
    _health_git(code, "config", "user.email", "fixture@example.invalid")
    _health_git(code, "remote", "set-url", "origin", "https://github.com/starlink-awaken/omostation.git")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    shim = bindir / "gh"
    shim.write_text(f"#!{sys.executable}\n" + '''import os, subprocess, sys
assert sys.argv[1:] == ["api", "--hostname", "github.com", "repos/starlink-awaken/omostation/git/ref/heads/main", "--jq", '. | select(.ref == "refs/heads/main" and .object.type == "commit") | .object.sha']
for key, value in {"GIT_OPTIONAL_LOCKS":"0", "GIT_NO_LAZY_FETCH":"1", "GIT_NO_REPLACE_OBJECTS":"1", "GIT_TERMINAL_PROMPT":"0", "GH_PROMPT_DISABLED":"1"}.items():
    assert os.environ.get(key) == value
mode = os.environ.get("HEALTH_FIXTURE_REMOTE_MODE", "ok")
if mode == "descendant-overflow":
    child = subprocess.Popen([sys.executable, "-c", "import os,time;from pathlib import Path;Path(os.environ['HEALTH_FIXTURE_CHILD_PID_FILE']).write_text(str(os.getpid()));print('x'*1024,flush=True);time.sleep(120)"])
    child.wait()
    sys.exit(0)
if mode != "ok":
    if mode == "failed":
        print("https://credential:secret@example.invalid", file=sys.stderr)
        sys.exit(1)
    print({"invalid": "not-an-oid", "missing": "", "oversized": "x" * 1024}[mode])
    sys.exit(0)
result = subprocess.run(["git", "--no-replace-objects", "ls-remote", "--refs", os.environ["HEALTH_FIXTURE_REMOTE"], "refs/heads/main"], capture_output=True, text=True, timeout=5)
if result.returncode:
    sys.exit(1)
print(result.stdout.split()[0] if result.stdout.strip() else "")
''')
    shim.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("HEALTH_FIXTURE_REMOTE", str(bare))
    monkeypatch.delenv("HEALTH_FIXTURE_REMOTE_MODE", raising=False)
    tree = ast.parse(source.read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "collect_code_root_health")
    def legacy_run(command, timeout=120):
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout.strip()
    namespace = dict(datetime=datetime.datetime, UTC=datetime.timezone.utc, Path=Path,
                     CODE_ROOT=code, ROOT=tmp_path / "runtime", os=os, re=re,
                     subprocess=subprocess, time=time, run=legacy_run)
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
    return bare, seed, code, namespace


def _health_snapshot(code):
    import hashlib

    index = code / ".git/index"
    return hashlib.sha256(index.read_bytes()).hexdigest(), index.stat().st_mtime_ns, _health_git(code, "show-ref")


def _health_advance(seed):
    (seed / "tracked.txt").write_text("advanced\n")
    _health_git(seed, "add", "tracked.txt")
    _health_git(seed, "commit", "-m", "advance")
    _health_git(seed, "push", "origin", "main")
    return _health_git(seed, "rev-parse", "HEAD")


@pytest.mark.parametrize("source", HEALTH_SOURCES, ids=["collector", "host-asset"])
@pytest.mark.parametrize("shallow", [False, True], ids=["full", "shallow"])
def test_code_root_health_equal_remote_is_read_only(tmp_path, monkeypatch, source, shallow):
    import os

    bare, seed, code, ns = _health_fixture(tmp_path, monkeypatch, source, shallow=shallow)
    # Invalidated stat cache would make ordinary status rewrite the index.
    tracked = code / "tracked.txt"
    stamp = tracked.stat().st_mtime_ns + 2_000_000_000
    os.utime(tracked, ns=(stamp, stamp))
    before = _health_snapshot(code)
    report = ns["collect_code_root_health"]()
    assert report["verdict"] == "PASS"
    assert report["origin_main_oid"] == _health_git(bare, "rev-parse", "main")
    assert report["local_origin_main_oid"] == report["head_oid"]
    assert report["behind_origin_main"] == report["ahead_origin_main"] == 0
    assert report["remote_main_observed_at"] >= report["checked_at"]
    assert report["comparison_scope"] == "official_remote_main"
    assert report["auto_update_performed"] is False
    assert _health_snapshot(code) == before


@pytest.mark.parametrize("source", HEALTH_SOURCES, ids=["collector", "host-asset"])
def test_code_root_health_rejects_unfetched_remote_advance(tmp_path, monkeypatch, source):
    bare, seed, code, ns = _health_fixture(tmp_path, monkeypatch, source)
    remote = _health_advance(seed)
    old = _health_git(code, "rev-parse", "HEAD")
    assert old == _health_git(code, "rev-parse", "origin/main") != remote
    before = _health_snapshot(code)
    report = ns["collect_code_root_health"]()
    assert report["verdict"] == "STALE"
    assert report["origin_main_oid"] == remote
    assert report["local_origin_main_oid"] == old
    assert report["behind_origin_main"] is report["ahead_origin_main"] is None
    assert report["error"] == "remote_commit_not_local"
    assert _health_snapshot(code) == before


@pytest.mark.parametrize("source", HEALTH_SOURCES, ids=["collector", "host-asset"])
def test_code_root_health_counts_real_remote_object_and_dirty_tree(tmp_path, monkeypatch, source):
    bare, seed, code, ns = _health_fixture(tmp_path, monkeypatch, source)
    remote = _health_advance(seed)
    # Fixture setup explicitly obtains the object, leaving origin/main unchanged.
    _health_git(code, "fetch", str(bare), "main")
    before = _health_snapshot(code)
    report = ns["collect_code_root_health"]()
    assert report["verdict"] == "STALE"
    assert report["origin_main_oid"] == remote != report["local_origin_main_oid"]
    assert (report["behind_origin_main"], report["ahead_origin_main"]) == (1, 0)
    assert _health_snapshot(code) == before
    (code / "local.txt").write_text("local\n")
    _health_git(code, "add", "local.txt")
    _health_git(code, "commit", "-m", "local branch")
    report = ns["collect_code_root_health"]()
    assert report["verdict"] == "STALE"
    assert (report["behind_origin_main"], report["ahead_origin_main"]) == (1, 1)
    (code / "tracked.txt").write_text("dirty\n")
    before = _health_snapshot(code)
    report = ns["collect_code_root_health"]()
    assert report["verdict"] == "DIRTY"
    assert report["dirty_count"] == 1
    assert _health_snapshot(code) == before


@pytest.mark.parametrize("source", HEALTH_SOURCES, ids=["collector", "host-asset"])
def test_code_root_health_shallow_unequal_counts_unknown(tmp_path, monkeypatch, source):
    bare, seed, code, ns = _health_fixture(tmp_path, monkeypatch, source, shallow=True)
    _health_advance(seed)
    _health_git(code, "fetch", "--depth=1", str(bare), "main")
    before = _health_snapshot(code)
    report = ns["collect_code_root_health"]()
    assert report["verdict"] == "STALE"
    assert report["behind_origin_main"] is report["ahead_origin_main"] is None
    assert report["error"] == "ancestry_unavailable"
    assert _health_snapshot(code) == before


@pytest.mark.parametrize("source", HEALTH_SOURCES, ids=["collector", "host-asset"])
@pytest.mark.parametrize("mode", ["failed", "missing", "invalid", "oversized"])
def test_code_root_health_remote_failure_never_falls_back(tmp_path, monkeypatch, source, mode):
    import json

    bare, seed, code, ns = _health_fixture(tmp_path, monkeypatch, source)
    monkeypatch.setenv("HEALTH_FIXTURE_REMOTE_MODE", mode)
    before = _health_snapshot(code)
    report = ns["collect_code_root_health"]()
    assert report["verdict"] == "UNAVAILABLE"
    assert report["available"] is False
    assert report["origin_main_oid"] is report["remote_main_observed_at"] is None
    assert report["behind_origin_main"] is report["ahead_origin_main"] is None
    assert report["error"] == "remote_main_unavailable"
    assert "credential" not in json.dumps(report)
    assert _health_snapshot(code) == before


@pytest.mark.parametrize("source", HEALTH_SOURCES, ids=["collector", "host-asset"])
@pytest.mark.parametrize("mismatch", ["origin", "top"])
def test_code_root_health_rejects_repository_identity(tmp_path, monkeypatch, source, mismatch):
    bare, seed, code, ns = _health_fixture(tmp_path, monkeypatch, source)
    if mismatch == "origin":
        _health_git(code, "remote", "set-url", "origin", "https://credential:secret@example.invalid/repo")
    else:
        (code / "nested").mkdir()
        ns["CODE_ROOT"] = code / "nested"
    before = _health_snapshot(code)
    report = ns["collect_code_root_health"]()
    assert report["verdict"] == "UNAVAILABLE"
    assert report["error"] == "repository_identity_mismatch"
    assert report["origin_main_oid"] is None
    assert _health_snapshot(code) == before


@pytest.mark.parametrize("source", HEALTH_SOURCES, ids=["collector", "host-asset"])
def test_code_root_health_missing_tracking_ref_uses_fresh_remote(tmp_path, monkeypatch, source):
    bare, seed, code, ns = _health_fixture(tmp_path, monkeypatch, source)
    _health_git(code, "update-ref", "-d", "refs/remotes/origin/main")
    before = _health_snapshot(code)
    report = ns["collect_code_root_health"]()
    assert report["verdict"] == "PASS"
    assert report["local_origin_main_oid"] is None
    assert report["origin_main_oid"] == report["head_oid"]
    assert _health_snapshot(code) == before


@pytest.mark.parametrize("source", HEALTH_SOURCES, ids=["collector", "host-asset"])
def test_code_root_health_deleted_remote_main_is_unavailable(tmp_path, monkeypatch, source):
    bare, seed, code, ns = _health_fixture(tmp_path, monkeypatch, source)
    _health_git(bare, "tag", "main", "refs/heads/main")
    _health_git(bare, "update-ref", "-d", "refs/heads/main")
    assert _health_git(bare, "rev-parse", "refs/tags/main")
    before = _health_snapshot(code)
    report = ns["collect_code_root_health"]()
    assert report["verdict"] == "UNAVAILABLE"
    assert report["error"] == "remote_main_unavailable"
    assert report["origin_main_oid"] is None
    assert _health_snapshot(code) == before


@pytest.mark.parametrize("source", HEALTH_SOURCES, ids=["collector", "host-asset"])
def test_code_root_health_ignores_replace_objects(tmp_path, monkeypatch, source):
    bare, seed, code, ns = _health_fixture(tmp_path, monkeypatch, source)
    initial = _health_git(code, "rev-parse", "HEAD")
    (code / "local.txt").write_text("local\n")
    _health_git(code, "add", "local.txt")
    _health_git(code, "commit", "-m", "ahead")
    local = _health_git(code, "rev-parse", "HEAD")
    _health_git(code, "replace", local, initial)
    before = _health_snapshot(code)
    report = ns["collect_code_root_health"]()
    assert report["verdict"] == "STALE"
    assert (report["behind_origin_main"], report["ahead_origin_main"]) == (0, 1)
    assert _health_snapshot(code) == before


@pytest.mark.parametrize("source", HEALTH_SOURCES, ids=["collector", "host-asset"])
def test_code_root_health_bounds_output_and_terminates_own_descendants(tmp_path, monkeypatch, source):
    import os
    import subprocess
    import time

    bare, seed, code, ns = _health_fixture(tmp_path, monkeypatch, source)
    pid_file = tmp_path / "read-child.pid"
    monkeypatch.setenv("HEALTH_FIXTURE_CHILD_PID_FILE", str(pid_file))
    monkeypatch.setenv("HEALTH_FIXTURE_REMOTE_MODE", "descendant-overflow")
    before = _health_snapshot(code)
    started = time.monotonic()
    report = ns["collect_code_root_health"]()
    assert report["verdict"] == "UNAVAILABLE"
    assert report["error"] == "remote_main_unavailable"
    assert time.monotonic() - started < 10
    child_pid = int(pid_file.read_text())
    # A killed orphan may briefly await reaping; it must never remain running.
    state = subprocess.run(["ps", "-p", str(child_pid), "-o", "stat="],
                           capture_output=True, text=True, timeout=2).stdout.strip()
    assert not state or state.startswith("Z")
    assert _health_snapshot(code) == before


PROTECTED_HOST_FUNCTIONS = (
    "collect_a7_gate", "_read_claims_preflight", "collect_claims_observation_progress",
)


def _protected_namespace(source, tmp_path):
    """Load just the protected functions, without executing a runtime collector."""
    import ast
    from datetime import datetime, timezone
    import subprocess
    import sys
    from types import SimpleNamespace

    tree = ast.parse(source.read_text())
    selected = [node for node in tree.body if (
        isinstance(node, ast.FunctionDef) and node.name in PROTECTED_HOST_FUNCTIONS
    ) or (
        isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in {
                "MULTICA_AS0_TIMEOUT_S", "MULTICA_AS0_DIRECT_HOSTS",
            } for target in node.targets
        )
    )]
    namespace = dict(Path=Path, datetime=datetime, UTC=timezone.utc, json=json,
                     os=SimpleNamespace(environ={"NO_PROXY": "internal.example", "no_proxy": "internal.example"}),
                     subprocess=subprocess, sys=sys,
                     ROOT=tmp_path / "runtime", CODE_ROOT=tmp_path / "code")
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), "exec"), namespace)
    return namespace


@pytest.mark.parametrize("name", PROTECTED_HOST_FUNCTIONS)
def test_host_protected_function_matches_canonical(name):
    import ast

    functions = []
    for source in HEALTH_SOURCES:
        node = next(node for node in ast.parse(source.read_text()).body
                    if isinstance(node, ast.FunctionDef) and node.name == name)
        functions.append(ast.dump(node, include_attributes=False))
    assert functions[0] == functions[1]


@pytest.mark.parametrize("source", HEALTH_SOURCES, ids=["canonical", "host-asset"])
@pytest.mark.parametrize("failure", ["timeout", "invalid-schema", "invalid-json"])
def test_host_claims_preflight_diagnostics_never_expose_raw_output(tmp_path, source, failure):
    import subprocess
    from types import SimpleNamespace

    ns = _protected_namespace(source, tmp_path)
    verifier = ns["CODE_ROOT"] / "bin/gac/claims-shadow-preflight.py"
    verifier.parent.mkdir(parents=True)
    verifier.touch()
    secret = "fixture-sensitive-output"

    def fake_run(command, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 30, output=secret, stderr=secret)
        return SimpleNamespace(stdout=secret if failure == "invalid-json" else
                               json.dumps({"schema": "wrong", "private": secret}), stderr=secret)

    ns["subprocess"] = SimpleNamespace(run=fake_run)
    report, error = ns["_read_claims_preflight"](ns["ROOT"])
    expected = {"timeout": "TimeoutExpired", "invalid-schema": "invalid_preflight_payload",
                "invalid-json": "JSONDecodeError"}[failure]
    assert report is None
    assert error == expected
    assert secret not in json.dumps((report, error))


@pytest.mark.parametrize("source", HEALTH_SOURCES, ids=["canonical", "host-asset"])
@pytest.mark.parametrize("malformed_current", [False, True])
def test_host_claims_observation_grades_only_current_attempt(tmp_path, source, malformed_current):
    from datetime import datetime, timedelta, timezone

    ns = _protected_namespace(source, tmp_path)
    evidence = tmp_path / "observation"
    evidence.mkdir()
    started = datetime.now(timezone.utc) - timedelta(minutes=10)
    descriptor, receipt = "sha256:" + "1" * 64, "sha256:" + "2" * 64
    summary = {"started_at_utc": started.isoformat(), "samples": 2,
               "invalid": False, "errors": 0, "max_gap_seconds": 60,
               "activation_state": "shadow-active", "descriptor_digest": descriptor,
               "expected_last_receipt": receipt}
    old = {"sampled_at_utc": (started - timedelta(minutes=20)).isoformat(),
           "error": "old-attempt-error", "status": {
               "descriptor_digest": "old-descriptor", "activation_state": "unactivated",
               "last_receipt_digest": "old-receipt", "sequence": 99}}
    records = [old] + [
        {"sampled_at_utc": (started + timedelta(seconds=seconds)).isoformat(),
         "status": {"descriptor_digest": descriptor, "activation_state": "shadow-active",
                    "last_receipt_digest": receipt, "sequence": sequence}}
        for seconds, sequence in ((1, 1), (61, 2))
    ]
    if malformed_current:
        records.append({"broken-current-record": True})
    (evidence / "summary.json").write_text(json.dumps(summary))
    (evidence / "samples.jsonl").write_text("".join(json.dumps(row) + "\n" for row in records))
    ns["collect_claims_activation_request"] = lambda: {
        "available": True, "observation": {"evidence_dir": str(evidence),
            "duration_seconds": 86400, "minimum_samples": 1440, "maximum_gap_seconds": 120},
        "execution_receipt": {"receipt_digest": receipt},
    }
    report = ns["collect_claims_observation_progress"]()
    assert report["sample_count"] == 2
    assert report["observed_max_gap_seconds"] == 60
    assert report["descriptor_variants"] == [descriptor]
    assert report["activation_variants"] == ["shadow-active"]
    assert report["receipt_variants"] == [receipt]
    assert report["first_sample_at_utc"] == (started + timedelta(seconds=1)).isoformat()
    assert report["sequence_regressions"] == 0
    assert report["errors"] == int(malformed_current)
    assert report["state"] == ("INVALID" if malformed_current else "IN_PROGRESS")
    assert report["graduation_ready"] is False


@pytest.mark.parametrize("source", HEALTH_SOURCES, ids=["canonical", "host-asset"])
@pytest.mark.parametrize("timed_out", [False, True])
def test_host_multica_verifier_preserves_configured_matrix_budget(tmp_path, monkeypatch, source, timed_out):
    import subprocess
    from types import SimpleNamespace

    ns = _protected_namespace(source, tmp_path)
    verifier = ns["CODE_ROOT"] / "bin/gac/multica-as0-verify.py"
    verifier.parent.mkdir(parents=True)
    verifier.touch()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("NO_PROXY", "internal.example")
    monkeypatch.setenv("no_proxy", "internal.example")
    (Path.home() / ".local/share/zhixing-dashboard").mkdir(parents=True)
    assert ns["MULTICA_AS0_TIMEOUT_S"] == 300
    ns["MULTICA_AS0_TIMEOUT_S"] = 321
    calls = []

    def fake_run(command, **kwargs):
        calls.append({"timeout": kwargs["timeout"], "cwd": kwargs["cwd"],
                      "bypass_hosts": {key: kwargs["env"][key] for key in ("NO_PROXY", "no_proxy")}})
        if timed_out:
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return SimpleNamespace(stdout=json.dumps({"ok": True,
            "api": {"passed": 30, "total": 30},
            "topology": {"passed": 7, "total": 7}, "trust": {"passed": 3, "total": 3}}))

    ns["subprocess"] = SimpleNamespace(run=fake_run, TimeoutExpired=subprocess.TimeoutExpired)
    report = ns["collect_a7_gate"]()
    assert calls and all(call["timeout"] == 321 for call in calls)
    assert all(call["cwd"] == ns["ROOT"] for call in calls)
    for call in calls:
        for key in ("NO_PROXY", "no_proxy"):
            assert {"internal.example", "multica.ai", ".multica.ai"} <= set(call["bypass_hosts"][key].split(","))
    assert report["verdict"] == ("NOT_ADMITTED" if timed_out else "PASS")
    if timed_out:
        assert "321s" in report["detail"]
