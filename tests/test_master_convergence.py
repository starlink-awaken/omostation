#!/usr/bin/env python3
"""全生态主干收敛与双守护进程自动化集成测试套件"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
import pytest
import yaml

WORKSPACE_ROOT = Path("/Users/xiamingxing/Workspace")


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if not spec or not spec.loader:
        raise ImportError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_lecp_schema_validity():
    """测试统一生命事件契约 (LECP v3.0) 的合法性"""
    schema_path = WORKSPACE_ROOT / "protocols" / "lecp-schema.yaml"
    assert schema_path.exists(), "lecp-schema.yaml missing"
    data = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "lecp/v3.0"
    assert len(data["domains"]) == 5
    assert {lvl["id"] for lvl in data["privacy_levels"]} == {"public", "internal", "secret"}


def test_inbox_watcher_scan(tmp_path):
    """测试 Ingress Inbox 扫描器"""
    mod = _load_module("inbox_watcher", WORKSPACE_ROOT / "bin" / "ingress" / "inbox_watcher.py")
    test_inbox = tmp_path / "_inbox"
    health_dir = test_inbox / "health"
    health_dir.mkdir(parents=True)
    sample_file = health_dir / "体检单_2026.txt"
    sample_file.write_text("甘油三酯: 2.1 mmol/L (偏高)", encoding="utf-8")

    events = mod.scan_inbox(inbox_root=test_inbox)
    assert len(events) == 1
    assert events[0]["domain"] == "p1_health"


def test_semantic_diff_engine(tmp_path):
    """测试 Memory OS 语义 Diff 提取与偏好生成"""
    mod = _load_module("diff_engine", WORKSPACE_ROOT / "bin" / "memory" / "diff_engine.py")
    draft = "领导好，请尽快办理相关事宜。"
    final = "领导好，请于本周五前完成审核并报送。"

    diff_res = mod.extract_semantic_diff(draft, final)
    assert diff_res["change_count"] >= 1
    assert len(diff_res["extracted_rules"]) >= 1

    # 测试持久化
    test_db = tmp_path / "diff-test.db"
    test_pref = tmp_path / "pref-test.md"
    record_res = mod.record_signature_diff("evt-test-1", "p0_work", draft, final, db_path=test_db, pref_file=test_pref)
    assert record_res["change_count"] >= 1
    assert test_db.exists()
    assert test_pref.exists()


def test_core_and_sentinel_health_heartbeat(tmp_path):
    """测试双守护进程心跳与互保机制"""
    core_script = WORKSPACE_ROOT / "bin" / "ops" / "core-daemon.py"
    sentinel_script = WORKSPACE_ROOT / "bin" / "ops" / "sentinel-daemon.py"

    assert core_script.exists()
    assert sentinel_script.exists()

    # 运行一次单步 tick
    res_c = subprocess.run([sys.executable, str(core_script), "--once"], capture_output=True, text=True)
    assert res_c.returncode == 0

    res_s = subprocess.run([sys.executable, str(sentinel_script), "--once"], capture_output=True, text=True)
    assert res_s.returncode == 0


def test_auto_decay_patrol():
    """测试 30-60-90 半衰期巡检器"""
    mod = _load_module("auto_decay_patrol", WORKSPACE_ROOT / "bin" / "gac" / "auto-decay-patrol.py")
    res = mod.run_patrol()
    assert res["status"] == "ok"
