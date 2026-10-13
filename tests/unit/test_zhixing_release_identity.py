"""Real composite release identity across publisher, producer and reader."""
import ast
import importlib.util
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "bin/panorama/assets/host"


def load(name, path):
    import types
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


def git_commit(root):
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-qm", "real-source"], check=True)
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


def extract(path, names, namespace):
    nodes = [n for n in ast.parse(path.read_text()).body
             if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    assert len(nodes) == len(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


@pytest.fixture
def release_env(tmp_path, monkeypatch):
    zhs = load("release_bridge_publisher", ROOT / "bin/gac/zhixing-host-sync.py")
    host, deploy = tmp_path / "source", tmp_path / "state"
    host.mkdir()
    deploy.mkdir()
    for name in ("live_server.py", "observatory_query.py", "release_identity.py"):
        shutil.copyfile(HOST / (name + ".asset"), host / (name + ".asset"))
    oid = git_commit(host)
    baseline = deploy / "releases" / "baseline-placeholder"
    baseline.mkdir(parents=True)
    for name in ("live_server.py", "observatory_query.py"):
        shutil.copyfile(HOST / (name + ".asset"), baseline / name)
    (baseline / "runtime_paths.py").write_text("# isolated revision-reader seam\n")
    (baseline / "collectors").mkdir()
    (baseline / "collectors/base.py").write_text("# unselected dependency retained\n")
    old_oid = git_commit(baseline)
    old = baseline.with_name(old_oid)
    baseline.rename(old)
    monkeypatch.setattr(zhs, "HOST_DIR", host)
    monkeypatch.setattr(zhs, "DASHBOARD_DIR", deploy)
    monkeypatch.setattr(zhs, "RELEASES_DIR", deploy / "releases")
    monkeypatch.setattr(zhs, "CURRENT_LINK", deploy / "current")
    monkeypatch.setattr(zhs, "CURRENT_ENTRYPOINT", deploy / "current/live_server.py")
    assert zhs._switch_current(old)["ok"]
    monkeypatch.setattr(zhs, "_running_registered_runtime", lambda: {"ok": True, "entrypoint": str(zhs.CURRENT_ENTRYPOINT.resolve())})
    return zhs, host, old, oid


def publish(release_env):
    zhs, _, _, _ = release_env
    result = zhs.publish(["live_server.py", "observatory_query.py", "release_identity.py"])
    assert result["ok"], result
    return zhs.CURRENT_LINK.resolve()


def test_real_publish_producer_reader_and_restore(release_env):
    zhs, _, old, oid = release_env
    root = publish(release_env)
    assert not (root / ".git").exists()
    for name in ("runtime_paths.py", "collectors/base.py"):
        assert (root / name).read_bytes() == (old / name).read_bytes()
    identity = load("verified_release", root / "release_identity.py").managed_release_identity(root)
    assert identity["code_oid"] == oid
    assert identity["identity_kind"] == "managed_release_manifest"
    producer = extract(ROOT / "bin/panorama/panorama-collect.py", {"resolve_projection_dashboard_code_root", "collect_projection_dashboard_identity"}, {"os": os, "Path": Path, "re": __import__("re")})
    actual = producer["collect_projection_dashboard_identity"](environ={"ZHIXING_DASHBOARD_CODE_ROOT": str(root)})
    assert actual == identity

    class Error(Exception):
        def __init__(self, status, public_error):
            self.status, self.public_error = status, public_error

    reader = extract(HOST / "live_server.py.asset", {"managed_dashboard_identity", "resolve_dashboard_code_identity", "probe_dashboard_code_identity"}, {"Path": Path, "CODE_ROOT": root, "ProjectionStateError": Error, "time": time})
    assert reader["resolve_dashboard_code_identity"](root) == actual
    assert reader["probe_dashboard_code_identity"](root) == {"code_oid": oid}
    before = (old / "live_server.py").read_bytes()
    assert zhs.restore()["ok"]
    assert zhs.CURRENT_LINK.resolve() == old
    assert (old / "live_server.py").read_bytes() == before


@pytest.mark.parametrize("damage", ["byte", "hash", "outside", "extra", "schema", "version", "symlink", "git"])
def test_invalid_managed_release_never_falls_back(release_env, damage):
    root = publish(release_env)
    helper = load("release_tamper_verifier", root / "release_identity.py")
    path = root / helper.MANIFEST
    payload = json.loads(path.read_text())
    if damage == "byte":
        (root / "runtime_paths.py").write_text("altered")
    elif damage == "hash":
        payload["files"]["runtime_paths.py"] = "0" * 64
    elif damage == "outside":
        payload["files"]["../outside.py"] = "0" * 64
    elif damage == "extra":
        (root / "extra.py").write_text("unexpected")
    elif damage == "schema":
        payload["schema"] = "wrong"
    elif damage == "version":
        payload["version_id"] = "0" * 40
    elif damage == "symlink":
        (root / "extra").symlink_to(root / "runtime_paths.py")
    elif damage == "git":
        (root / ".git").write_text("gitdir: /outside\n")
    path.write_text(json.dumps(payload))
    with pytest.raises(helper.ReleaseIdentityError):
        helper.managed_release_identity(root)
    producer = extract(ROOT / "bin/panorama/panorama-collect.py", {"resolve_projection_dashboard_code_root", "collect_projection_dashboard_identity"}, {"os": os, "Path": Path, "re": __import__("re")})
    with pytest.raises(RuntimeError, match="projection_release_identity_invalid"):
        producer["collect_projection_dashboard_identity"](environ={"ZHIXING_DASHBOARD_CODE_ROOT": str(root)})


def test_no_manifest_returns_legacy_only(tmp_path):
    helper = load("legacy_release_verifier", HOST / "release_identity.py.asset")
    assert helper.managed_release_identity(tmp_path) is None
    (tmp_path / helper.MANIFEST).write_text("not-json")
    with pytest.raises(helper.ReleaseIdentityError):
        helper.managed_release_identity(tmp_path)
