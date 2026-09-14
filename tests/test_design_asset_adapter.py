from __future__ import annotations

from forge import (
    build_design_context,
    build_page_spec,
    choose_design_assets,
    discover_design_assets,
    find_awesome_design_repo,
    render_page_spec,
)


def test_find_awesome_design_repo_returns_live_repo():
    repo = find_awesome_design_repo()
    assert repo.exists()
    assert (repo / "design-md").exists()


def test_discover_design_assets_reads_real_metadata():
    assets = discover_design_assets(find_awesome_design_repo())
    assert len(assets) >= 5
    assert any(asset["brand"] == "Claude" for asset in assets)
    assert any(asset["source_path"].startswith("design-md/") for asset in assets)


def test_choose_design_assets_builds_context_and_prompt():
    assets = choose_design_assets(find_awesome_design_repo(), query="claude", limit=3)
    assert len(assets) >= 1
    selected = assets[0]
    context = build_design_context(selected)
    assert context["brand"] == "Claude"
    assert "prompt" in context
    assert "claude" in context["prompt"].lower() or "Claude" in context["prompt"]


def test_build_page_spec_and_render_page_spec():
    assets = choose_design_assets(find_awesome_design_repo(), query="claude", limit=3)
    assert len(assets) >= 1
    page_spec = build_page_spec(assets[0])
    assert page_spec["brand"] == "Claude"
    assert page_spec["sections"]
    assert any(section["type"] == "hero" for section in page_spec["sections"])
    assert any(section.get("layout") in {"split", "grid", "stacked"} for section in page_spec["sections"])
    assert page_spec["responsive_constraints"]["section_order"]
    html = render_page_spec(page_spec, output_format="html")
    assert "Claude" in html
    assert "<section" in html
    assert "testimonial" in html.lower() or "quote" in html.lower()
