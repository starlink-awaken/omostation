"""发布器生产者字节绑定前置检查 (BET-Y2Q4-T10-365)。

采集器在宿主 refresh 作业里自带身份自校验: 正在执行的字节必须等于
PANORAMA_CODE_ROOT (code-main) HEAD 上的 bin/panorama/panorama-collect.py,
不等即抛 projection_collector_not_at_bound_commit 拒绝运行 ⇒ 投影停更 ⇒ 静态资源 503。
发布器此前只校验「发布字节 == 仓库资产字节」, 会发布一份必然让采集器拒绝运行的字节。
本文件钉住发布器那另一半: publish 在切换 current 之前必须先验这条绑定。
"""
import json
import os
import plistlib
import shutil
import subprocess
from pathlib import Path
import types

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "bin/panorama/assets/host"
COLLECTOR_ASSET = "panorama-collect-main.py.asset"
COLLECTOR_RELPATH = "bin/panorama/panorama-collect.py"


def load(name, path):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


def git_commit(root):
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=test",
         "-c", "user.email=test@example.invalid", "commit", "-qm", "source"],
        check=True,
    )
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


def make_producer_root(tmp_path, collector_bytes):
    """构造生产者代码根: HEAD 上的采集器字节 == collector_bytes。"""
    producer = tmp_path / "code-main"
    (producer / COLLECTOR_RELPATH).parent.mkdir(parents=True)
    (producer / COLLECTOR_RELPATH).write_bytes(collector_bytes)
    git_commit(producer)
    return producer


def write_refresh_plist(home, code_root):
    plist_dir = home / "Library" / "LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "Label": "com.omostation.panorama-dashboard-refresh",
        "EnvironmentVariables": {"PANORAMA_CODE_ROOT": str(code_root)},
        "ProgramArguments": ["/usr/bin/true"],
    }
    (plist_dir / "com.omostation.panorama-dashboard-refresh.plist").write_bytes(
        plistlib.dumps(payload)
    )


@pytest.fixture
def zhs_module():
    return load("zhixing_host_sync_binding", ROOT / "bin/gac/zhixing-host-sync.py")


def test_producer_root_prefers_refresh_plist(zhs_module, tmp_path, monkeypatch):
    home = tmp_path / "home"
    plist_root = tmp_path / "from-plist"
    env_root = tmp_path / "from-env"
    write_refresh_plist(home, plist_root)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PANORAMA_CODE_ROOT", str(env_root))
    assert zhs_module._producer_code_root() == plist_root


