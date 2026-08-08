"""ADR-0374 G1: gac-drift indexed-rule detection regression tests.

Locks the behavior of `check_indexed_drift` for SSOT-index rules.
The historical bug: legacy_index rules (id `CR-*-SSOT`) are themselves
the SSOT *index name*, NOT a rule inside the source file. The check
used to fail with "rule ID in source_ref not found" because the literal
string search never matched. The fix recognizes `*-SSOT` suffix and
`legacy_index` check_type as a special case.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
GAC_DRIFT = ROOT / "bin" / "gac" / "gac-drift.py"


def _load_gac_drift():
    spec = importlib.util.spec_from_file_location("gac_drift_test", GAC_DRIFT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gd():
    """Late-bind import so a stale .pyc never shadows the live script.

    gac-drift.py uses a `sys.path.insert` + `import gac_severity` shim at
    top level, so we need to ensure `bin/gac/` is on path before loading.
    """
    import sys
    bin_gac = str(ROOT / "bin" / "gac")
    if bin_gac not in sys.path:
        sys.path.insert(0, bin_gac)
    return _load_gac_drift()


def test_ssot_index_rule_passes_when_file_exists(gd, tmp_path) -> None:
    """G1 happy path: CR-*-SSOT rule + existing source_ref file → 0 drift."""
    fake_ssot = tmp_path / "x1-policies.yaml"
    fake_ssot.write_text(
        "documentation_contract:\n  ssot_role: authoritative\npolicies: []\n",
        encoding="utf-8",
    )
    rule = {
        "id": "CR-X1-POLICIES-SSOT",
        "source_type": "indexed",
        "check_type": "legacy_index",
        "source_ref": f"{fake_ssot}::policies",
    }
    drifts = gd.check_indexed_drift(rule)
    assert drifts == [], f"unexpected drifts: {drifts}"


def test_ssot_index_rule_passes_via_id_suffix(gd, tmp_path) -> None:
    """G1: rule id ending in -SSOT is recognized as SSOT index, no content match needed."""
    fake_ssot = tmp_path / "x2-rules.yaml"
    fake_ssot.write_text("# unrelated content with no rule_id\n", encoding="utf-8")
    rule = {
        "id": "CR-X2-FRESHNESS-SSOT",  # ends with -SSOT
        "source_type": "indexed",
        "check_type": "freshness",  # not legacy_index
        "source_ref": f"{fake_ssot}::rules",
    }
    drifts = gd.check_indexed_drift(rule)
    assert drifts == [], f"unexpected drifts: {drifts}"


def test_non_ssot_rule_still_fails_when_id_missing_from_content(gd, tmp_path) -> None:
    """G1: regular rule whose id is NOT in source content still fails (regression guard)."""
    fake_ssot = tmp_path / "regular.yaml"
    fake_ssot.write_text("totally unrelated content\n", encoding="utf-8")
    rule = {
        "id": "CR-X2-NORMAL-RULE",
        "source_type": "indexed",
        "check_type": "freshness",
        "source_ref": f"{fake_ssot}::rules",
    }
    drifts = gd.check_indexed_drift(rule)
    assert any("未找到" in d for d in drifts), (
        f"expected drift, got: {drifts}"
    )


def test_indexed_rule_fails_when_file_missing(gd) -> None:
    """G1: source_ref path does not exist → drift (regardless of index type)."""
    rule = {
        "id": "CR-X1-POLICIES-SSOT",
        "source_type": "indexed",
        "check_type": "legacy_index",
        "source_ref": "/this/path/does/not/exist.yaml::policies",
    }
    drifts = gd.check_indexed_drift(rule)
    assert any("文件不存在" in d for d in drifts), f"expected missing-file drift, got: {drifts}"


def test_non_indexed_rule_skips_indexed_check(gd) -> None:
    """G1: rule with source_type != 'indexed' is handled elsewhere; the indexed
    check must short-circuit and not emit false-positive drift."""
    rule = {
        "id": "CR-ANY-NATIVE-RULE",
        "source_type": "native",
        "check_type": "freshness",
        "source_ref": "/nope.yaml",
    }
    drifts = gd.check_indexed_drift(rule)
    assert drifts == []


def test_derived_plane_target_skipped(gd) -> None:
    """ADR-0377 G11: runtime-derived target (gitignored _derived) 存在性取决于
    本地生成, 静态 target-exists 检查必须跳过 — fresh checkout 必然缺失也不报 drift."""
    rule = {
        "id": "CR-M4-HEALTH-SCORE",
        "target": "projects/ecos/.omo/_derived/m4-health.json",
        "check_type": "freshness",
    }
    assert gd.check_target_exists(rule) == [], "derived file target must not flag drift"


def test_derived_plane_dir_target_skipped(gd) -> None:
    """G11: _derived/ 目录 target 同样跳过 (CR-M4-DERIVED-PLANE-AUDIT)."""
    rule = {
        "id": "CR-M4-DERIVED-PLANE-AUDIT",
        "target": "projects/ecos/.omo/_derived/",
        "check_type": "ssot_pointer",
    }
    assert gd.check_target_exists(rule) == [], "derived dir target must not flag drift"


def test_regular_missing_target_still_flags(gd) -> None:
    """G11 回归: 非派生面 target 缺失仍必须报 drift (排除逻辑不伤主路径)."""
    rule = {
        "id": "CR-ANY-REAL-TARGET",
        "target": "projects/does-not-exist-xyz/audit.json",
        "check_type": "freshness",
    }
    drifts = gd.check_target_exists(rule)
    assert any("target 文件不存在" in d for d in drifts), f"expected drift, got: {drifts}"
