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


def publish(release_env, *, publication_id=None):
    zhs, _, _, _ = release_env
    result = zhs.publish(["live_server.py", "observatory_query.py", "release_identity.py"],
                         publication_id=publication_id)
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
@pytest.mark.parametrize("publication_id", [None, "9" * 32])
def test_invalid_managed_release_never_falls_back(release_env, damage, publication_id):
    root = publish(release_env, publication_id=publication_id)
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


def test_same_commit_explicit_publications_and_native_restore(release_env):
    zhs, _, old, oid = release_env
    (old / "observatory_query.py").write_text("# healthy retained older query\n")
    initial = zhs.publish(["live_server.py", "release_identity.py"])
    assert initial["ok"], initial
    legacy = zhs.CURRENT_LINK.resolve()
    legacy_bytes = {p.relative_to(legacy).as_posix(): p.read_bytes()
                    for p in legacy.rglob("*") if p.is_file()}
    selected = ["live_server.py", "release_identity.py"]
    first = zhs.publish(selected, publication_id="a" * 32)
    assert first["ok"], first
    root = zhs.CURRENT_LINK.resolve()
    assert root.name == oid + "--pub-" + "a" * 32
    assert first["commit_oid"] == first["oid"] == oid
    assert first["version_id"] == root.name
    manifest = json.loads((root / zhs.RELEASE_MANIFEST).read_text())
    assert manifest["schema"] == "zhixing-host-release-manifest/v2"
    assert manifest["selected_assets"] == selected
    assert manifest["base_version"] == legacy.name
    assert manifest["publication_id"] == "a" * 32
    identity = load("v2_identity", root / "release_identity.py").managed_release_identity(root)
    assert identity["code_oid"] == oid
    before = (root / zhs.RELEASE_MANIFEST).read_bytes()
    repeated = zhs.publish(selected, publication_id="a" * 32)
    assert repeated["ok"], repeated
    assert (root / zhs.RELEASE_MANIFEST).read_bytes() == before
    assert zhs.restore()["ok"]
    assert zhs.CURRENT_LINK.resolve() == legacy
    assert zhs.restore()["ok"]
    assert zhs.CURRENT_LINK.resolve() == root
    second = zhs.publish(["observatory_query.py"], publication_id="b" * 32)
    assert second["ok"], second
    second_identity = load("second_identity", zhs.CURRENT_LINK / "release_identity.py").managed_release_identity(zhs.CURRENT_LINK)
    assert second_identity["code_oid"] == oid
    assert second_identity["tree_sha256"] != identity["tree_sha256"]
    assert (root / "observatory_query.py").read_bytes() == (old / "observatory_query.py").read_bytes()
    assert zhs.CURRENT_LINK.resolve().name == oid + "--pub-" + "b" * 32
    for name in ("runtime_paths.py", "collectors/base.py"):
        assert (zhs.CURRENT_LINK / name).read_bytes() == (old / name).read_bytes()
    assert zhs.restore()["ok"]
    assert zhs.CURRENT_LINK.resolve() == root
    assert zhs.restore()["ok"]
    # Native history records the actual previous target, so restore toggles.
    assert zhs.CURRENT_LINK.resolve().name == second["version_id"]
    assert {p.relative_to(legacy).as_posix(): p.read_bytes()
            for p in legacy.rglob("*") if p.is_file()} == legacy_bytes
    assert zhs.publish(["observatory_query.py"])["reason"] == "version_identity_conflict"


@pytest.mark.parametrize("token", ["", "../outside", "A" * 32, "a" * 31, "a" * 33])
def test_publication_token_rejected_without_switch(release_env, token):
    zhs, _, old, _ = release_env
    before = zhs._switch_state_snapshot()
    result = zhs.publish(["live_server.py"], publication_id=token)
    assert not result["ok"]
    assert zhs._switch_state_snapshot() == before
    assert zhs.CURRENT_LINK.resolve() == old


def test_v2_requires_explicit_compatible_staged_helper(release_env):
    zhs, _, old, _ = release_env
    before = zhs._switch_state_snapshot()
    result = zhs.publish(["live_server.py"], publication_id="c" * 32)
    assert result["reason"] == "publication_identity_helper_incompatible"
    assert "release_identity.py" in result["detail"]
    assert zhs._switch_state_snapshot() == before
    assert zhs.CURRENT_LINK.resolve() == old
    assert zhs.publish(["live_server.py", "release_identity.py"], publication_id="c" * 32)["ok"]


