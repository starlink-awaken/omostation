"""架构健康度周报：检查器失败/文件缺席不得折叠成「0」。

缺陷（2026-11-10 实测）：
1. `dim_anticorrosion` 调的是 `meta-doctor.py --workspace . --json`，而 meta-doctor
   **没有 `--json`**（只有 --workspace/--reference-root/--refs-only）⇒ 每次都 argparse
   报错 ⇒ `_run_check` 折叠成 default ⇒ `drift=0`。实测周报长期印 `drift=0`。
   而且它读的字段 `drift_count` 在 meta-doctor 的输出里**根本不存在**（真值在
   `summary` 里），就算命令跑通也仍是 0 —— 双重坏。
2. `dim_operations` 在 system.yaml 缺席时返回 `{online:0,total:0,error:...}`，而
   `to_markdown` 只读 online/total/ratio ⇒ 印成 `0/0 在线 (0%)`，读起来像
   「所有 daemon 都挂了」，实际是「文件没物化」。system.yaml 是 gitignored 的，
   任何干净检出都拿不到它。

判据自证：把 `dim_anticorrosion` 的默认值改回 `{}`、或把 `--json` 加回去，
对应用例当场红。
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/arch-health-meter.py"


def _load(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "arch_health_meter_under_test",
        SCRIPT,
        loader=importlib.machinery.SourceFileLoader("arch_health_meter_under_test", str(SCRIPT)),
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_meta_doctor_invocation_has_no_json_flag(monkeypatch):
    """meta-doctor.py 没有 --json；多传会让它 argparse 报错、整维恒 0。"""
    module = _load(monkeypatch)
    seen = []

    def fake(cmd, default=None):
        seen.append(cmd)
        return {"summary": {}}

    module._run_check = fake
    module.dim_anticorrosion()

    assert seen, "dim_anticorrosion 未调用任何子检查"
    assert "--json" not in seen[0], f"meta-doctor 不接受 --json: {seen[0]}"


def test_anticorrosion_failure_is_unavailable_not_zero(monkeypatch):
    module = _load(monkeypatch)
    module._run_check = lambda cmd, default=None: default  # 子检查全失败

    data = module.dim_anticorrosion()

    assert data["meta_doctor_available"] is False
    assert data["meta_doctor_drift_count"] is None, "检查器失败被折叠成 0 —— 假绿"
    assert data["meta_doctor_error"]


def test_anticorrosion_reads_summary_fields(monkeypatch):
    module = _load(monkeypatch)

    def fake(cmd, default=None):
        if "meta-doctor" in cmd:
            return {"summary": {"stale_beats": 2, "absent_beats": 4, "dead_refs": 1}}
        return "PASS"

    module._run_check = fake
    data = module.dim_anticorrosion()
    assert data["meta_doctor_available"] is True
    assert data["meta_doctor_drift_count"]


def test_markdown_surfaces_absent_operations_instead_of_zero(monkeypatch):
    module = _load(monkeypatch)
    report = {
        "scene": {"total": 0, "by_lifecycle": {}},
        "architecture": {"sfop_ok": False, "chain_ok": True},
        "evolution": {"done": 1, "total": 2, "ratio": 0.5, "done_30d": 0},
        "operations": {"online": 0, "total": 0, "ratio": 0.0,
                       "error": "system.yaml missing"},
        "anti_corrosion": {"meta_doctor_drift_count": 0,
                           "meta_doctor_available": True,
                           "ssot_guardian_clean": True},
        "perception": {"skill_count": 0, "workflow_count": 0, "silent_workflows": 0},
    }

    md = module.to_markdown(report)

    assert "system.yaml missing" in md, "缺席被渲染成 0/0 在线 —— 读起来像全部宕机"
    assert "0/0 在线" not in md


def test_markdown_surfaces_unavailable_anticorrosion(monkeypatch):
    module = _load(monkeypatch)
    report = {
        "scene": {"total": 0, "by_lifecycle": {}},
        "architecture": {"sfop_ok": True, "chain_ok": True},
        "evolution": {"done": 1, "total": 2, "ratio": 0.5, "done_30d": 0},
        "operations": {"online": 0, "total": 0, "ratio": 0.0, "error": "system.yaml missing"},
        "anti_corrosion": {"meta_doctor_drift_count": None,
                           "meta_doctor_available": False,
                           "meta_doctor_error": "meta-doctor 未产出 JSON（命令失败或超时）",
                           "ssot_guardian_clean": False},
        "perception": {"skill_count": 0, "workflow_count": 0, "silent_workflows": 0},
    }

    md = module.to_markdown(report)

    assert "不可用" in md
    assert "drift=None" not in md


def _report(**overrides):
    base = {
        "scene": {"total": 0, "by_lifecycle": {}},
        "architecture": {"sfop_ok": True, "chain_ok": True},
        "evolution": {"done": 1, "total": 2, "ratio": 0.5, "done_30d": 0},
        "operations": {"online": 0, "total": 0, "ratio": 0.0, "error": None},
        "anti_corrosion": {"meta_doctor_drift_count": 0,
                           "meta_doctor_available": True,
                           "ssot_guardian_clean": True},
        "perception": {"skill_count": 0, "workflow_count": 0, "silent_workflows": 0},
    }
    base.update(overrides)
    return base


def test_markdown_surfaces_absent_scene_cards(monkeypatch):
    module = _load(monkeypatch)
    report = _report(scene={"total": 0, "by_lifecycle": {},
                            "error": "docs/scene-cards/ missing"})

    md = module.to_markdown(report)

    assert "docs/scene-cards/ missing" in md, "缺席被渲染成 0 cards —— 读起来像一张都没有"
    assert "0 cards" not in md


def test_markdown_surfaces_missing_ledger(monkeypatch):
    module = _load(monkeypatch)
    report = _report(evolution={"total": 0, "done": 0, "ratio": 0.0,
                                "done_30d": 0, "error": "ledger missing"})

    md = module.to_markdown(report)

    assert "ledger missing" in md, "台账缺席被渲染成 0/0 —— 读起来像没有 BET"
    assert "0/0 bet done" not in md