def test_producer_root_falls_back_to_env(zhs_module, tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    env_root = tmp_path / "from-env"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PANORAMA_CODE_ROOT", str(env_root))
    assert zhs_module._producer_code_root() == env_root


def test_binding_satisfied_when_bytes_match(zhs_module, tmp_path, monkeypatch):
    collector = b"# collector bytes\n"
    producer = make_producer_root(tmp_path, collector)
    release = tmp_path / "release"
    release.mkdir()
    (release / zhs_module.DEPLOYED_COLLECTOR_NAME).write_bytes(collector)
    monkeypatch.setattr(zhs_module, "_producer_code_root", lambda: producer)
    result = zhs_module.check_producer_binding(release)
    assert result["ok"] is True
    assert result["checked"] is True
    assert result["reason"] == "producer_binding_satisfied"


def test_binding_unsatisfied_reports_both_digests(zhs_module, tmp_path, monkeypatch):
    producer = make_producer_root(tmp_path, b"# producer collector\n")
    release = tmp_path / "release"
    release.mkdir()
    (release / zhs_module.DEPLOYED_COLLECTOR_NAME).write_bytes(b"# newer collector\n")
    monkeypatch.setattr(zhs_module, "_producer_code_root", lambda: producer)
    result = zhs_module.check_producer_binding(release)
    assert result["ok"] is False
    assert result["reason"] == "producer_binding_unsatisfied"
    assert result["release_sha256"] != result["bound_sha256"]
    assert "重锚" in result["detail"]


def test_binding_skipped_when_producer_root_missing(zhs_module, tmp_path, monkeypatch):
    release = tmp_path / "release"
    release.mkdir()
    (release / zhs_module.DEPLOYED_COLLECTOR_NAME).write_bytes(b"# collector\n")
    monkeypatch.setattr(zhs_module, "_producer_code_root", lambda: None)
    result = zhs_module.check_producer_binding(release)
    assert result["ok"] is True
    assert result["checked"] is False
    assert result["reason"] == "producer_root_unavailable"


def test_binding_skipped_when_producer_root_not_git(zhs_module, tmp_path, monkeypatch):
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    release = tmp_path / "release"
    release.mkdir()
    (release / zhs_module.DEPLOYED_COLLECTOR_NAME).write_bytes(b"# collector\n")
    monkeypatch.setattr(zhs_module, "_producer_code_root", lambda: plain)
    result = zhs_module.check_producer_binding(release)
    assert result["ok"] is True
    assert result["checked"] is False
    assert result["reason"] == "producer_binding_unverifiable"


def test_binding_skipped_when_release_has_no_collector(zhs_module, tmp_path, monkeypatch):
    release = tmp_path / "release"
    release.mkdir()
    monkeypatch.setattr(zhs_module, "_producer_code_root", lambda: tmp_path)
    result = zhs_module.check_producer_binding(release)
    assert result["ok"] is True
    assert result["checked"] is False
    assert result["reason"] == "collector_absent_in_release"


@pytest.fixture
def release_env(tmp_path, monkeypatch):
    """发布面夹具: 宿主资产仓 + 一个已发布 release + 生产者代码根。"""
    zhs = load("zhixing_host_sync_publish_binding", ROOT / "bin/gac/zhixing-host-sync.py")
    host, deploy = tmp_path / "source", tmp_path / "state"
    host.mkdir()
    deploy.mkdir()
    for name in ("live_server.py", "observatory_query.py"):
        shutil.copyfile(HOST / (name + ".asset"), host / (name + ".asset"))
    shutil.copyfile(HOST / COLLECTOR_ASSET, host / COLLECTOR_ASSET)
    oid = git_commit(host)
    baseline = deploy / "releases" / "baseline-placeholder"
    baseline.mkdir(parents=True)
    for name in ("live_server.py", "observatory_query.py"):
        shutil.copyfile(HOST / (name + ".asset"), baseline / name)
    shutil.copyfile(HOST / COLLECTOR_ASSET, baseline / zhs.DEPLOYED_COLLECTOR_NAME)
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
    monkeypatch.setattr(
        zhs, "_running_registered_runtime",
        lambda: {"ok": True, "entrypoint": str(zhs.CURRENT_ENTRYPOINT.resolve())},
    )
    return zhs, host, old, oid


def test_publish_refuses_when_binding_unsatisfied(release_env, tmp_path, monkeypatch):
    """接线钉子: 绑定不成立时 publish 必须拒绝, 且 current 不被切换。"""
    zhs, host, old, _ = release_env
    producer = make_producer_root(tmp_path, b"# producer collector bytes\n")
    monkeypatch.setattr(zhs, "_producer_code_root", lambda: producer)
    before = zhs._switch_state_snapshot()
    result = zhs.publish(["live_server.py", "observatory_query.py", "panorama-collect-main.py"])
    assert result["ok"] is False
    assert result["reason"] == "producer_binding_unsatisfied"
    assert zhs.CURRENT_LINK.resolve() == old
    assert zhs._switch_state_snapshot() == before
    published = [p.name for p in (zhs.RELEASES_DIR).iterdir() if p.is_dir()]
    assert published == [old.name], published


def test_publish_proceeds_when_binding_satisfied(release_env, tmp_path, monkeypatch):
    zhs, host, old, _ = release_env
    collector_bytes = (host / COLLECTOR_ASSET).read_bytes()
    producer = make_producer_root(tmp_path, collector_bytes)
    monkeypatch.setattr(zhs, "_producer_code_root", lambda: producer)
    result = zhs.publish(["live_server.py", "observatory_query.py", "panorama-collect-main.py"])
    assert result["ok"] is True, result
    root = zhs.CURRENT_LINK.resolve()
    assert root != old
    assert (root / zhs.DEPLOYED_COLLECTOR_NAME).read_bytes() == collector_bytes
