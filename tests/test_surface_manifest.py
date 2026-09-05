"""Unit and integration tests for Declarative Card Extension SDK & Manifest Loader (DCE SDK v1)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from cockpit.surface.cards import ActionPanelCard, DataTableCard, MetricGridCard
from cockpit.surface.loader import (
    CardManifest,
    ExtensionManifest,
    ExtensionRegistry,
    ManifestError,
    load_manifest_file,
    manifest_card_to_envelope,
    normalize_domain,
    parse_manifest_dict,
    scan_manifests,
)
from cockpit.surface.protocol import CardType, RefreshMode, SurfaceDomain, SurfaceEnvelope

VALID_MANIFEST_DICT = {
    "schema_version": "surface-manifest/v1",
    "extension_id": "test-ext",
    "domain": "governance",
    "title": "测试扩展",
    "description": "用于测试的扩展卡片清单",
    "refresh_interval_ms": 3000,
    "cards": [
        {
            "id": "card-1",
            "type": "metric_grid",
            "title": "核心指标",
            "static_data": {
                "metrics": [
                    {"label": "健康度", "value": "99.9%", "status": "normal"},
                    {"label": "待处理", "value": 3, "status": "warning"},
                ]
            },
        },
        {
            "id": "card-2",
            "type": "data_table",
            "title": "任务列表",
            "static_data": {
                "columns": [{"key": "name", "label": "任务名称"}, {"key": "state", "label": "状态"}],
                "rows": [{"name": "Task A", "state": "done"}],
            },
        },
        {
            "id": "card-3",
            "type": "action_panel",
            "title": "操作面板",
            "static_data": {
                "actions": [
                    {"id": "btn-1", "label": "执行", "variant": "primary"},
                    {"id": "btn-2", "label": "取消", "variant": "danger"},
                ]
            },
        },
    ],
}


def test_parse_manifest_dict_valid() -> None:
    manifest = parse_manifest_dict(VALID_MANIFEST_DICT)
    assert manifest.extension_id == "test-ext"
    assert manifest.domain == "governance"
    assert manifest.title == "测试扩展"
    assert len(manifest.cards) == 3

    c1 = manifest.cards[0]
    assert c1.id == "card-1"
    assert c1.type == CardType.METRIC_GRID
    assert c1.title == "核心指标"

    c2 = manifest.cards[1]
    assert c2.id == "card-2"
    assert c2.type == CardType.DATA_TABLE

    c3 = manifest.cards[2]
    assert c3.id == "card-3"
    assert c3.type == CardType.ACTION_PANEL


def test_parse_manifest_dict_invalid_schema() -> None:
    bad_data = dict(VALID_MANIFEST_DICT)
    bad_data["schema_version"] = "surface-manifest/v999"
    with pytest.raises(ManifestError, match="Unsupported schema_version"):
        parse_manifest_dict(bad_data)


def test_parse_manifest_dict_missing_fields() -> None:
    bad_data = dict(VALID_MANIFEST_DICT)
    del bad_data["extension_id"]
    with pytest.raises(ManifestError, match="extension_id"):
        parse_manifest_dict(bad_data)

    bad_data2 = dict(VALID_MANIFEST_DICT)
    del bad_data2["cards"]
    with pytest.raises(ManifestError, match="cards"):
        parse_manifest_dict(bad_data2)


def test_parse_manifest_dict_unknown_card_type() -> None:
    bad_data = dict(VALID_MANIFEST_DICT)
    bad_data["cards"] = [{"id": "bad-card", "type": "floating_hologram"}]
    with pytest.raises(ManifestError, match="unsupported type"):
        parse_manifest_dict(bad_data)


def test_load_manifest_file(tmp_path: Path) -> None:
    f = tmp_path / "surface.manifest.yaml"
    f.write_text(yaml.dump(VALID_MANIFEST_DICT), encoding="utf-8")

    manifest = load_manifest_file(f)
    assert manifest.extension_id == "test-ext"
    assert manifest.source_path == f


def test_manifest_card_to_envelope() -> None:
    manifest = parse_manifest_dict(VALID_MANIFEST_DICT)

    # MetricGrid conversion
    env1 = manifest_card_to_envelope(manifest.cards[0], manifest.domain, manifest.extension_id)
    assert isinstance(env1, SurfaceEnvelope)
    assert env1.card_type == CardType.METRIC_GRID
    assert env1.domain == SurfaceDomain.GOVERNANCE
    assert "cells" in env1.payload
    assert len(env1.payload["cells"]) == 2

    # DataTable conversion
    env2 = manifest_card_to_envelope(manifest.cards[1], manifest.domain, manifest.extension_id)
    assert env2.card_type == CardType.DATA_TABLE
    assert len(env2.payload["rows"]) == 1

    # ActionPanel conversion
    env3 = manifest_card_to_envelope(manifest.cards[2], manifest.domain, manifest.extension_id)
    assert env3.card_type == CardType.ACTION_PANEL
    assert len(env3.payload["actions"]) == 2


def test_scan_manifests(tmp_path: Path) -> None:
    # Good manifest
    dir1 = tmp_path / "proj1"
    dir1.mkdir()
    (dir1 / "surface.manifest.yaml").write_text(yaml.dump(VALID_MANIFEST_DICT), encoding="utf-8")

    # Corrupt manifest (circuit breaker should isolate and not crash)
    dir2 = tmp_path / "proj2"
    dir2.mkdir()
    (dir2 / "surface.manifest.yaml").write_text("schema_version: broken!!!", encoding="utf-8")

    results = scan_manifests([tmp_path])
    assert len(results) == 1
    assert results[0].extension_id == "test-ext"


def test_extension_registry() -> None:
    registry = ExtensionRegistry()
    manifest = parse_manifest_dict(VALID_MANIFEST_DICT)
    registry.register(manifest)

    assert registry.get_extension("test-ext") is not None
    assert len(registry.get_all()) == 1

    # Query domain envelopes
    gov_envelopes = registry.get_envelopes_for_domain(SurfaceDomain.GOVERNANCE)
    assert len(gov_envelopes) == 3

    # Query unrelated domain
    compute_envelopes = registry.get_envelopes_for_domain(SurfaceDomain.COMPUTE)
    assert len(compute_envelopes) == 0


def test_family_hub_manifest_validity() -> None:
    # Test our production family-hub manifest
    hub_manifest_path = Path(__file__).resolve().parent.parent.parent / "family-hub" / "surface.manifest.yaml"
    if not hub_manifest_path.exists():
        pytest.skip("family-hub directory not at standard relative path")

    manifest = load_manifest_file(hub_manifest_path)
    assert manifest.extension_id == "family-hub"
    assert len(manifest.cards) >= 3

    envelopes = [
        manifest_card_to_envelope(c, manifest.domain, manifest.extension_id)
        for c in manifest.cards
    ]
    assert len(envelopes) >= 3


@pytest.mark.asyncio
async def test_tui_app_renders_extension_cards() -> None:
    pytest.importorskip("textual")
    from cockpit.tui.app import CardDeck, SovereignCockpitApp

    ExtensionRegistry.default().clear()
    manifest = parse_manifest_dict(VALID_MANIFEST_DICT)
    ExtensionRegistry.default().register(manifest)

    app = SovereignCockpitApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        deck = app.query_one(CardDeck)
        assert len(deck.envelopes) >= 3
        ext_titles = [e.title for e in deck.envelopes]
        assert "核心指标" in ext_titles
        assert "任务列表" in ext_titles
        assert "操作面板" in ext_titles

