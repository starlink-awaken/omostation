"""迁移路径的运行期契约 (BET-Y2Q4-T10-367)。

migrate() 是第三个会切 `current` 的入口。 T10-366 把「切换后必须让运行中 live
server 重新绑定并验收收敛」补进了 publish() / restore(), 但迁移这一支仍然只做
「捕获部署态 → 建基线 → 切 current → 改 plist」; 更靠前一层, 迁移激活的基线
release 在运行期根本绑不了:

  * 基线清单的形态 (identity_kind=deployment_baseline, commit_oid=null) 被运行期
    身份 helper fail-closed 拒绝 (release_manifest_source_invalid);
  * 基线 release 里根本没有身份 helper —— 部署根里本来就没有这个文件。

本文件钉住两件事: ① 迁移基线必须**可被运行期独立验证并绑定** (内容寻址身份,
    摘要可从 release 字节重算); ② migrate() 必须走与 publish() 同一套运行期契约
    (比身份 / 协调不可用则拒绝 / 收敛验收 / 不收敛即回滚)。

装置纪律: launchd 动作一律换成记录型替身 —— 用例绝不允许真的 kick 本机服务;
/health 探针换成脚本化读数替身; 部署面与宿主面都在临时目录里。
"""
import json
import plistlib
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "bin/panorama/assets/host"
RELEASE_MANIFEST = ".zhixing-host-release.json"
RUNTIME_PID = 4242


def load(name: str, path: Path):
    module = SimpleNamespace()
    module.__dict__["__file__"] = str(path)
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


class LaunchdRecorder:
    """launchd 动作替身: 只记录, 绝不真的 kick 本机服务。"""

    def __init__(self, loaded: bool = True):
        self.calls: list[tuple] = []
        self._loaded = loaded

    def loaded_job(self, label: str) -> bool:
        self.calls.append(("loaded", label))
        return self._loaded

    def kickstart(self, label: str, *, kill: bool = False) -> dict:
        self.calls.append(("kickstart", label, kill))
        return {"ok": True, "label": label, "returncode": 0, "detail": None}

    def kickstarts(self) -> list[tuple]:
        return [call for call in self.calls if call[0] == "kickstart"]


class HealthStub:
    """/health 探针替身: 按调用序返回脚本化读数。"""

    def __init__(self, provider):
        self.provider = provider
        self.index = 0

    def __call__(self, port=43191):
        reading = self.provider(self.index)
        self.index += 1
        return reading


def legacy_reading():
    """旧代运行期: /health 报身份但指向旧 release (与候选不同)。"""
    return (200, {"pid": RUNTIME_PID, "dashboard_code_oid": "a" * 40,
                  "dashboard_tree_sha256": "b" * 64, "dashboard_code_sha256": "c" * 64,
                  "code_drift": False})


def unidentified_reading(pid=RUNTIME_PID):
    """旧代运行期: /health 不报告身份 (旧部署根没有 release_identity helper)。"""
    return (200, {"pid": pid})


def _plist(entrypoint: str) -> bytes:
    payload = {
        "Label": "com.omostation.zhixing-dashboard",
        "ProgramArguments": ["/opt/homebrew/bin/python3", "-B", entrypoint, "--port", "43191"],
        "RunAtLoad": True,
    }
    return plistlib.dumps(payload)


