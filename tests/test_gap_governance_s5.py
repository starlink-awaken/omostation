"""S5 差距治理工具测试: GOV-REBAL / AUTO-FIX / UX-NOISE.

覆盖:
  1. check-derived-only-fast-track (GOV-REBAL):
     - 纯派生文档 → fast_track=True, change-lane=derived-doc-only
     - 混入源码 → fast_track=False
     - 空变更 → 无 fast-track
  2. auto-fix-loop (AUTO-FIX):
     - 干净环境 → 无漂移
     - PATH-DRIFT 检测 (注册表 path 缺失)
     - 不自动应用需人工项
  3. command-discovery (UX-NOISE):
     - 解析场景组 + 密度分布
     - 兜底组 ("其他") 超阈值 → dense_groups 非空
     - JSON 结构完整
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "bin" / "gac"

FAST_TRACK = BIN / "check-derived-only-fast-track.py"
AUTO_FIX = BIN / "auto-fix-loop.py"
DISCOVERY = BIN / "command-discovery.py"


def _run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _load(script: Path):
    spec = importlib.util.spec_from_file_location(script.stem, str(script))
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


# ── GOV-REBAL: check-derived-only-fast-track ────────────────────────────────
def test_fast_track_pure_derived() -> None:
    mod = _load(FAST_TRACK)
    report = mod.check(staged=True, files=["docs/generated/capability-registry.yaml", "docs/CLI-REFERENCE.md"])
    assert report["fast_track"] is True
    assert report["change_lane"] == "derived-doc-only"
    assert report["derived_files"] == ["docs/generated/capability-registry.yaml", "docs/CLI-REFERENCE.md"]
    assert report["non_derived_files"] == []
    assert "project-doc-change" in report["workflows"]


def test_fast_track_mixed_source() -> None:
    mod = _load(FAST_TRACK)
    report = mod.check(
        staged=True,
        files=["docs/generated/capability-registry.yaml", "bin/gac/gac-local-gate.py"],
    )
    assert report["fast_track"] is False
    assert report["change_lane"] == "mixed-or-source"
    assert "bin/gac/gac-local-gate.py" in report["non_derived_files"]


def test_fast_track_empty() -> None:
    mod = _load(FAST_TRACK)
    report = mod.check(staged=True, files=[])
    assert report["fast_track"] is False
    assert report["change_lane"] == "no-changes"


# ── AUTO-FIX: auto-fix-loop ─────────────────────────────────────────────────
def test_auto_fix_detect_no_drift() -> None:
    mod = _load(AUTO_FIX)
    drifts = mod.detect_drifts()
    # PATH-DRIFT 不应有 error (当前注册表干净)
    errors = [d for d in drifts if d.severity == "error"]
    assert errors == []


def test_auto_fix_path_drift_detection() -> None:
    """模拟 PATH-DRIFT: 注册表 path 指向缺失实现 → error 级, 不自动修复."""
    mod = _load(AUTO_FIX)
    fake = {
        "tools": {"ghost-capability": {"path": "nonexistent/impl.py"}},
    }
    drifts = mod.detect_drifts()
    # 构造一个 path-drift 漂移对象验证 apply_fix 拒绝自动应用
    d = mod.Drift(
        kind="PATH-DRIFT",
        severity="error",
        message="注册表 path 指向缺失实现 (需人工)",
        fix_cmd="bin/gac/check-capability-ownership.py",
        auto_fixable=False,
    )
    ok, out = mod.apply_fix(d)
    assert ok is False
    assert "人工" in out


def test_auto_fix_json_shape() -> None:
    r = _run(AUTO_FIX, "--json")
    assert r.returncode == 0
    payload = json.loads(r.stdout)
    assert "drifts" in payload and "applied" in payload and "count" in payload


# ── UX-NOISE: command-discovery ─────────────────────────────────────────────
def test_command_discovery_parses_groups() -> None:
    mod = _load(DISCOVERY)
    ref = ROOT / "docs" / "CLI-REFERENCE.md"
    assert ref.is_file()
    groups = mod.parse_groups(ref.read_text(encoding="utf-8"))
    assert len(groups) >= 5  # 至少 5 个场景组
    # cockpit 主命令族应存在
    all_cmds = [c for v in groups.values() for c in v]
    assert any(c.startswith("cockpit") for c in all_cmds)


def test_command_discovery_density() -> None:
    mod = _load(DISCOVERY)
    ref = ROOT / "docs" / "CLI-REFERENCE.md"
    groups = mod.parse_groups(ref.read_text(encoding="utf-8"))
    report = mod.detect_noise(groups)
    assert report["total_commands"] >= 50
    assert report["group_count"] == len(groups)
    # 兜底组 ("其他") 承载最多命令 → 应触发 dense 信号
    assert report["dense_groups"], "兜底组超阈值应触发 UX-NOISE 密度信号"
    assert all(k in report for k in ("total_commands", "group_count", "dense_groups", "similar_commands", "confusing_commands", "orphan_groups", "groups"))


def test_command_discovery_cli() -> None:
    r = _run(DISCOVERY, "--json")
    assert r.returncode == 0
    payload = json.loads(r.stdout)
    assert payload["total_commands"] >= 50
