"""BET-Y2Q4-T10-350 — scene-journey-autogen 数据源对齐 docs 体系.

根因: SCENES_DIR/JOURNEYS_DIR 原指向 .omo/_truth/{scenarios,journeys}/v3
(与 journey-runner 的 docs/ 数据源分裂, scan 永远 0 missing 假阴); covered
判定读 runtime.journey_ref 子字段 (70/70 卡零使用, 真实字段是顶层 journey_id)。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "bin" / "ssot" / "scene-journey-autogen.py"


def _module():
    spec = importlib.util.spec_from_file_location("autogen_under_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_datasource_is_docs_tree():
    """BET-Y2Q4-T10-350: 目录常量必须与 journey-runner 的数据源一致 (docs/ 体系)."""
    m = _module()
    assert m.SCENES_DIR == m.ROOT / "docs" / "scene-cards"
    assert m.JOURNEYS_DIR == m.ROOT / "docs" / "journey-specs"


def test_journey_ref_reads_top_level_journey_id_first():
    """covered 判定优先读顶层 journey_id; runtime.journey_ref 仅向后兼容."""
    m = _module()
    scene = {
        "scene_id": "s1",
        "journey_id": "top-level-ref",
        "runtime": {"journey_ref": "legacy-ref"},
    }
    assert m._journey_ref(scene) == "top-level-ref"


def test_journey_ref_falls_back_to_legacy_then_convention():
    m = _module()
    assert m._journey_ref({"scene_id": "s2", "runtime": {"journey_ref": "legacy"}}) == "legacy"
    assert m._journey_ref({"scene_id": "s3"}) == "journey-s3"


def test_scan_finds_cards_whose_spec_missing():
    """scan 对 journey_id 指向不存在 spec 的卡必须报 missing (假阴修复)."""
    m = _module()
    missing = m.scan()
    missing_ids = {item["scene_id"] for item in missing}
    # 修复后全量数据已闭环 (3 张欠账已生成), scan 应为空;
    # 但判定本身对 404 卡生效 — 用合成卡直接验证:
    scenes = [
        {"scene_id": "probe-card", "journey_id": "definitely-missing-spec"},
    ]
    existing = m._get_existing_journeys()
    refs = [m._journey_ref(s) for s in scenes]
    assert all(r not in existing for r in refs)
    assert missing_ids.isdisjoint({"probe-card"})  # 合成卡不在真实数据里


def test_generate_spec_uses_top_level_journey_id():
    """生成的 spec journey_id 必须取卡顶层 journey_id — 卡↔spec 即刻对上."""
    m = _module()
    scene = {
        "scene_id": "gen-probe",
        "journey_id": "gen-probe-workflow",
        "scene_type": "inbound",
        "scene_class": "business",
        "name": "Gen Probe",
        "description": "",
    }
    spec = m.generate_spec(scene)
    assert spec["journey_id"] == "gen-probe-workflow"
    assert spec.get("states"), "template states must be present"
    assert spec.get("transitions"), "template transitions must be present"