@pytest.mark.parametrize("damage", ["bytes", "manifest", "extra"])
def test_corrupt_base_is_not_remanifested(release_env, damage):
    zhs, _, _, _ = release_env
    root = publish(release_env)
    if damage == "bytes":
        (root / "runtime_paths.py").write_text("corrupted")
    elif damage == "manifest":
        (root / zhs.RELEASE_MANIFEST).write_text("not-json")
    else:
        (root / "unexpected.py").write_text("corrupted")
    before = zhs._switch_state_snapshot()
    result = zhs.publish(["live_server.py", "release_identity.py"], publication_id="d" * 32)
    assert result["reason"] == "current_release_integrity_invalid"
    assert zhs._switch_state_snapshot() == before


def test_v2_producer_reader_and_driver_roots(release_env):
    zhs, _, _, oid = release_env
    assert zhs.publish(["live_server.py", "release_identity.py"], publication_id="e" * 32)["ok"]
    root = zhs.CURRENT_LINK.resolve()
    producer = extract(ROOT / "bin/panorama/panorama-collect.py",
                       {"resolve_projection_dashboard_code_root", "collect_projection_dashboard_identity"},
                       {"os": os, "Path": Path, "re": __import__("re")})
    actual = producer["collect_projection_dashboard_identity"](
        environ={"ZHIXING_DASHBOARD_CODE_ROOT": str(zhs.DASHBOARD_DIR)})
    assert actual["code_oid"] == oid
    assert producer["resolve_projection_dashboard_code_root"](
        {"ZHIXING_DASHBOARD_CODE_ROOT": str(root)}) == root
    driver = extract(ROOT / "bin/panorama/projection-full-refresh.py",
                     {"resolve_dashboard_release_root"}, {"Path": Path, "re": __import__("re")})
    assert driver["resolve_dashboard_release_root"](zhs.DASHBOARD_DIR) == root

    class Error(Exception):
        pass

    reader = extract(HOST / "live_server.py.asset",
                     {"managed_dashboard_identity", "resolve_dashboard_code_identity", "probe_dashboard_code_identity"},
                     {"Path": Path, "CODE_ROOT": root, "ProjectionStateError": Error, "time": time})
    assert reader["resolve_dashboard_code_identity"](root) == actual
    assert reader["probe_dashboard_code_identity"](root) == {"code_oid": oid}


def test_v2_dirty_source_and_token_reuse_fail_without_switch(release_env):
    zhs, host, _, _ = release_env
    selected = ["live_server.py", "release_identity.py"]
    assert zhs.publish(selected, publication_id="f" * 32)["ok"]
    before = zhs._switch_state_snapshot()
    assert zhs.publish(["observatory_query.py"], publication_id="f" * 32)["reason"] == "version_identity_conflict"
    assert zhs._switch_state_snapshot() == before
    (host / "live_server.py.asset").write_text("dirty source")
    assert zhs.publish(selected, publication_id="0" * 32)["reason"] == "source_git_commit_required"
    assert zhs._switch_state_snapshot() == before


def test_v2_selected_set_reordering_is_idempotent(release_env):
    zhs, _, old, oid = release_env
    selected = ["release_identity.py", "live_server.py"]
    first = zhs.publish(selected, publication_id="7" * 32)
    assert first["ok"], first
    root = zhs.CURRENT_LINK.resolve()
    before = zhs._switch_state_snapshot()
    manifest_before = (root / zhs.RELEASE_MANIFEST).read_bytes()
    replay = zhs.publish(list(reversed(selected)), publication_id="7" * 32)
    assert replay["ok"], replay
    assert replay["commit_oid"] == first["commit_oid"] == oid
    assert replay["version_id"] == first["version_id"]
    assert zhs._switch_state_snapshot() == before
    assert (root / zhs.RELEASE_MANIFEST).read_bytes() == manifest_before
    manifest = json.loads(manifest_before)
    assert manifest["selected_assets"] == sorted(selected)
    assert manifest["base_version"] == old.name


def test_legacy_asset_order_keeps_existing_conflict_behavior(release_env):
    zhs, _, _, _ = release_env
    selected = ["release_identity.py", "live_server.py"]
    first = zhs.publish(selected)
    assert first["ok"], first
    root = zhs.CURRENT_LINK.resolve()
    before = zhs._switch_state_snapshot()
    manifest_before = (root / zhs.RELEASE_MANIFEST).read_bytes()
    replay = zhs.publish(list(reversed(selected)))
    assert replay["reason"] == "version_identity_conflict"
    assert zhs._switch_state_snapshot() == before
    assert (root / zhs.RELEASE_MANIFEST).read_bytes() == manifest_before
    assert json.loads(manifest_before)["selected_assets"] == selected


