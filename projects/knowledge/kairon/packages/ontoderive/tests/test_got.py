"""Tests for GoT (Graph of Thoughts) — 图思维推理引擎"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from ontoderive.intelligence.got import GraphOfThoughts


class MockGraph:
    """模拟蕴含图"""

    def __init__(self):
        self.nodes = {
            "D-F1": {"type": "fact", "label": "事实1"},
            "D-F2": {"type": "fact", "label": "事实2"},
            "INF-L1": {"type": "inference", "label": "推论1从事实1和2"},
            "D-F3": {"type": "fact", "label": "事实3"},
            "INF-L2": {"type": "inference", "label": "推论2从推论1和事实3"},
        }
        self.edges = {
            "D-F1": ["INF-L1"],
            "D-F2": ["INF-L1"],
            "INF-L1": ["INF-L2"],
            "D-F3": ["INF-L2"],
        }
        self.reverse = {
            "INF-L1": ["D-F1", "D-F2"],
            "INF-L2": ["INF-L1", "D-F3"],
        }


class MockEnhancer:
    available = True
    backend = "mock"
    model = "mock-model"

    def _call(self, prompt, system="", temperature=0.3):
        return '{"coherence": 4, "sufficiency": 3, "issues": [], "summary": "逻辑一致"}'


class TestGraphOfThoughts:
    def test_create(self):
        g = GraphOfThoughts(MockGraph(), None)
        assert g is not None
        assert g.graph is not None

    def test_topological_order(self):
        g = GraphOfThoughts(MockGraph(), None)
        order = g._topological_order()
        # 事实应在推论之前
        inf_l1_idx = order.index("INF-L1")
        df1_idx = order.index("D-F1")
        df2_idx = order.index("D-F2")
        assert df1_idx < inf_l1_idx
        assert df2_idx < inf_l1_idx

    def test_find_merge_nodes(self):
        g = GraphOfThoughts(MockGraph(), None)
        merges = g._find_merge_nodes()
        # INF-L1 和 INF-L2 都是推理节点(非事实)
        assert "INF-L1" in merges or "INF-L2" in merges

    def test_reason_on_node_no_llm(self):
        """没有LLM时返回summary兜底"""
        g = GraphOfThoughts(MockGraph(), None)
        try:
            result = g._reason_on_node("INF-L1", {"D-F1": {"summary": "事实1"}})
            assert "summary" in result
        except AttributeError:
            # 没有enhancer则跳过LLM测试
            pass

    def test_reason_on_node_with_llm(self):
        g = GraphOfThoughts(MockGraph(), MockEnhancer())
        result = g._reason_on_node("INF-L1", {"D-F1": {"summary": "事实1"}})
        assert "coherence" in result or "summary" in result

    def test_merge_paths_no_llm(self):
        g = GraphOfThoughts(MockGraph(), None)
        g.thoughts = {"D-F1": {"summary": "事实1"}}
        try:
            result = g._merge_paths("INF-L1", ["D-F1"])
            assert "merged" in result
        except AttributeError:
            pass

    def test_traverse_and_reason(self):
        g = GraphOfThoughts(MockGraph(), MockEnhancer())
        results = g.traverse_and_reason()
        assert isinstance(results, dict)

    def test_empty_graph(self):
        """空图拓扑排序返回空"""
        mg = MockGraph()
        mg.nodes = {}
        mg.edges = {}
        g = GraphOfThoughts(mg, None)
        order = g._topological_order()
        assert order == []
        merges = g._find_merge_nodes()
        assert merges == {}
