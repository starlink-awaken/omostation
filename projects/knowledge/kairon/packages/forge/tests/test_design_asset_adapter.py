from __future__ import annotations

from pathlib import Path

import yaml

from forge.design_asset_adapter import (
    build_design_context,
    build_design_prompt,
    choose_design_assets,
    match_assets,
    scan_design_assets,
    write_manifest,
)


def test_scan_design_assets(tmp_path: Path) -> None:
    repo = tmp_path / "awesome-design-md"
    design_file = repo / "design-md" / "stripe" / "DESIGN.md"
    design_file.parent.mkdir(parents=True)
    design_file.write_text(
        "# Stripe\n\n## Product\n\nThis is a premium SaaS landing page with dark-accented navigation.\n"
        "Use colors #635bff and #0f172a.\n",
        encoding="utf-8",
    )

    assets = scan_design_assets(repo)
    assert len(assets) == 1
    asset = assets[0]
    assert asset["brand"] == "stripe"
    assert asset["source_path"] == "design-md/stripe/DESIGN.md"
    assert asset["layer"] == "forge"
    assert asset["access_mode"] == "read-only"
    assert "stripe" in asset["id"]


def test_write_manifest_and_prompt(tmp_path: Path) -> None:
    repo = tmp_path / "awesome-design-md"
    design_file = repo / "design-md" / "stripe" / "DESIGN.md"
    design_file.parent.mkdir(parents=True)
    design_file.write_text("# Stripe\n\n## Dashboard\n\nPalette: #635bff #0f172a\n", encoding="utf-8")

    output_file = tmp_path / "manifest.yaml"
    manifest = write_manifest(repo, output_file)
    assert manifest["source_type"] == "external_design_corpus"
    assert manifest["assets"][0]["brand"] == "stripe"
    assert output_file.exists()
    parsed = yaml.safe_load(output_file.read_text(encoding="utf-8"))
    assert parsed["assets"][0]["title"] == "Stripe"

    context = build_design_context(manifest["assets"][0], "Create a fintech landing page")
    assert context["brand"] == "stripe"
    assert context["layout_pattern"] in {"landing-page", "sidebar-dashboard"}
    assert context["governance"]["control_plane"] == "omostation"

    prompt = build_design_prompt(manifest["assets"][0], "Create a fintech landing page")
    assert "Stripe" in prompt
    assert "Palette tokens" in prompt
    assert "Summary:" in prompt

    matches = match_assets(manifest["assets"], brand="stripe", platform="web")
    assert len(matches) == 1


def test_choose_design_assets_filters_and_builds_prompt(tmp_path: Path) -> None:
    repo = tmp_path / "awesome-design-md"
    design_file = repo / "design-md" / "stripe" / "DESIGN.md"
    design_file.parent.mkdir(parents=True)
    design_file.write_text(
        "# Stripe\n\n## SaaS product dashboard\n\nPremium fintech landing page with dark mode and product cards.\n"
        "Colors: #635bff #0f172a #f8fafc\n",
        encoding="utf-8",
    )

    matches = choose_design_assets(repo, brand="stripe", platform="web", query="dashboard", limit=3)
    assert len(matches) == 1
    assert matches[0]["brand"] == "stripe"
    assert "dashboard" in " ".join(matches[0]["tags"]).lower()

    prompt = build_design_prompt(matches[0], "Build a fintech product page")
    assert "Stripe" in prompt
    assert "fintech product page" in prompt
