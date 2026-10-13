"""Zhixing host-sync 发布机制 hermetic 测试 (DCP-20 spec v1.1.0 验收)。

所有测试使用 temp dir + 私有 resolver seam, **不触碰真实 LaunchAgent plist、
部署目录、43191 端口或任何生产文件**。
"""
from __future__ import annotations

import importlib.util
import plistlib
import subprocess
from pathlib import Path

import pytest

_ZHS_FILE = Path(__file__).resolve().parents[1] / "bin" / "gac" / "zhixing-host-sync.py"
_SPEC = importlib.util.spec_from_file_location("zhs", str(_ZHS_FILE))
zhs = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(zhs)


@pytest.fixture
def zhs_env(tmp_path, monkeypatch):
    host = tmp_path / "host"
    host.mkdir()
    deploy = tmp_path / "deploy"
    deploy.mkdir()
    plist = tmp_path / "com.omostation.zhixing-dashboard.plist"
    monkeypatch.setattr(zhs, "HOST_DIR", host)
    monkeypatch.setattr(zhs, "DASHBOARD_DIR", deploy)
    monkeypatch.setattr(zhs, "LAUNCH_AGENT_PLIST", plist)
    monkeypatch.setattr(zhs, "CURRENT_LINK", deploy / "current")
    monkeypatch.setattr(zhs, "RELEASES_DIR", deploy / "releases")
    monkeypatch.setattr(zhs, "CURRENT_ENTRYPOINT", deploy / "current" / "live_server.py")
    return {"host": host, "deploy": deploy, "plist": plist}


def _write_plist(path: Path, entrypoint: str) -> None:
    payload = {
        "Label": zhs.LAUNCH_AGENT_LABEL,
        "ProgramArguments": ["/opt/homebrew/bin/python3", "-B", entrypoint, "--port", "43191"],
        "RunAtLoad": True,
    }
    path.write_bytes(plistlib.dumps(payload))


def _git_baseline(deploy: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=deploy, check=True)
    subprocess.run(["git", "-C", str(deploy), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(deploy), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "baseline"], check=True)


def _fake_runtime(runtime_root: Path) -> dict:
    entry = zhs.CURRENT_ENTRYPOINT.resolve()
    return {
        "ok": True, "label": zhs.LAUNCH_AGENT_LABEL,
        "plist": str(zhs.LAUNCH_AGENT_PLIST),
        "runtime_root": str(entry.parent), "entrypoint": str(entry),
    }


def test_prepare_version_sha_alignment(zhs_env):
    host = zhs_env["host"]
    (host / "live_server.py.asset").write_text("fixed live_server\n")
    _git_baseline(host)
    oid = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=host, text=True).strip()
    result = zhs._prepare_version((("live_server.py", "live_server.py.asset"),), oid)
    assert result["ok"], result
    version_dir = Path(result["version_dir"])
    assert version_dir.is_dir()
    assert (version_dir / "live_server.py").read_text() == "fixed live_server\n"
    for item in version_dir.rglob("*"):
        assert not item.is_symlink(), f"version dir has internal symlink: {item}"


def test_switch_current_atomic(zhs_env):
    deploy = zhs_env["deploy"]
    version = deploy / "releases" / ("b" * 40)
    version.mkdir(parents=True)
    (version / "live_server.py").write_text("v2\n")
    result = zhs._switch_current(version)
    assert result["ok"], result
    current = deploy / "current"
    assert current.is_symlink()
    assert current.resolve() == version.resolve()
    assert list(deploy.glob(".current.tmp.*")) == []


