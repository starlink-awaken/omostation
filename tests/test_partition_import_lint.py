"""partition-map import lint (ADR-0181 Phase 3)."""

from __future__ import annotations


import pytest

from ecos.ssot.tools.partition_import_lint import (
    lint_file,
    lint_tree,
    load_partition_map,
    resolve_zone,
)


@pytest.fixture(scope="module")
def pmap():
    return load_partition_map()


@pytest.fixture(scope="module")
def zones(pmap):
    return pmap["zones"]


def test_partition_map_has_three_zones(pmap):
    assert set(pmap["zones"]) == {"core", "fabric", "ops"}


def test_zone_resolution(zones):
    assert resolve_zone("ecos/l0/ssb/ssb_client.py", zones) == "core"
    assert resolve_zone("ecos/workflow/executor.py", zones) == "fabric"
    assert resolve_zone("ecos/services/core/brief.py", zones) == "ops"
    assert resolve_zone("ecos/ssot/tools/mof_validate.py", zones) == "fabric"
    assert resolve_zone("ecos/ssot/registry/L0-constraints.yaml", zones) == "core"


def test_full_tree_clean():
    """Live ecos tree must satisfy partition rules (baseline after Phase 3)."""
    viols = lint_tree()
    assert viols == [], "\n".join(
        f"{v.rule} {v.path}:{v.line} {v.message}" for v in viols
    )


def test_core_cannot_import_metaos(tmp_path, zones):
    src = tmp_path / "src"
    core = src / "ecos" / "l0"
    core.mkdir(parents=True)
    bad = core / "evil.py"
    bad.write_text("import metaos\n", encoding="utf-8")
    # minimal map via real zones + file under core prefix
    viols = lint_file(bad, src, zones)
    assert any(v.rule in ("CORE-NO-EXTERNAL", "ZONE-FORBID-EXTERNAL") for v in viols)


def test_fabric_top_level_metaos_forbidden(tmp_path, zones):
    src = tmp_path / "src"
    fab = src / "ecos" / "workflow"
    fab.mkdir(parents=True)
    bad = fab / "evil.py"
    bad.write_text("from metaos.core.engine import SEngine\n", encoding="utf-8")
    viols = lint_file(bad, src, zones)
    assert any(v.rule == "FABRIC-LAZY-EXTERNAL" for v in viols)


def test_fabric_lazy_metaos_ok(tmp_path, zones):
    src = tmp_path / "src"
    fab = src / "ecos" / "workflow"
    fab.mkdir(parents=True)
    good = fab / "good.py"
    good.write_text(
        "def execute():\n    from metaos.core.engine import SEngine\n    return SEngine\n",
        encoding="utf-8",
    )
    viols = lint_file(good, src, zones)
    assert not any(v.rule == "FABRIC-LAZY-EXTERNAL" for v in viols)


def test_core_cannot_import_fabric(tmp_path, zones):
    src = tmp_path / "src"
    (src / "ecos" / "l0").mkdir(parents=True)
    (src / "ecos" / "workflow").mkdir(parents=True)
    (src / "ecos" / "workflow" / "__init__.py").write_text("", encoding="utf-8")
    bad = src / "ecos" / "l0" / "evil.py"
    bad.write_text("from ecos.workflow import execute_m1_workflow\n", encoding="utf-8")
    viols = lint_file(bad, src, zones)
    assert any(v.rule == "ZONE-IMPORT-DIR" for v in viols)


def test_cli_entrypoint(monkeypatch):
    from ecos.ssot.tools import partition_import_lint as mod

    code = mod.main([])
    assert code == 0
