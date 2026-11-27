"""发布器运行期收敛 (BET-Y2Q4-T10-366)。

live server 的身份自校验把「正在执行的 release」钉死在 import 时解析出的
CODE_ROOT (runtime_paths.py.asset), 投影 revision 的绑定却来自采集器当时看到的
`current` 软链 ⇒ 每次发布换 release oid, 运行中的 server 必然与新 revision 不等
⇒ CODE_DRIFT ⇒ 静态资源 503, 而 publish 仍返回 ok:true (T10-364 回执 §5 实测:
发布后宿主进入只读态, 直到人工重启才恢复)。

本文件钉住发布器那另一半: publish 必须在切换 current 之前比两侧身份; 绑定将被
破坏时必须由发布器重绑定运行期并验收收敛; 不收敛即回滚。

装置纪律: launchd 动作 (_launchd_job_loaded / _kickstart) 一律换成记录型替身 ——
用例绝不允许真的 kick 本机服务; /health 探针换成脚本化读数替身。
"""
import shutil
import subprocess
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "bin/panorama/assets/host"
COLLECTOR_ASSET = "panorama-collect-main.py.asset"
COLLECTOR_RELPATH = "bin/panorama/panorama-collect.py"
RUNTIME_PID = 4242
OLD_TREE_SHA = "a" * 64
OLD_BUNDLE_SHA = "b" * 64
ASSETS = ["live_server.py", "observatory_query.py", "panorama-collect-main.py"]
REFRESH_LABEL = "com.omostation.panorama-dashboard-refresh"
DASHBOARD_LABEL = "com.omostation.zhixing-dashboard"


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
    """生产者代码根: HEAD 上的采集器字节 == collector_bytes。"""
    producer = tmp_path / "code-main"
    (producer / COLLECTOR_RELPATH).parent.mkdir(parents=True)
    (producer / COLLECTOR_RELPATH).write_bytes(collector_bytes)
    git_commit(producer)
    return producer


class LaunchdRecorder:
    """launchd 动作替身: 只记录, 绝不真的 kick 本机服务。"""

    def __init__(self):
        self.calls: list[tuple] = []

    def loaded_job(self, label):
        self.calls.append(("loaded", label))
        return True

    def kickstart(self, label, *, kill=False):
        self.calls.append(("kickstart", label, kill))
        return {"ok": True, "label": label, "returncode": 0, "detail": None}

    def kickstarts(self) -> list[tuple]:
        return [call for call in self.calls if call[0] == "kickstart"]


class HealthStub:
    """/health 探针替身: 按调用序返回脚本化读数 (最后一个读数可重复)。"""

    def __init__(self, provider):
        self.provider = provider
        self.index = 0

    def __call__(self, port=43191):
        reading = self.provider(self.index)
        self.index += 1
        return reading


def server_reading(oid, tree_sha, bundle_sha, *, drift=False):
    return (200, {"pid": RUNTIME_PID, "code_drift": drift,
                  "dashboard_code_oid": oid,
                  "dashboard_tree_sha256": tree_sha,
                  "dashboard_code_sha256": bundle_sha})


@pytest.fixture
def publisher(tmp_path, monkeypatch):
    """发布面夹具: 宿主资产仓 + 一个已发布 release + 生产者代码根 + 动作替身。"""
    zhs = load("zhixing_host_sync_convergence", ROOT / "bin/gac/zhixing-host-sync.py")
    host, deploy = tmp_path / "source", tmp_path / "state"
    host.mkdir()
    deploy.mkdir()
    for name in ("live_server.py", "observatory_query.py"):
        shutil.copyfile(HOST / (name + ".asset"), host / (name + ".asset"))
    shutil.copyfile(HOST / "release_identity.py.asset", host / "release_identity.py.asset")
    shutil.copyfile(HOST / COLLECTOR_ASSET, host / COLLECTOR_ASSET)
    oid = git_commit(host)
    baseline = deploy / "releases" / "baseline-placeholder"
    baseline.mkdir(parents=True)
    for name in ("live_server.py", "observatory_query.py"):
        shutil.copyfile(HOST / (name + ".asset"), baseline / name)
    shutil.copyfile(HOST / "release_identity.py.asset", baseline / "release_identity.py")
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
        lambda: {"ok": True, "entrypoint": str(zhs.CURRENT_ENTRYPOINT.resolve()),
                 "pid": RUNTIME_PID},
    )
    producer = make_producer_root(tmp_path, (host / COLLECTOR_ASSET).read_bytes())
    monkeypatch.setattr(zhs, "_producer_code_root", lambda: producer)
    monkeypatch.setattr(zhs, "RUNTIME_CONVERGENCE_TIMEOUT_SECONDS", 0)
    monkeypatch.setattr(zhs, "RUNTIME_CONVERGENCE_POLL_SECONDS", 0)
    recorder = LaunchdRecorder()
    monkeypatch.setattr(zhs, "_launchd_job_loaded", recorder.loaded_job)
    monkeypatch.setattr(zhs, "_kickstart", recorder.kickstart)
    return SimpleNamespace(zhs=zhs, host=host, old=old, oid=oid, launchd=recorder,
                            candidate=zhs.RELEASES_DIR / oid)


