import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from onto_merge import build_merges, existing_children, preview, apply_merges


def test_build_merges_skips_existing():
    existing = {"adr", "agent-workflow"}
    merges = build_merges(existing)
    names = [m["child"] for m in merges]
    assert "adr" not in names
    assert "frontmatter" in names
    assert len(merges) == 9


def test_merge_has_m3_parent():
    merges = build_merges(set())
    for m in merges:
        assert m["parent"] in ("DescriptiveElement", "BehavioralElement",
                               "GovernanceElement", "StructuralElement")


def test_preview_lists_count():
    merges = build_merges(set())
    report = preview(merges)
    assert f"{len(merges)} 条待并入" in report


def test_apply_merges_appends():
    ontology = {"m2_ontology": {"generalizations": [{"child": "old", "parent": "x"}]}}
    merges = [{"child": "adr", "parent": "DescriptiveElement", "note": "n"}]
    merged = apply_merges(ontology, merges)
    assert len(merged["m2_ontology"]["generalizations"]) == 2