@pytest.fixture
def migrated(tmp_path, monkeypatch):
    """旧代部署面 + 宿主资产面 + 动作替身 (migrate() 的真实入口)。"""
    zhs = load("zhixing_host_sync_migrate", ROOT / "bin/gac/zhixing-host-sync.py")
    host, deploy = tmp_path / "host", tmp_path / "deploy"
    host.mkdir()
    deploy.mkdir()
    shutil.copyfile(HOST / "release_identity.py.asset", host / "release_identity.py.asset")
    for name in ("live_server.py", "observatory_query.py", "runtime_paths.py"):
        (deploy / name).write_text(f"# legacy deployed {name}\n")
    (deploy / "collectors").mkdir()
    (deploy / "collectors" / "base.py").write_text("# legacy collector base\n")
    plist = tmp_path / "com.omostation.zhixing-dashboard.plist"
    plist.write_bytes(_plist(str(deploy / "live_server.py")))
    monkeypatch.setattr(zhs, "HOST_DIR", host)
    monkeypatch.setattr(zhs, "DASHBOARD_DIR", deploy)
    monkeypatch.setattr(zhs, "RELEASES_DIR", deploy / "releases")
    monkeypatch.setattr(zhs, "CURRENT_LINK", deploy / "current")
    monkeypatch.setattr(zhs, "CURRENT_ENTRYPOINT", deploy / "current/live_server.py")
    monkeypatch.setattr(zhs, "LAUNCH_AGENT_PLIST", plist)
    monkeypatch.setattr(zhs, "RUNTIME_CONVERGENCE_TIMEOUT_SECONDS", 0)
    monkeypatch.setattr(zhs, "RUNTIME_CONVERGENCE_POLL_SECONDS", 0)
    monkeypatch.setattr(
        zhs, "_running_registered_runtime",
        lambda: {"ok": True, "pid": RUNTIME_PID,
                 "entrypoint": str(zhs.CURRENT_ENTRYPOINT)},
    )
    recorder = LaunchdRecorder()
    monkeypatch.setattr(zhs, "_launchd_job_loaded", recorder.loaded_job)
    monkeypatch.setattr(zhs, "_kickstart", recorder.kickstart)
    return SimpleNamespace(zhs=zhs, host=host, deploy=deploy, plist=plist,
                            launchd=recorder)


def baseline_of(migrated):
    return migrated.zhs.CURRENT_LINK.resolve()


def manifest_of(migrated):
    return json.loads((baseline_of(migrated) / RELEASE_MANIFEST).read_text())


def rebound_reading(migrated):
    """指针切换后运行期重新绑定: 报告当前 release 的真实身份三元组。"""
    release = baseline_of(migrated)
    helper = load("probe_identity", release / "release_identity.py")
    identity = helper.managed_release_identity(release)
    return (200, {"pid": RUNTIME_PID, "code_drift": False,
                  "dashboard_code_oid": identity["code_oid"],
                  "dashboard_tree_sha256": identity["tree_sha256"],
                  "dashboard_code_sha256": identity["code_bundle_sha256"]})


def restarting_provider(migrated):
    """切换前旧进程, 切换后新进程 (kickstart -k 的可观测效果)。"""
    zhs = migrated.zhs

    def provider(_index):
        restarted = zhs.CURRENT_LINK.is_symlink()
        return unidentified_reading(pid=RUNTIME_PID + 1 if restarted else RUNTIME_PID)

    return provider


def test_migration_baseline_is_bindable_by_runtime_identity(migrated, monkeypatch):
    """迁移基线必须能被运行期身份契约独立验证并绑定。"""
    zhs = migrated.zhs
    monkeypatch.setattr(zhs, "_runtime_health_probe",
                        HealthStub(restarting_provider(migrated)))
    result = zhs.migrate()
    assert result["ok"], result
    manifest = manifest_of(migrated)
    assert manifest["identity_kind"] == "deployment_baseline"
    assert manifest["commit_oid"] is None
    assert manifest["content_oid"] == manifest["version_id"]
    assert len(manifest["content_oid"]) == 40
    baseline = baseline_of(migrated)
    assert baseline.name == manifest["content_oid"]
    # 基线自带身份 helper —— 否则采集器与 live server 读不出这个 release 是谁。
    assert (baseline / "release_identity.py").is_file()
    helper = load("baseline_identity", baseline / "release_identity.py")
    identity = helper.managed_release_identity(baseline)
    assert identity["code_oid"] == manifest["content_oid"]
    assert len(identity["tree_sha256"]) == 64
    assert len(identity["code_bundle_sha256"]) == 64


