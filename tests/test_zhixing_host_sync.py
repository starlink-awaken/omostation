"""织星宿主资产只读状态、漂移计划与发布封锁测试.

对应 docs/DASHBOARDS.md §3.1 (2026-09-17 实证): :43191 部署目录不在版本控制,
多 agent 并发编辑 template.html/refresh.py 互相覆盖 —— 场景面板丢失、已修 bug
被回退。本工具报告已版本化资产的运行漂移；生产写入保持封锁。
"""

from __future__ import annotations

import hashlib
import importlib.util
import plistlib
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "bin/gac/zhixing-host-sync.py"

# The fixture contract is explicit and independent of HOST_FILES, so accidentally
# dropping a production mapping cannot make drift-plan tests silently pass.
EXPECTED_FILES = {
    "template.html": "template.html",
    "refresh.py": "refresh.py.asset",
    "live_server.py": "live_server.py.asset",
    "observatory_query.py": "observatory_query.py.asset",
    "panorama-collect-main.py": "panorama-collect-main.py.asset",
    "copilot_service.py": "copilot_service.py.asset",
    "rag_engine.py": "rag_engine.py.asset",
    "strategy_sources.py": "strategy_sources.py.asset",
    "collectors/strategy.py": "strategy_collector.py.asset",
    "collectors/documents.py": "documents_collector.py.asset",
    "collectors/workflow.py": "workflow_collector.py.asset",
    "collectors/scheduler.py": "scheduler_collector.py.asset",
    "orchestrator.py": "orchestrator.py.asset",
    "collectors/portfolio.py": "portfolio_collector.py.asset",
    "strategy_projection.py": "strategy_projection.py.asset",
    "collectors/agent_brief.py": "agent_brief_collector.py.asset",
}


def _load():
    spec = importlib.util.spec_from_file_location("zhixing_host_sync", TOOL)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["zhixing_host_sync"] = mod
    spec.loader.exec_module(mod)
    return mod


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def _dirs(tmp_path: Path):
    dash = tmp_path / "deploy"
    host = tmp_path / "repo" / "host"
    dash.mkdir(parents=True)
    return dash, host


def _seed_deploy(dash: Path, *, template: str = "<html>live</html>\n",
                 refresh: str = "# refresh live\n",
                 live_server: str = "# live server\n",
                 observatory_query: str = "# observatory query\n",
                 panorama_collector: str = "# panorama collector live\n") -> None:
    (dash / "template.html").write_text(template, encoding="utf-8")
    (dash / "refresh.py").write_text(refresh, encoding="utf-8")
    (dash / "live_server.py").write_text(live_server, encoding="utf-8")
    (dash / "observatory_query.py").write_text(observatory_query, encoding="utf-8")
    (dash / "panorama-collect-main.py").write_text(panorama_collector, encoding="utf-8")
    for name in EXPECTED_FILES:
        target = dash / name
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"# fixture for {name}\n", encoding="utf-8")


def _seed_repo(host: Path, *, template: str, refresh: str,
               live_server: str = "# repo live server\n",
               observatory_query: str = "# repo observatory query\n",
               panorama_collector: str = "# repo panorama collector\n") -> None:
    """仓库资产名与部署名不同 (*.py 存为 *.py.asset, 见工具头注释)."""
    host.mkdir(parents=True, exist_ok=True)
    (host / "template.html").write_text(template, encoding="utf-8")
    (host / "refresh.py.asset").write_text(refresh, encoding="utf-8")
    (host / "live_server.py.asset").write_text(live_server, encoding="utf-8")
    (host / "observatory_query.py.asset").write_text(observatory_query, encoding="utf-8")
    (host / "panorama-collect-main.py.asset").write_text(panorama_collector, encoding="utf-8")
    for name in EXPECTED_FILES.values():
        target = host / name
        if not target.exists():
            target.write_text(f"# repo fixture for {name}\n", encoding="utf-8")


def _align_repo_to_deploy(dash: Path, host: Path) -> None:
    host.mkdir(parents=True, exist_ok=True)
    for deploy_name, repo_name in EXPECTED_FILES.items():
        target = host / repo_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((dash / deploy_name).read_bytes())


def _bind_running_agent(tool, monkeypatch, dash: Path, host: Path, *, command: str | None = None,
                        with_working_directory: bool = True) -> None:
    entrypoint = dash / "live_server.py"
    payload = {
        "Label": "com.omostation.zhixing-dashboard",
        "ProgramArguments": ["/opt/homebrew/bin/python3", "-B", str(entrypoint), "--port", "43191"],
    }
    if with_working_directory:
        payload["WorkingDirectory"] = str(dash)
    plist = dash.parent / "com.omostation.zhixing-dashboard.plist"
    plist.write_bytes(plistlib.dumps(payload))
    monkeypatch.setattr(tool, "LAUNCH_AGENT_PLIST", plist)
    monkeypatch.setattr(tool, "HOST_DIR", host)

    class Result:
        def __init__(self, returncode: int, stdout: str):
            self.returncode = returncode
            self.stdout = stdout

    def runner(arguments, **_kwargs):
        if arguments[0] == "launchctl":
            return Result(0, "\tpid = 4321\n")
        assert arguments[:3] == ["ps", "-p", "4321"]
        return Result(0, command or f"/opt/homebrew/bin/python3 -B {entrypoint} --port 43191\n")

    monkeypatch.setattr(tool.subprocess, "run", runner)


