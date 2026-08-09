import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from onto_ekg_bootstrap import extract_candidate_concepts, build_bootstrap_report


def test_extract_from_frontmatter():
    docs = [
        {"path": "docs/ARCHITECTURE.md",
         "content": "---\nstatus: active\nsurface: L3\ndimension: X1\n---\n# 架构\n分层契约 layer-contract.yaml 是权威"},
    ]
    concepts = extract_candidate_concepts(docs)
    assert any("layer-contract" in c["name"] or "分层契约" in c["name"] for c in concepts)


def test_extract_dedup():
    docs = [
        {"path": "a.md", "content": "## 分层契约\nlayer-contract.yaml 权威"},
        {"path": "b.md", "content": "## 分层契约\nlayer-contract.yaml 再次提及"},
    ]
    concepts = extract_candidate_concepts(docs)
    names = [c["name"] for c in concepts]
    assert names.count("layer-contract") == 1


def test_build_report():
    concepts = [{"name": "layer-contract", "count": 5, "source": "docs/ARCHITECTURE.md",
                 "dimension": "X1", "surface": "L3"}]
    report = build_bootstrap_report(concepts)
    assert "layer-contract" in report
    assert "5" in report