def test_publish_end_to_end_hermetic(zhs_env):
    host = zhs_env["host"]
    deploy = zhs_env["deploy"]
    (host / "live_server.py.asset").write_text("fixed live_server v2\n")
    (host / "observatory_query.py.asset").write_text("fixed observatory v2\n")
    for name in ("template.html", "refresh.py.asset", "panorama-collect-main.py.asset",
                 "copilot_service.py.asset", "rag_engine.py.asset", "strategy_sources.py.asset",
                 "strategy_collector.py.asset", "documents_collector.py.asset",
                 "workflow_collector.py.asset", "scheduler_collector.py.asset",
                 "orchestrator.py.asset", "portfolio_collector.py.asset",
                 "strategy_projection.py.asset", "agent_brief_collector.py.asset"):
        (host / name).write_text("x\n")
    (deploy / "live_server.py").write_text("old live_server\n")
    (deploy / "observatory_query.py").write_text("old observatory\n")
    (deploy / "template.html").write_text("template\n")
    (deploy / "refresh.py").write_text("refresh\n")
    (deploy / "runtime_paths.py").write_text("# retained runtime paths\n")
    (deploy / "collectors").mkdir()
    (deploy / "collectors" / "__init__.py").write_text("")
    (deploy / "collectors" / "base.py").write_text("# retained collector base\n")
    _git_baseline(host)
    _git_baseline(deploy)
    _write_plist(zhs_env["plist"], str(deploy / "live_server.py"))

    m = zhs.migrate()
    assert m.get("ok"), m
    assert m["entrypoint"] == str(zhs.CURRENT_ENTRYPOINT)
    assert (deploy / "current").is_symlink()

    zhs._running_registered_runtime = lambda: _fake_runtime(deploy)
    p = zhs.publish(["live_server.py", "observatory_query.py"])
    assert p.get("ok"), p
    assert (deploy / "current").resolve() == (deploy / "releases" / p["oid"]).resolve()
    assert (deploy / "current" / "live_server.py").read_text() == "fixed live_server v2\n"
    assert (deploy / "current" / "runtime_paths.py").read_text() == "# retained runtime paths\n"
    assert (deploy / "current" / "collectors" / "base.py").read_text() == "# retained collector base\n"


def test_publish_requires_migration_first(zhs_env):
    deploy = zhs_env["deploy"]
    (deploy / "live_server.py").write_text("old\n")
    (zhs_env["host"] / "live_server.py.asset").write_text("fixed\n")
    zhs._running_registered_runtime = lambda: {
        "ok": True, "runtime_root": str(deploy),
        "entrypoint": str(deploy / "live_server.py")}
    result = zhs.publish(["live_server.py"])
    assert result.get("reason") == "plist_not_migrated"


def test_restore_switches_back(zhs_env, monkeypatch):
    deploy = zhs_env["deploy"]
    v1 = deploy / "releases" / ("1" * 40)
    v2 = deploy / "releases" / ("2" * 40)
    v1.mkdir(parents=True)
    v2.mkdir(parents=True)
    (v1 / "live_server.py").write_text("v1\n")
    (v2 / "live_server.py").write_text("v2\n")
    assert zhs._switch_current(v1)["ok"]
    assert zhs._switch_current(v2)["ok"]
    assert zhs._previous_version() == "1" * 40
    r = zhs.restore()
    assert r.get("ok"), r
    assert (deploy / "current").resolve() == v1.resolve()


def test_migrate_backs_up_plist(zhs_env):
    host = zhs_env["host"]
    deploy = zhs_env["deploy"]
    (deploy / "live_server.py").write_text("old\n")
    for name in ("live_server.py.asset", "observatory_query.py.asset", "template.html",
                 "refresh.py.asset", "panorama-collect-main.py.asset", "copilot_service.py.asset",
                 "rag_engine.py.asset", "strategy_sources.py.asset", "strategy_collector.py.asset",
                 "documents_collector.py.asset", "workflow_collector.py.asset",
                 "scheduler_collector.py.asset", "orchestrator.py.asset",
                 "portfolio_collector.py.asset", "strategy_projection.py.asset",
                 "agent_brief_collector.py.asset"):
        (host / name).write_text("x\n")
    _git_baseline(deploy)
    _write_plist(zhs_env["plist"], str(deploy / "live_server.py"))

    m = zhs.migrate()
    assert m.get("ok"), m
    assert Path(m["backup"]).exists()
    payload = plistlib.load(zhs_env["plist"].open("rb"))
    assert str(zhs.CURRENT_ENTRYPOINT) in payload["ProgramArguments"]
    # WorkingDirectory 使用稳定入口，与后续 current 原子切换一起移动。
    assert payload.get("WorkingDirectory") == str(zhs.CURRENT_LINK)
    assert (deploy / "current").is_symlink()