# ── 未版本化检测 ─────────────────────────────────────────


def test_status_reports_missing_repo_copy(tmp_path):
    dash, host = _dirs(tmp_path)
    _seed_deploy(dash)
    tool = _load()
    info = tool.status(dashboard_dir=dash, host_dir=host)
    assert info["missing_repo_copy"] == len(EXPECTED_FILES)
    assert info["ok"] is False
    assert {f["state"] for f in info["files"]} == {"no_repo_copy"}
    # 仍能报告线上 sha (便于人工确认捕获对象)
    assert all(f["deploy_sha"] for f in info["files"])


def test_check_exits_nonzero_when_unversioned(tmp_path):
    dash, host = _dirs(tmp_path)
    _seed_deploy(dash)
    tool = _load()
    assert tool.status(dashboard_dir=dash, host_dir=host)["ok"] is False


# ── 漂移检测（核心）──────────────────────────────────────


def test_detects_drift_after_direct_deploy_edit(tmp_path):
    """核心: 部署被直接编辑 (即"被并发覆盖"的形态) → 必须检出漂移."""
    dash, host = _dirs(tmp_path)
    _seed_deploy(dash)
    _align_repo_to_deploy(dash, host)
    tool = _load()
    assert tool.status(dashboard_dir=dash, host_dir=host)["ok"] is True

    # 模拟另一 agent 直接改部署目录
    (dash / "template.html").write_text("<html>HACKED by other agent</html>\n",
                                        encoding="utf-8")
    info = tool.status(dashboard_dir=dash, host_dir=host)
    assert info["drifted"] == 1
    drifted = [f for f in info["files"] if f["state"] == "drifted"]
    assert drifted[0]["name"] == "template.html"
    assert drifted[0]["repo_sha"] != drifted[0]["deploy_sha"]
    assert tool.status(dashboard_dir=dash, host_dir=host)["ok"] is False
    # 未被漂移的文件仍应为 in_sync
    assert [f["state"] for f in info["files"] if f["name"] == "refresh.py"] == ["in_sync"]


def test_status_reports_absent_runtime_without_writing(tmp_path):
    """状态读取不会把未部署目录或报告文件创建出来。"""
    _, host = _dirs(tmp_path)
    missing_runtime = tmp_path / "nope"
    tool = _load()
    info = tool.status(dashboard_dir=missing_runtime, host_dir=host)
    assert info["missing_repo_copy"] == len(EXPECTED_FILES)
    assert missing_runtime.exists() is False


# ── 真实仓库的纳管副本 ───────────────────────────────────


def test_real_repo_host_copies_are_tracked_and_nonempty():
    """本仓已纳管宿主副本 (防止 PR 里只留空壳)."""
    host = Path(__file__).resolve().parents[1] / "bin/panorama/assets/host"
    for repo_name in ("template.html", "refresh.py.asset"):
        f = host / repo_name
        assert f.is_file(), f"{repo_name} 未纳管"
        assert f.stat().st_size > 1000, f"{repo_name} 体积异常, 疑为空壳"


def test_host_files_scope_includes_server_and_excludes_data():
    """纳管范围只含宿主文件; 排除数据/产物; 且仓库名不得是 .py/.sh (避开脚本治理面)."""
    tool = _load()
    deploy_names = {d for d, _ in tool.HOST_FILES}
    assert dict(tool.HOST_FILES) == EXPECTED_FILES
    assert len(tool.HOST_FILES) == len(EXPECTED_FILES)
    for _, repo_name in tool.HOST_FILES:
        assert not repo_name.endswith((".py", ".sh")), (
            f"{repo_name} 会被 script-registry/bin-quota 视为脚本 —— 应加 .asset 后缀"
        )
    for banned in ("index.html", "current.json", "previous-snapshot.json"):
        assert banned not in deploy_names


def test_plan_only_uses_registered_launch_agent_root(tmp_path, monkeypatch):
    dash, host = _dirs(tmp_path)
    _seed_deploy(dash)
    _align_repo_to_deploy(dash, host)
    tool = _load()
    _bind_running_agent(tool, monkeypatch, dash, host)
    (dash / "template.html").write_text("runtime drift\n", encoding="utf-8")

    result = tool.plan(["template.html"])
    assert result["registration"]["runtime_root"] == str(dash.resolve())
    assert result["target_root"] == str(dash.resolve())
    assert result["files"] == [{
        "name": "template.html",
        "state": "drifted",
        "source": str(host / "template.html"),
        "runtime": str(dash / "template.html"),
        "source_sha": _sha(host / "template.html"),
        "runtime_sha": _sha(dash / "template.html"),
    }]
    assert result["write_performed"] is False
    assert result["registration"]["pid"] == 4321