def candidate_identity(publisher):
    identity = publisher.zhs.release_identity_of(publisher.candidate)
    assert identity["ok"] is True, identity
    return identity


def test_runtime_identity_preserved_skips_coordination(publisher, monkeypatch):
    """绑定保持 ⇒ 不触发任何 kickstart, 也不做收敛等待。"""
    zhs = publisher.zhs

    def provider(_index):
        identity = candidate_identity(publisher)
        return server_reading(identity["code_oid"], identity["tree_sha256"],
                              identity["code_bundle_sha256"])

    monkeypatch.setattr(zhs, "_runtime_health_probe", HealthStub(provider))
    result = zhs.publish(ASSETS)
    assert result["ok"] is True, result
    assert result["runtime"]["reason"] == "runtime_identity_preserved"
    assert result["runtime"]["coordinated"] is False
    assert publisher.launchd.kickstarts() == []
    assert zhs.CURRENT_LINK.resolve() == publisher.candidate


def test_runtime_identity_will_break_triggers_convergence(publisher, monkeypatch):
    """绑定将被破坏 ⇒ 协调 (刷新采集器 + 重启服务) 并验收收敛。"""
    zhs = publisher.zhs

    def provider(index):
        if index == 0:
            return server_reading(publisher.old.name, OLD_TREE_SHA, OLD_BUNDLE_SHA)
        identity = candidate_identity(publisher)
        return server_reading(identity["code_oid"], identity["tree_sha256"],
                              identity["code_bundle_sha256"])

    monkeypatch.setattr(zhs, "_runtime_health_probe", HealthStub(provider))
    result = zhs.publish(ASSETS)
    assert result["ok"] is True, result
    assert result["runtime"]["reason"] == "runtime_identity_will_break"
    assert result["runtime"]["coordinated"] is True
    assert result["runtime"]["converged"] is True
    kicks = publisher.launchd.kickstarts()
    assert ("kickstart", REFRESH_LABEL, False) in kicks
    assert ("kickstart", DASHBOARD_LABEL, True) in kicks
    assert zhs.CURRENT_LINK.resolve() == publisher.candidate


def test_runtime_convergence_failure_rolls_back(publisher, monkeypatch):
    """不收敛 ⇒ ok=false / runtime_convergence_failed, 且 current 切回上一版。"""
    zhs = publisher.zhs

    def provider(_index):
        return server_reading(publisher.old.name, OLD_TREE_SHA, OLD_BUNDLE_SHA, drift=True)

    monkeypatch.setattr(zhs, "_runtime_health_probe", HealthStub(provider))
    result = zhs.publish(ASSETS)
    assert result["ok"] is False
    assert result["reason"] == "runtime_convergence_failed"
    assert result["runtime"]["converged"] is False
    assert zhs.CURRENT_LINK.resolve() == publisher.old
    assert not publisher.candidate.exists()


def test_unobservable_runtime_does_not_block_publish(publisher, monkeypatch):
    """探不到运行实例 ⇒ 跳过判定, 不阻断发布, 不做协调。"""
    zhs = publisher.zhs
    monkeypatch.setattr(zhs, "_runtime_health_probe", lambda port=43191: (None, {}))
    result = zhs.publish(ASSETS)
    assert result["ok"] is True, result
    assert result["runtime"]["checked"] is False
    assert result["runtime"]["reason"] == "runtime_unreachable"
    assert publisher.launchd.kickstarts() == []
    assert zhs.CURRENT_LINK.resolve() == publisher.candidate


