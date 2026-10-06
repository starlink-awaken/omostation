from __future__ import annotations

import importlib.util
import json
import os
import time
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / "bin" / "gac" / "check-resident-status.py"


def _module():
    spec = importlib.util.spec_from_file_location("resident_status_under_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_watermark(mdir: Path, name: str, mtime: float) -> None:
    path = mdir / name
    path.write_text(json.dumps({"byte_offset": 42}), encoding="utf-8")
    os.utime(path, (mtime, mtime))


def test_scope_excludes_roles_that_never_tick(monkeypatch, tmp_path: Path) -> None:
    """停用角色与不写水位的角色都不参与活性判据。

    背景 (2026-10-06):
    - resident-heartbeat/monitor/sediment 在 services.yaml 中 enabled=False,
      水位自然停在 33h 前。旧判据取 min(mtime) 会把它们算进去, 让健康的
      daemon 被误报 degraded (实测 decision/execute 水位仅 3s 前)。
    - signals/inbox/promote 走各自独立 CLI 入口 (omo.resident.cli <role>),
      从不进入 daemon 的 run_projector, 因此**不写水位**。把它们纳入判活
      等于要求一个永不更新的文件保持新鲜。

    本测试用陈旧的 daemon 角色水位 + 新鲜的非判活角色, 断言仍判 FAIL,
    证明判活范围确实被正确收窄, 而不是把检查一并放过了。
    """
    module = _module()
    mdir = tmp_path / "watermarks"
    mdir.mkdir()
    now = time.time()
    stale = now - 10_000  # 远超 1800s 阈值

    _write_watermark(mdir, "resident-decision.json", stale)
    _write_watermark(mdir, "resident-execute.json", stale)
    # 这三个既不在 DAEMON_TICKED_ROLES, 又对判活无意义, 但 mtime 是新鲜的
    _write_watermark(mdir, "resident-signals.json", now)
    _write_watermark(mdir, "resident-inbox.json", now)
    _write_watermark(mdir, "resident-promote.json", now)
    # 停用角色: 陈旧
    _write_watermark(mdir, "resident-heartbeat.json", stale)
    _write_watermark(mdir, "resident-sediment.json", stale)
    _write_watermark(mdir, "resident-monitor.json", stale)

    monkeypatch.setattr(module, "WATERMARKS", mdir)
    monkeypatch.setattr(module, "enabled_resident_roles", lambda: {"resident-decision", "resident-execute"})

    passed, detail = module.check_daemon_watermark()
    assert passed is False, "陈旧的 daemon 角色水位必须仍然 FAIL"
    assert "resident-decision" in detail
    assert "scope=enabled+daemon" in detail


def test_healthy_daemon_roles_pass_despite_stale_disabled_ones(monkeypatch, tmp_path: Path) -> None:
    """反向护栏: 在役 daemon 角色新鲜时必须 PASS, 不被停用角色的陈旧水位拖累。"""
    module = _module()
    mdir = tmp_path / "watermarks"
    mdir.mkdir()
    now = time.time()

    _write_watermark(mdir, "resident-decision.json", now)
    _write_watermark(mdir, "resident-execute.json", now)
    # 停用角色的水位很旧 —— 这正是本缺陷的现场
    _write_watermark(mdir, "resident-heartbeat.json", now - 120_000)
    _write_watermark(mdir, "resident-monitor.json", now - 120_000)
    _write_watermark(mdir, "resident-sediment.json", now - 120_000)

    monkeypatch.setattr(module, "WATERMARKS", mdir)
    monkeypatch.setattr(module, "enabled_resident_roles", lambda: {"resident-decision", "resident-execute"})

    passed, detail = module.check_daemon_watermark()
    assert passed is True, f"健康的 daemon 不应被停用角色的陈旧水位判 degraded: {detail}"


def test_disabled_daemon_role_is_excluded(monkeypatch, tmp_path: Path) -> None:
    """enabled=False 的 daemon 角色也不参与判活 (水位本就不再推进)。"""
    module = _module()
    mdir = tmp_path / "watermarks"
    mdir.mkdir()
    now = time.time()

    _write_watermark(mdir, "resident-decision.json", now)
    # execute 是 daemon 角色, 但在册 enabled=False → 排除
    _write_watermark(mdir, "resident-execute.json", now - 120_000)

    monkeypatch.setattr(module, "WATERMARKS", mdir)
    monkeypatch.setattr(module, "enabled_resident_roles", lambda: {"resident-decision"})

    passed, _ = module.check_daemon_watermark()
    assert passed is True


def test_missing_registry_falls_back_to_daemon_roles(monkeypatch, tmp_path: Path) -> None:
    """读不到注册表时退回「daemon 角色」范围, 不得静默豁免全部检查。"""
    module = _module()
    mdir = tmp_path / "watermarks"
    mdir.mkdir()
    now = time.time()

    _write_watermark(mdir, "resident-decision.json", now - 10_000)
    _write_watermark(mdir, "resident-signals.json", now)  # 不该被采信

    monkeypatch.setattr(module, "WATERMARKS", mdir)
    monkeypatch.setattr(module, "enabled_resident_roles", lambda: None)

    passed, detail = module.check_daemon_watermark()
    assert passed is False, "注册表不可读时不能因为信号角色新鲜就放行"
    assert "scope=daemon" in detail


def test_never_ticked_is_exempt() -> None:
    """从未 tick (无水位文件) 仍豁免, 保持既有语义。"""
    module = _module()
    assert module.check_daemon_watermark()[0] is True