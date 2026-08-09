import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from export_mof_framework import collect_assets, build_manifest, export_framework


def test_collect_assets_finds_mof():
    assets = collect_assets()
    assert any("m3.yaml" in a["name"] for a in assets)
    assert any("constraints.yaml" in a["name"] for a in assets)
    assert any("consumer_index.py" in a["name"] for a in assets)


def test_build_manifest_lists_layers():
    assets = collect_assets()
    manifest = build_manifest(assets)
    assert manifest["layers"]["m3"] >= 1
    assert manifest["layers"]["m2"] >= 1
    assert manifest["total_assets"] == len(assets)


def test_export_framework_writes_pack(tmp_path):
    assets = collect_assets()
    dest = tmp_path / "mof-framework-pack"
    manifest = export_framework(assets, str(dest))
    assert manifest["total_assets"] == len(assets)
    assert (dest / "manifest.yaml").exists()
