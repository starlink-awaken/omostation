from __future__ import annotations

from forge import build_design_context, choose_design_assets, discover_design_assets, find_awesome_design_repo


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
