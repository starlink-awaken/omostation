"""CR-RESIDENT-STATUS-01 门禁的回归: 水位根随常驻服务的状态根声明走。

缺陷背景 (2026-10-28 实锤): ADR-0456 B4b Batch 3 (#4933) 把 6 条常驻服务的
OMOSTATION_STATE_ROOT 从检出根切到 ~/.local/state/omostation/prod, daemon 的水位
随之改写到那个根; 而本门禁当时仍硬解检出根 (Path(__file__).parents[2]) => 读到
切道前冻结的那份 => 判活永久失明 —— 报「stale 5 小时」而 daemon 实际每 2 分钟在跑。

本测试锁住两件事:
1. 水位到**角色自己声明的状态根**下找 (而非检出根);
2. 判据仍有牙齿: 声明根下的水位陈旧 => 必须 FAIL (不是被「找不到」悄悄放过)。
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin" / "gac" / "check-resident-status.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_resident_status", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_resident_status"] = mod
    spec.loader.exec_module(mod)
    return mod


def _services_yaml(state_root, enabled=True):
    """最小 services.yaml 主体文档: 一个 enabled 的 resident.decision 服务。"""
    environment = ""
    if state_root:
        environment = "  environment:\n    OMOSTATION_STATE_ROOT: {}\n".format(state_root)
    return (
        "status: active\n"
        "lifecycle: ssot\n"
        "---\n"
        "services:\n"
        "- id: resident.decision\n"
        "  enabled: {}\n"
        "  scheduler: launchd\n"
        "  label: com.l4.resident.decision\n".format(str(enabled).lower())
        + environment
    )


def _write_watermark(root, age_seconds):
    wm_dir = root / ".omo" / "_delivery" / "resident-orchestrator" / "watermarks"
    wm_dir.mkdir(parents=True, exist_ok=True)
    path = wm_dir / "resident-decision.json"
    path.write_text(json.dumps({"byte_offset": 42}), encoding="utf-8")
    stamp = time.time() - age_seconds
    os.utime(path, (stamp, stamp))
    return path


def test_reads_watermark_from_the_declared_state_root(tmp_path, monkeypatch):
    """水位在声明的状态根下 => 必须读到, 且判为新鲜 (这是修复前失明的那一面)。"""
    state_root = tmp_path / "state"
    _write_watermark(state_root, 5)

    registry = tmp_path / "services.yaml"
    registry.write_text(_services_yaml(state_root), encoding="utf-8")

    mod = _load()
    monkeypatch.setattr(mod, "SERVICES_REGISTRY", registry)
    monkeypatch.setattr(mod, "REPO", tmp_path / "checkout")

    ok, detail = mod.check_daemon_watermark()
    assert ok, detail
    assert "scope=enabled+daemon" in detail


def test_stale_watermark_in_declared_state_root_still_fails(tmp_path, monkeypatch):
    """判据有牙齿: 声明根下的水位陈旧 => FAIL (不得被「找不到」悄悄放过)。"""
    state_root = tmp_path / "state"
    _write_watermark(state_root, 7200)

    registry = tmp_path / "services.yaml"
    registry.write_text(_services_yaml(state_root), encoding="utf-8")

    mod = _load()
    monkeypatch.setattr(mod, "SERVICES_REGISTRY", registry)
    monkeypatch.setattr(mod, "REPO", tmp_path / "checkout")

    ok, detail = mod.check_daemon_watermark()
    assert not ok, detail
    assert "degraded" in detail


def test_frozen_watermark_in_checkout_root_is_not_used(tmp_path, monkeypatch):
    """切道前冻结在检出根的那份水位不得再被采用 (失明根因本身)。"""
    checkout = tmp_path / "checkout"
    _write_watermark(checkout, 7200)
    state_root = tmp_path / "state"
    _write_watermark(state_root, 5)

    registry = tmp_path / "services.yaml"
    registry.write_text(_services_yaml(state_root), encoding="utf-8")

    mod = _load()
    monkeypatch.setattr(mod, "SERVICES_REGISTRY", registry)
    monkeypatch.setattr(mod, "REPO", checkout)

    ok, detail = mod.check_daemon_watermark()
    assert ok, detail
    assert "degraded" not in detail


def test_no_state_root_declaration_falls_back_to_checkout(tmp_path, monkeypatch):
    """未声明状态根 => 回落检出根 (逐字节复现切道前的历史落点)。"""
    checkout = tmp_path / "checkout"
    _write_watermark(checkout, 5)

    registry = tmp_path / "services.yaml"
    registry.write_text(_services_yaml(None), encoding="utf-8")

    mod = _load()
    monkeypatch.setattr(mod, "SERVICES_REGISTRY", registry)
    monkeypatch.setattr(mod, "REPO", checkout)

    ok, detail = mod.check_daemon_watermark()
    assert ok, detail


def test_missing_watermarks_is_never_ticked_and_exempt(tmp_path, monkeypatch):
    """判活范围内无水位 => never_ticked 豁免 (CI 干净检出的事实, 不是放行)。"""
    registry = tmp_path / "services.yaml"
    registry.write_text(_services_yaml(tmp_path / "state"), encoding="utf-8")

    mod = _load()
    monkeypatch.setattr(mod, "SERVICES_REGISTRY", registry)
    monkeypatch.setattr(mod, "REPO", tmp_path / "checkout")

    ok, detail = mod.check_daemon_watermark()
    assert ok, detail
    assert "never_ticked=true" in detail


def test_disabled_role_is_excluded_from_scope(tmp_path, monkeypatch):
    """enabled=False 的角色不参与判活 (停用角色水位本就不再推进)。"""
    state_root = tmp_path / "state"
    _write_watermark(state_root, 7200)

    registry = tmp_path / "services.yaml"
    registry.write_text(_services_yaml(state_root, enabled=False), encoding="utf-8")

    mod = _load()
    monkeypatch.setattr(mod, "SERVICES_REGISTRY", registry)
    monkeypatch.setattr(mod, "REPO", tmp_path / "checkout")

    ok, detail = mod.check_daemon_watermark()
    assert ok, detail
    assert "never_ticked=true" in detail

def test_real_stall_is_reported_even_when_checkout_root_looks_fresh(tmp_path, monkeypatch):
    """真停摆必须报出: 声明根水位陈旧 + 检出根水位新鲜 (切道前冻结的假象)
    => 仍须 FAIL —— 否则「切道前那份还新鲜」会把停摆掩盖成健康。"""
    state_root = tmp_path / "state"
    _write_watermark(state_root, 7200)
    checkout = tmp_path / "checkout"
    _write_watermark(checkout, 5)

    registry = tmp_path / "services.yaml"
    registry.write_text(_services_yaml(state_root), encoding="utf-8")

    mod = _load()
    monkeypatch.setattr(mod, "SERVICES_REGISTRY", registry)
    monkeypatch.setattr(mod, "REPO", checkout)

    ok, detail = mod.check_daemon_watermark()
    assert not ok, detail
    assert "degraded" in detail