def test_baseline_content_digest_is_recomputable_from_release_bytes(migrated, monkeypatch):
    """内容摘要必须能从 release 字节独立重算 —— 篡改字节即 fail-closed。"""
    zhs = migrated.zhs
    monkeypatch.setattr(zhs, "_runtime_health_probe",
                        HealthStub(restarting_provider(migrated)))
    assert zhs.migrate()["ok"]
    baseline = baseline_of(migrated)
    helper = load("baseline_tamper_verifier", baseline / "release_identity.py")
    (baseline / "live_server.py").write_text("# tampered legacy live_server\n")
    with pytest.raises(helper.ReleaseIdentityError):
        helper.managed_release_identity(baseline)


def test_baseline_manifest_content_oid_must_match_recomputed_digest(migrated, monkeypatch):
    """清单里的 content_oid 与字节不符 ⇒ 拒绝 (不得信清单自述)。"""
    zhs = migrated.zhs
    monkeypatch.setattr(zhs, "_runtime_health_probe",
                        HealthStub(restarting_provider(migrated)))
    assert zhs.migrate()["ok"]
    baseline = baseline_of(migrated)
    helper = load("baseline_oid_verifier", baseline / "release_identity.py")
    path = baseline / RELEASE_MANIFEST
    payload = json.loads(path.read_text())
    payload["content_oid"] = "d" * 40
    path.write_text(json.dumps(payload))
    with pytest.raises(helper.ReleaseIdentityError):
        helper.managed_release_identity(baseline)


def test_publisher_and_runtime_reject_bare_baseline_manifest_equally(migrated, monkeypatch):
    """旧形态裸基线清单 (无 content_oid): 发布器与运行期**都**拒绝。"""
    zhs = migrated.zhs
    monkeypatch.setattr(zhs, "_runtime_health_probe",
                        HealthStub(restarting_provider(migrated)))
    assert zhs.migrate()["ok"]
    baseline = baseline_of(migrated)
    helper = load("bare_baseline_verifier", baseline / "release_identity.py")
    path = baseline / RELEASE_MANIFEST
    payload = json.loads(path.read_text())
    payload.pop("content_oid")
    path.write_text(json.dumps(payload))
    with pytest.raises(helper.ReleaseIdentityError):
        helper.managed_release_identity(baseline)
    # 发布器侧: 同一份清单不得被 _base_manifest_valid 认可。
    assert zhs._base_manifest_valid(baseline) is False


def test_migrate_refuses_when_coordination_unavailable(migrated, monkeypatch):
    """绑定将被破坏且协调通道不可用 ⇒ 拒绝迁移, 指针与 plist 均不变。"""
    zhs = migrated.zhs
    monkeypatch.setattr(zhs, "_runtime_health_probe", HealthStub(lambda _i: legacy_reading()))
    monkeypatch.setattr(zhs, "_runtime_coordination_available", lambda: False)
    before = zhs._switch_state_snapshot()
    result = zhs.migrate()
    assert result["ok"] is False
    assert result["reason"] == "runtime_coordination_unavailable"
    assert zhs._switch_state_snapshot() == before
    assert not zhs.CURRENT_LINK.is_symlink()
    assert migrated.launchd.kickstarts() == []
    assert migrated.plist.read_bytes() == _plist(str(migrated.deploy / "live_server.py"))


def test_migrate_converges_and_reports_runtime_readings(migrated, monkeypatch):
    """切换后收敛运行期并把读数写进返回值。"""

    def provider(_index):
        if migrated.zhs.CURRENT_LINK.is_symlink():
            return rebound_reading(migrated)
        return unidentified_reading()

    zhs = migrated.zhs
    monkeypatch.setattr(zhs, "_runtime_health_probe", HealthStub(provider))
    result = zhs.migrate()
    assert result["ok"], result
    assert result["runtime"]["converged"] is True
    assert result["runtime"]["criterion"] == "identity_bound"
    assert result["runtime"]["coordinated"] is True
    assert result["runtime"]["identity"]["code_oid"] == manifest_of(migrated)["content_oid"]
    kicks = migrated.launchd.kickstarts()
    assert ("kickstart", zhs.REFRESH_LAUNCH_AGENT_LABEL, False) in kicks
    assert ("kickstart", zhs.LAUNCH_AGENT_LABEL, True) in kicks


