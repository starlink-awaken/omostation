"""policy-radar 写面在调用时刻取根, 且产物不再进 git 跟踪 (ADR-0456 B5).

契约: docs/superpowers/specs/2026-10-05-policy-radar-artifacts-state-root-untrack.md
CI 的 governance-check 用显式文件白名单且不覆盖 tests/unit —— 本文件的绿是**本地**证据,
不构成 CI 判定 (AGENTS.md §7)。
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
POLICY_RADAR = ROOT / "bin" / "bc-os" / "policy_radar.py"
PULSE = ROOT / "bin" / "gac" / "convergence-pulse.py"
REPO_ROOT_MODULE = ROOT / "bin" / "lib" / "repo_root.py"
REL_DIR = Path(".omo") / "state" / "policy-radar"


def _load(path: Path, alias: str):
    spec = importlib.util.spec_from_file_location(alias, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def pr():
    """独立模块名加载: 不与其它用例共享 sys.modules 里的 STATE_DIR 覆盖位."""
    return _load(POLICY_RADAR, "t10230_policy_radar")


@pytest.fixture
def rr():
    return _load(REPO_ROOT_MODULE, "t10230_repo_root")


def _no_redirect(monkeypatch: pytest.MonkeyPatch, pr_module) -> None:
    monkeypatch.setattr(pr_module, "STATE_DIR", None)
    monkeypatch.delenv("OMO_POLICY_RADAR_STATE_DIR", raising=False)
    monkeypatch.delenv("OMOSTATION_STATE_ROOT", raising=False)


def test_state_dir_follows_late_declared_state_root(pr, tmp_path, monkeypatch):
    """I1: 声明 profile 后无需 reload 即生效 —— 缺陷形状正是"要 reload 才看见"."""
    _no_redirect(monkeypatch, pr)
    before = pr.state_dir()
    monkeypatch.setenv("OMOSTATION_STATE_ROOT", str(tmp_path))
    after = pr.state_dir()
    assert before != after, "写面被冻在导入时刻"
    assert after == tmp_path / REL_DIR


def test_resolution_priority_override_then_env_then_profile(pr, tmp_path, monkeypatch):
    """I1 优先级: 模块属性覆盖位 → OMO_POLICY_RADAR_STATE_DIR → state 根."""
    _no_redirect(monkeypatch, pr)
    monkeypatch.setattr(pr, "STATE_DIR", tmp_path / "override")
    monkeypatch.setenv("OMO_POLICY_RADAR_STATE_DIR", str(tmp_path / "env"))
    monkeypatch.setenv("OMOSTATION_STATE_ROOT", str(tmp_path / "profile"))
    assert pr.state_dir() == tmp_path / "override"

    monkeypatch.setattr(pr, "STATE_DIR", None)
    assert pr.state_dir() == tmp_path / "env"

    monkeypatch.delenv("OMO_POLICY_RADAR_STATE_DIR")
    assert pr.state_dir() == tmp_path / "profile" / REL_DIR


def test_state_dir_matches_historical_layout_without_profile(pr, rr, monkeypatch):
    """I2: 未声明 profile 时与历史布局逐字节相同 (state_root()==code_root())."""
    _no_redirect(monkeypatch, pr)
    assert rr.state_root() == rr.code_root()
    assert pr.state_dir() == rr.code_root() / REL_DIR


def test_generate_lands_artifacts_in_the_resolved_state_root(pr, tmp_path, monkeypatch):
    """I6 正向落点: 断言产物**出现在** state 根, 而非只断言检出没变脏."""
    _no_redirect(monkeypatch, pr)
    out_root = tmp_path / "profile"
    monkeypatch.setenv("OMOSTATION_STATE_ROOT", str(out_root))
    canned = {"date": "2026-10-05", "items": [], "internal": {}, "is_degraded": False, "degraded_sources": []}
    monkeypatch.setattr(pr, "collect", lambda now=None: canned)
    assert pr.generate() == 0
    assert sorted(p.name for p in (out_root / REL_DIR).iterdir()) == ["brief-20261005.json", "brief-20261005.md"]


def test_reader_seam_prefers_state_root_dir_then_checkout(rr, tmp_path, monkeypatch):
    """I5 读取侧对偶: state 根目录存在则优先, 否则退回检出; 未声明 profile 时即检出."""
    rel = str(REL_DIR)
    checkout = tmp_path / "checkout"
    monkeypatch.delenv("OMOSTATION_STATE_ROOT", raising=False)
    assert rr.state_dir_read(rel, root=checkout) == checkout / rel

    profile = tmp_path / "elsewhere"
    monkeypatch.setenv("OMOSTATION_STATE_ROOT", str(profile))
    assert rr.state_dir_read(rel, root=checkout) == checkout / rel, "state 根无该目录时应退回检出"
    (profile / rel).mkdir(parents=True)
    assert rr.state_dir_read(rel, root=checkout) == profile / rel


def test_convergence_pulse_brief_probe_uses_the_same_seam(tmp_path, monkeypatch):
    """I5: 探针与写者同缝 —— 否则写面收敛会被读成"晨报断更"."""
    pulse = _load(PULSE, "t10230_pulse")
    monkeypatch.delenv("OMOSTATION_STATE_ROOT", raising=False)
    assert pulse._brief_dir() == ROOT / REL_DIR
    monkeypatch.setenv("OMOSTATION_STATE_ROOT", str(tmp_path))
    assert pulse._brief_dir() == ROOT / REL_DIR, "state 根尚无目录, 应仍读得到检出那份"
    (tmp_path / REL_DIR).mkdir(parents=True)
    assert pulse._brief_dir() == tmp_path / REL_DIR


def test_artifacts_are_untracked_and_the_face_is_ignored():
    """I3/I4 边界: 两个目录下的任何路径都不得在跟踪面里, 且摘库面必须被 ignore."""
    tracked = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", ".omo/state/policy-radar", ".omo/state/runtime/policy-radar"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert tracked == [], f"生成态重新进跟踪: {tracked}"
    probe = subprocess.run(
        ["git", "-C", str(ROOT), "check-ignore", "-q", ".omo/state/policy-radar/cache.json"],
        capture_output=True,
        text=True,
    )
    assert probe.returncode == 0, "摘库面未 ignore, 每日新产物会变成 ?? 噪音"


def _violations(text: str) -> list[str]:
    """检测器: 任何把 policy-radar 面钉到 `ROOT`/源码位置上的写法."""
    return [
        line.strip()
        for line in text.splitlines()
        if "policy-radar" in line and ("ROOT" in line or "parents[" in line)
    ]


def test_write_plane_source_scan_fires_on_a_synthetic_violation():
    """扫源码的门禁必须自证 —— 否则"绿"可能只是检测器压根没命中 (AGENTS.md §7)."""
    synthetic = (
        'ROOT = Path(__file__).resolve().parents[2]\n'
        'STATE_DIR = ROOT / ".omo/state/policy-radar"\n'
        'brief = ROOT / ".omo" / "state" / "policy-radar" / name\n'
        'out = Path(__file__).resolve().parents[1] / "policy-radar"\n'
    )
    assert len(_violations(synthetic)) == 3, _violations(synthetic)


@pytest.mark.parametrize("path", [POLICY_RADAR, PULSE], ids=["writer", "reader"])
def test_no_import_time_write_plane_constant(path):
    hits = _violations(path.read_text(encoding="utf-8"))
    assert hits == [], f"{path.name} 把 policy-radar 写面钉回了源码位置: {hits}"
