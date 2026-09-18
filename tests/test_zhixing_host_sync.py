"""织星宿主文件版本化/漂移检测回归测试.

对应 docs/DASHBOARDS.md §3.1 (2026-09-17 实证): :43191 部署目录不在版本控制,
多 agent 并发编辑 template.html/refresh.py 互相覆盖 —— 场景面板丢失、已修 bug
被回退。本工具把宿主文件纳管并提供漂移检测/恢复。
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "bin/gac/zhixing-host-sync.py"


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
                 refresh: str = "# refresh live\n") -> None:
    (dash / "template.html").write_text(template, encoding="utf-8")
    (dash / "refresh.py").write_text(refresh, encoding="utf-8")


def _seed_repo(host: Path, *, template: str, refresh: str) -> None:
    """仓库资产名与部署名不同 (refresh.py 存为 refresh.py.asset, 见工具头注释)."""
    host.mkdir(parents=True, exist_ok=True)
    (host / "template.html").write_text(template, encoding="utf-8")
    (host / "refresh.py.asset").write_text(refresh, encoding="utf-8")


# ── 未版本化检测 ─────────────────────────────────────────


def test_status_reports_missing_repo_copy(tmp_path):
    dash, host = _dirs(tmp_path)
    _seed_deploy(dash)
    tool = _load()
    info = tool.status(dashboard_dir=dash, host_dir=host)
    assert info["missing_repo_copy"] == 2
    assert info["ok"] is False
    assert {f["state"] for f in info["files"]} == {"no_repo_copy"}
    # 仍能报告线上 sha (便于人工确认捕获对象)
    assert all(f["deploy_sha"] for f in info["files"])


def test_check_exits_nonzero_when_unversioned(tmp_path):
    dash, host = _dirs(tmp_path)
    _seed_deploy(dash)
    tool = _load()
    assert tool.check(dashboard_dir=dash, host_dir=host) == 1


# ── capture ──────────────────────────────────────────────


def test_capture_versions_deploy_files(tmp_path):
    dash, host = _dirs(tmp_path)
    _seed_deploy(dash)
    tool = _load()
    r = tool.capture(dashboard_dir=dash, host_dir=host)
    assert r["ok"] is True
    assert {c["name"] for c in r["captured"]} == {"template.html", "refresh.py"}
    assert (host / "template.html").read_bytes() == (dash / "template.html").read_bytes()
    # refresh.py 以 .asset 后缀纳管 (避开 script-registry 脚本治理面)
    assert (host / "refresh.py.asset").read_bytes() == (dash / "refresh.py").read_bytes()

    info = tool.status(dashboard_dir=dash, host_dir=host)
    assert info["ok"] is True
    assert info["drifted"] == 0
    assert tool.check(dashboard_dir=dash, host_dir=host) == 0


def test_capture_is_idempotent(tmp_path):
    dash, host = _dirs(tmp_path)
    _seed_deploy(dash)
    tool = _load()
    tool.capture(dashboard_dir=dash, host_dir=host)
    second = tool.capture(dashboard_dir=dash, host_dir=host)
    assert second["captured"] == []
    assert {s["reason"] for s in second["skipped"]} == {"already_same"}


# ── 漂移检测（核心）──────────────────────────────────────


def test_detects_drift_after_direct_deploy_edit(tmp_path):
    """核心: 部署被直接编辑 (即"被并发覆盖"的形态) → 必须检出漂移."""
    dash, host = _dirs(tmp_path)
    _seed_deploy(dash)
    tool = _load()
    tool.capture(dashboard_dir=dash, host_dir=host)
    assert tool.check(dashboard_dir=dash, host_dir=host) == 0

    # 模拟另一 agent 直接改部署目录
    (dash / "template.html").write_text("<html>HACKED by other agent</html>\n",
                                        encoding="utf-8")
    info = tool.status(dashboard_dir=dash, host_dir=host)
    assert info["drifted"] == 1
    drifted = [f for f in info["files"] if f["state"] == "drifted"]
    assert drifted[0]["name"] == "template.html"
    assert drifted[0]["repo_sha"] != drifted[0]["deploy_sha"]
    assert tool.check(dashboard_dir=dash, host_dir=host) == 1
    # 未被漂移的文件仍应为 in_sync
    assert [f["state"] for f in info["files"] if f["name"] == "refresh.py"] == ["in_sync"]


def test_check_skips_when_not_deployed(tmp_path):
    """非本机/未部署 → 天然跳过, 不误报."""
    _, host = _dirs(tmp_path)
    tool = _load()
    assert tool.check(dashboard_dir=tmp_path / "nope", host_dir=host) == 0


# ── restore ──────────────────────────────────────────────


def test_restore_dry_run_does_not_write(tmp_path):
    dash, host = _dirs(tmp_path)
    _seed_deploy(dash)
    tool = _load()
    tool.capture(dashboard_dir=dash, host_dir=host)
    (dash / "template.html").write_text("drift\n", encoding="utf-8")

    r = tool.restore(force=False, dashboard_dir=dash, host_dir=host)
    assert r["dry_run"] is True
    assert r["restored"] == ["template.html"]
    assert (dash / "template.html").read_text() == "drift\n", "dry-run 不得写入"


def test_restore_force_reverts_and_keeps_backup(tmp_path):
    dash, host = _dirs(tmp_path)
    _seed_deploy(dash)
    tool = _load()
    tool.capture(dashboard_dir=dash, host_dir=host)
    expected = (host / "template.html").read_text()
    (dash / "template.html").write_text("HACKED\n", encoding="utf-8")

    r = tool.restore(force=True, dashboard_dir=dash, host_dir=host)
    assert r["restored"] == ["template.html"]
    assert (dash / "template.html").read_text() == expected, "应回滚为仓库版本"
    bak = dash / "template.html.before-restore"
    assert bak.is_file() and bak.read_text() == "HACKED\n", "原文件必须留备份"
    assert tool.check(dashboard_dir=dash, host_dir=host) == 0


def test_restore_reports_missing_repo_copy(tmp_path):
    """两种缺失形态: 整目录缺失 → no_repo_copy; 单文件缺失 → missing_repo 列表."""
    dash, host = _dirs(tmp_path)
    _seed_deploy(dash)
    tool = _load()

    # (a) 仓库宿主目录整体不存在
    r = tool.restore(force=True, dashboard_dir=dash, host_dir=host)
    assert r["ok"] is False and r["reason"] == "no_repo_copy"

    # (b) 目录存在但只纳管了部分文件
    _seed_repo(host, template="repo template\n", refresh="repo refresh\n")
    (host / "refresh.py.asset").unlink()
    r2 = tool.restore(force=True, dashboard_dir=dash, host_dir=host)
    assert r2["ok"] is True
    assert r2["missing_repo"] == ["refresh.py"]
    assert r2["restored"] == ["template.html"]


# ── 真实仓库的纳管副本 ───────────────────────────────────


def test_real_repo_host_copies_are_tracked_and_nonempty():
    """本仓已纳管宿主副本 (防止 PR 里只留空壳)."""
    host = Path(__file__).resolve().parents[1] / "bin/panorama/assets/host"
    for repo_name in ("template.html", "refresh.py.asset"):
        f = host / repo_name
        assert f.is_file(), f"{repo_name} 未纳管"
        assert f.stat().st_size > 1000, f"{repo_name} 体积异常, 疑为空壳"


def test_host_files_scope_excludes_data_and_scripts():
    """纳管范围只含宿主文件; 排除数据/产物; 且仓库名不得是 .py/.sh (避开脚本治理面)."""
    tool = _load()
    deploy_names = {d for d, _ in tool.HOST_FILES}
    assert deploy_names == {"template.html", "refresh.py"}
    for _, repo_name in tool.HOST_FILES:
        assert not repo_name.endswith((".py", ".sh")), (
            f"{repo_name} 会被 script-registry/bin-quota 视为脚本 —— 应加 .asset 后缀"
        )
    for banned in ("index.html", "current.json", "previous-snapshot.json"):
        assert banned not in deploy_names