def test_plan_derives_root_from_registered_absolute_entrypoint(tmp_path, monkeypatch):
    dash, host = _dirs(tmp_path)
    _seed_deploy(dash)
    _align_repo_to_deploy(dash, host)
    tool = _load()
    _bind_running_agent(tool, monkeypatch, dash, host, with_working_directory=False)

    result = tool.plan(["live_server.py"])
    assert result["registration"]["runtime_root"] == str(dash.resolve())
    assert result["files"][0]["state"] == "in_sync"
    assert result["write_performed"] is False


def test_cli_status_binds_the_live_pid_and_command(tmp_path, monkeypatch, capsys):
    dash, host = _dirs(tmp_path)
    _seed_deploy(dash)
    _align_repo_to_deploy(dash, host)
    tool = _load()
    _bind_running_agent(tool, monkeypatch, dash, host)

    assert tool.main(["status", "--json"]) == 0
    import json
    result = json.loads(capsys.readouterr().out)
    assert result["registration"]["pid"] == 4321
    assert str(dash / "live_server.py") in result["registration"]["command"]
    assert result["write_performed"] is False


def test_plan_rejects_pid_command_mismatch_without_writing(tmp_path, monkeypatch):
    dash, host = _dirs(tmp_path)
    _seed_deploy(dash)
    _align_repo_to_deploy(dash, host)
    tool = _load()
    before = {path.relative_to(dash): _sha(path) for path in dash.rglob("*") if path.is_file()}
    _bind_running_agent(
        tool,
        monkeypatch,
        dash,
        host,
        command="/opt/homebrew/bin/python3 -B /tmp/other-live_server.py --port 43191\n",
    )

    result = tool.plan(["live_server.py"])
    assert result["ok"] is False
    assert result["reason"] == "launch_agent_identity_unverified"
    assert result["runtime"]["reason"] == "launch_agent_pid_command_mismatch"
    after = {path.relative_to(dash): _sha(path) for path in dash.rglob("*") if path.is_file()}
    assert after == before


def test_all_public_functions_are_read_only_or_blocked(tmp_path, monkeypatch):
    dash, host = _dirs(tmp_path)
    _seed_deploy(dash)
    _align_repo_to_deploy(dash, host)
    tool = _load()
    _bind_running_agent(tool, monkeypatch, dash, host)
    before = {
        path.relative_to(tmp_path): _sha(path)
        for path in tmp_path.rglob("*") if path.is_file()
    }

    assert tool.status(dashboard_dir=dash, host_dir=host)["ok"] is True
    assert tool.plan(["live_server.py"])["ok"] is True
    assert tool.check() == 0
    for operation in ("capture", "publish", "restore"):
        result = getattr(tool, operation)()
        assert result["state"] == "BLOCKED"
        assert result["reason"] == tool.BLOCKED_REASON
    after = {
        path.relative_to(tmp_path): _sha(path)
        for path in tmp_path.rglob("*") if path.is_file()
    }
    assert after == before


def test_cli_write_commands_are_blocked_and_check_remains_read_only(tmp_path, monkeypatch, capsys):
    dash, host = _dirs(tmp_path)
    _seed_deploy(dash)
    _align_repo_to_deploy(dash, host)
    tool = _load()
    _bind_running_agent(tool, monkeypatch, dash, host)
    before = {path.relative_to(tmp_path): _sha(path) for path in tmp_path.rglob("*") if path.is_file()}

    for command in ("apply", "capture", "publish", "restore"):
        assert tool.main([command, "--target-root", str(dash)]) == 2
        out = capsys.readouterr().out
        assert '"state": "BLOCKED"' in out
        assert '"operation": "' + command + '"' in out
    assert tool.main(["check", "--json"]) == 0
    assert '"write_performed": false' in capsys.readouterr().out
    assert "--target-root" not in tool.__doc__
    after = {path.relative_to(tmp_path): _sha(path) for path in tmp_path.rglob("*") if path.is_file()}
    assert after == before


def test_real_repo_server_assets_have_no_static_credentials():
    host = Path(__file__).resolve().parents[1] / "bin/panorama/assets/host"
    for repo_name in (
        "live_server.py.asset",
        "observatory_query.py.asset",
        "panorama-collect-main.py.asset",
    ):
        text = (host / repo_name).read_text(encoding="utf-8")
        assert "ghp_" not in text
        assert "github_pat_" not in text
        assert "BEGIN OPENSSH PRIVATE KEY" not in text