def test_migrate_labels_degraded_criterion_when_runtime_unidentified(migrated, monkeypatch):
    """旧代运行期不报告身份 ⇒ 判据降级为「服务可用 + 进程已重启」且显式标注。"""
    zhs = migrated.zhs

    def provider(_index):
        if zhs.CURRENT_LINK.is_symlink():
            return unidentified_reading(pid=RUNTIME_PID + 1)
        return unidentified_reading()

    monkeypatch.setattr(zhs, "_runtime_health_probe", HealthStub(provider))
    result = zhs.migrate()
    assert result["ok"], result
    assert result["runtime"]["converged"] is True
    assert result["runtime"]["criterion"] == "service_available_only"


def test_degraded_criterion_rejects_a_server_that_never_restarted(migrated, monkeypatch):
    """重启没生效 (pid 未变) ⇒ 旧进程仍在服务 ⇒ 降级判据不得放行。"""
    zhs = migrated.zhs
    monkeypatch.setattr(zhs, "_runtime_health_probe",
                        HealthStub(lambda _i: unidentified_reading()))
    before = zhs._switch_state_snapshot()
    result = zhs.migrate()
    assert result["ok"] is False
    assert result["reason"] == "runtime_convergence_failed"
    assert zhs._switch_state_snapshot() == before
    assert not zhs.CURRENT_LINK.is_symlink()


def test_migrate_rolls_back_when_convergence_fails(migrated, monkeypatch):
    """不收敛 ⇒ ok=false / runtime_convergence_failed, plist 与 current 复原。"""
    zhs = migrated.zhs
    monkeypatch.setattr(zhs, "_runtime_health_probe",
                        HealthStub(lambda _i: (503, {"pid": RUNTIME_PID})))
    before = zhs._switch_state_snapshot()
    result = zhs.migrate()
    assert result["ok"] is False
    assert result["reason"] == "runtime_convergence_failed"
    assert result["runtime"]["converged"] is False
    assert zhs._switch_state_snapshot() == before
    assert not zhs.CURRENT_LINK.is_symlink()
    assert migrated.plist.read_bytes() == _plist(str(migrated.deploy / "live_server.py"))


def test_migrate_refuses_when_identity_helper_asset_missing(migrated, monkeypatch):
    """仓库侧缺身份 helper 资产 ⇒ 迁移拒绝并给出可执行原因。"""
    zhs = migrated.zhs
    (migrated.host / "release_identity.py.asset").unlink()
    monkeypatch.setattr(zhs, "_runtime_health_probe",
                        HealthStub(lambda _i: unidentified_reading()))
    before = zhs._switch_state_snapshot()
    result = zhs.migrate()
    assert result["ok"] is False
    assert result["reason"] == "baseline_identity_helper_missing"
    assert zhs._switch_state_snapshot() == before
    assert not zhs.CURRENT_LINK.is_symlink()


def test_migrate_is_idempotent_on_a_bound_release(migrated, monkeypatch):
    """已迁移且 current 可绑定 ⇒ already_migrated, 不重建基线。"""
    zhs = migrated.zhs
    monkeypatch.setattr(zhs, "_runtime_health_probe",
                        HealthStub(restarting_provider(migrated)))
    assert zhs.migrate()["ok"]
    baseline = baseline_of(migrated)
    kicks_before = len(migrated.launchd.kickstarts())
    again = zhs.migrate()
    assert again["ok"] is True
    assert again["already_migrated"] is True
    assert baseline_of(migrated) == baseline
    assert len(migrated.launchd.kickstarts()) == kicks_before