def test_unverifiable_runtime_pid_does_not_block_publish(publisher, monkeypatch):
    """pid 不可验证 ⇒ 跳过判定, 不阻断发布 (无法自证时不得反手阻断)。"""
    zhs = publisher.zhs
    monkeypatch.setattr(
        zhs, "_running_registered_runtime",
        lambda: {"ok": True, "entrypoint": str(zhs.CURRENT_ENTRYPOINT.resolve())},
    )
    monkeypatch.setattr(zhs, "_runtime_health_probe",
                        lambda port=43191: server_reading(publisher.old.name, OLD_TREE_SHA,
                                                          OLD_BUNDLE_SHA))
    result = zhs.publish(ASSETS)
    assert result["ok"] is True, result
    assert result["runtime"]["reason"] == "runtime_pid_unverified"
    assert publisher.launchd.kickstarts() == []


def test_publish_refuses_when_coordination_unavailable(publisher, monkeypatch):
    """协调不可用 ⇒ 拒绝发布, current 不切换, 新版本目录不残留。"""
    zhs = publisher.zhs

    def provider(_index):
        return server_reading(publisher.old.name, OLD_TREE_SHA, OLD_BUNDLE_SHA)

    monkeypatch.setattr(zhs, "_runtime_health_probe", HealthStub(provider))
    monkeypatch.setattr(zhs, "_runtime_coordination_available", lambda: False)
    result = zhs.publish(ASSETS)
    assert result["ok"] is False
    assert result["reason"] == "runtime_coordination_unavailable"
    assert result["write_performed"] is False
    assert zhs.CURRENT_LINK.resolve() == publisher.old
    assert not publisher.candidate.exists()
    assert publisher.launchd.kickstarts() == []


def test_release_identity_of_reads_candidate_manifest(publisher, monkeypatch):
    """候选 release 的身份来自它自己的 manifest (真实读数, 不靠桩)。"""
    zhs = publisher.zhs
    monkeypatch.setattr(zhs, "_runtime_health_probe", lambda port=43191: (None, {}))
    assert zhs.publish(ASSETS)["ok"] is True
    identity = zhs.release_identity_of(publisher.candidate)
    assert identity["ok"] is True
    assert identity["code_oid"] == publisher.oid
    assert len(identity["tree_sha256"]) == 64
    assert len(identity["code_bundle_sha256"]) == 64


def test_restore_coordinates_when_binding_will_break(publisher, monkeypatch):
    """restore() 同样走收敛 —— 回滚不得把宿主留在只读态。"""
    zhs = publisher.zhs
    real_identity_of = zhs.release_identity_of
    rolled_back_identity = {"ok": True, "code_oid": "f" * 40,
                            "tree_sha256": "1" * 64, "code_bundle_sha256": "2" * 64}

    def identity_of(root):
        if Path(root).name == publisher.old.name:
            return dict(rolled_back_identity)
        return real_identity_of(root)

    def provider(index):
        identity = candidate_identity(publisher)
        if index <= 1:
            # 发布期探针: 运行中 server 就是候选 release (绑定保持, 不协调);
            # 回滚期探针: server 仍跑着刚发布的那一版 (与回滚目标不同 ⇒ 绑定将被破坏)。
            return server_reading(identity["code_oid"], identity["tree_sha256"],
                                  identity["code_bundle_sha256"])
        return server_reading(rolled_back_identity["code_oid"],
                              rolled_back_identity["tree_sha256"],
                              rolled_back_identity["code_bundle_sha256"])

    monkeypatch.setattr(zhs, "release_identity_of", identity_of)
    monkeypatch.setattr(zhs, "_runtime_health_probe", HealthStub(provider))
    assert zhs.publish(ASSETS)["ok"] is True
    assert zhs.CURRENT_LINK.resolve() == publisher.candidate

    result = zhs.restore()
    assert result["ok"] is True, result
    assert result["restored_version"] == publisher.old.name
    assert result["runtime"]["reason"] == "runtime_identity_will_break"
    assert result["runtime"]["converged"] is True
    assert zhs.CURRENT_LINK.resolve() == publisher.old
    kicks = publisher.launchd.kickstarts()
    assert ("kickstart", DASHBOARD_LABEL, True) in kicks
