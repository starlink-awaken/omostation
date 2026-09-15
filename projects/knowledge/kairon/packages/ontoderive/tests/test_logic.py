from pathlib import Path

"""逻辑蕴含图测试"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false


from ontoderive.theories.logic import EntailmentGraph, build_from_project


def test_empty_graph():
    g = EntailmentGraph()
    stats = g.stats()
    assert stats["nodes"] == 0
    assert stats["edges"] == 0


def test_add_nodes():
    g = EntailmentGraph()
    g.add_node("D-F1", "fact")
    g.add_node("INF-L1", "inference")
    g.add_edge("D-F1", "INF-L1")
    stats = g.stats()
    assert stats["nodes"] == 2
    assert stats["edges"] == 1


def test_chain_depths():
    g = EntailmentGraph()
    g.add_node("D-F1", "fact")
    g.add_node("D-F2", "fact")
    g.add_node("INF-A", "inference")
    g.add_node("INF-B", "inference")
    g.add_edge("D-F1", "INF-A")
    g.add_edge("D-F2", "INF-A")
    g.add_edge("INF-A", "INF-B")
    depths = g.chain_depths()
    assert depths["max"] >= 2


def test_no_cycles_clean():
    g = EntailmentGraph()
    g.add_node("D-F1", "fact")
    g.add_node("INF-A", "inference")
    g.add_edge("D-F1", "INF-A")
    assert g.detect_cycles() == []


def test_bottlenecks():
    g = EntailmentGraph()
    g.add_node("D-F1", "fact")
    for i in range(5):
        g.add_node(f"INF-{i}", "inference")
        g.add_edge("D-F1", f"INF-{i}")
    bn = g.bottlenecks()
    assert len(bn) >= 1
    assert bn[0]["node"] == "D-F1"


def test_build_from_project():
    proj = str(Path(__file__).parent.parent / "examples" / "z-park")
    g = build_from_project(proj)
    stats = g.stats()
    assert stats["nodes"] >= 2
    assert stats["edges"] >= 1


def test_to_graphml():
    g = EntailmentGraph()
    g.add_node("D-F1", "fact")
    g.add_edge("D-F1", "INF-A")
    xml = g.to_graphml()
    assert "graphml" in xml