def test_actual_legacy_helper_rejects_v2_without_implicit_overlay(release_env):
    zhs, _, old, _ = release_env
    (old / "release_identity.py").write_text(
        "def managed_release_identity(root):\n"
        "    raise ValueError('legacy helper only accepts v1')\n")
    before = zhs._switch_state_snapshot()
    result = zhs.publish(["live_server.py"], publication_id="4" * 32)
    assert result["reason"] == "publication_identity_helper_incompatible"
    assert zhs._switch_state_snapshot() == before
    assert (old / "release_identity.py").read_text().endswith("only accepts v1')\n")


def test_v2_post_switch_failure_restores_exact_history(release_env, monkeypatch):
    zhs, _, _, _ = release_env
    publish(release_env)
    before = zhs._switch_state_snapshot()
    monkeypatch.setattr(zhs, "_asset_plan", lambda *args: {"ok": False})
    result = zhs.publish(["live_server.py", "release_identity.py"], publication_id="5" * 32)
    assert result["reason"] == "deploy_verify_failed"
    assert result["recovery"]["ok"]
    assert zhs._switch_state_snapshot() == before
    assert not (zhs.RELEASES_DIR / (release_env[3] + "--pub-" + "5" * 32)).exists()


def test_runtime_bytecode_does_not_invalidate_release(release_env):
    """Bytecode regenerated in place by the refresh jobs must not break identity.

    Regression: the orchestrator runs with cwd=<release> and rewrites __pycache__,
    which used to flip the manifest tree hash and make the service refuse to start.
    """
    zhs, _, _, oid = release_env
    root = publish(release_env)
    cache = root / "__pycache__"
    cache.mkdir()
    (cache / "refresh.cpython-315.pyc").write_bytes(b"\x00regenerated")
    (root / "stray.pyc").write_bytes(b"\x00stray")
    identity = load("bytecode_tolerant_verifier", root / "release_identity.py").managed_release_identity(root)
    assert identity["code_oid"] == oid
    hashed = zhs._release_tree_files(root)
    assert hashed is not None
    assert not [name for name in hashed if name.endswith(".pyc")]
    assert not [name for name in hashed if name.startswith("__pycache__/")]
    manifest = json.loads((root / zhs.RELEASE_MANIFEST).read_text())
    assert not [name for name in manifest["files"] if name.endswith(".pyc")]


def test_publish_drops_base_runtime_bytecode(release_env):
    zhs, _, old, oid = release_env
    cache = old / "__pycache__"
    cache.mkdir()
    (cache / "base.cpython-315.pyc").write_bytes(b"\x00bytecode")
    (old / "stray.pyc").write_bytes(b"\x00stray")
    root = publish(release_env)
    assert root.name == oid
    assert not (root / "__pycache__").exists()
    assert not list(root.rglob("*.pyc"))
    assert load("bytecode_free_identity", root / "release_identity.py").managed_release_identity(root)["code_oid"] == oid


@pytest.mark.parametrize("bad_name", ["bad", "0" * 40 + "--pub-" + "A" * 32, "../outside"])
def test_both_root_consumers_reject_invalid_publication_targets(release_env, tmp_path, bad_name):
    zhs, _, _, _ = release_env
    producer = extract(ROOT / "bin/panorama/panorama-collect.py",
                       {"resolve_projection_dashboard_code_root"},
                       {"os": os, "Path": Path, "re": __import__("re")})
    driver = extract(ROOT / "bin/panorama/projection-full-refresh.py",
                     {"resolve_dashboard_release_root"}, {"Path": Path, "re": __import__("re")})
    target = (zhs.RELEASES_DIR / bad_name).resolve()
    target.mkdir(parents=True, exist_ok=True)
    zhs.CURRENT_LINK.unlink()
    zhs.CURRENT_LINK.symlink_to(target)
    with pytest.raises(RuntimeError, match="release_invalid"):
        producer["resolve_projection_dashboard_code_root"]({"ZHIXING_DASHBOARD_CODE_ROOT": str(zhs.DASHBOARD_DIR)})
    with pytest.raises(ValueError, match="release_invalid"):
        driver["resolve_dashboard_release_root"](zhs.DASHBOARD_DIR)
