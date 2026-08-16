"""Tests for ReAct (Reasoning + Acting) — 推理行动引擎"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from ontoderive.intelligence.react import ReActEngine


class MockEnhancer:
    available = True
    backend = "mock"
    model = "mock-model"

    def _call(self, prompt, system="", temperature=0.3):
        return "Thought: 开始分析\nAction: FINISH"


class TestReActEngine:
    def test_create(self):
        eng = ReActEngine("/tmp", None)
        assert eng is not None
        assert len(eng.ACTION_SCHEMA) == 7

    def test_action_schema(self):
        eng = ReActEngine("/tmp", None)
        assert "read_fact" in eng.ACTION_SCHEMA
        assert "read_inference" in eng.ACTION_SCHEMA
        assert "check_reference" in eng.ACTION_SCHEMA
        assert "get_confidence" in eng.ACTION_SCHEMA
        assert "trace_chain" in eng.ACTION_SCHEMA
        assert "find_contradictions" in eng.ACTION_SCHEMA
        assert "compute_kqi" in eng.ACTION_SCHEMA

    def test_parse_result_thought_action(self):
        eng = ReActEngine("/tmp", None)
        text = "Thought: 需要验证数据\nAction: read_fact(D-F1)"
        thought, action, arg = eng._parse_result(text)
        assert "需要验证数据" in thought
        assert action == "read_fact"
        assert arg == "D-F1"

    def test_parse_result_finish(self):
        eng = ReActEngine("/tmp", None)
        text = "Thought: 分析完成\nAction: FINISH"
        thought, action, arg = eng._parse_result(text)
        assert action == "FINISH"

    def test_build_action_prompt(self):
        eng = ReActEngine("/tmp", None)
        prompt = eng._build_action_prompt()
        assert "read_fact" in prompt
        assert "Action:" in prompt
        assert "Thought:" in prompt

    def test_exists_missing(self, tmp_path):
        eng = ReActEngine(tmp_path, None)
        assert not eng._exists("NONEXISTENT-ID")

    def test_run_finishes_immediately(self, tmp_project):
        """模拟enhancer返回FINISH时立即结束"""
        eng = ReActEngine(tmp_project, MockEnhancer())
        result = eng.run(max_steps=3)
        assert "verdict" in result
        assert result["steps"] == 1

    def test_parse_result_with_arg(self):
        eng = ReActEngine("/tmp", None)
        text = "Thought: 查一下\nAction: read_inference(INF-L1)"
        thought, action, arg = eng._parse_result(text)
        assert action == "read_inference"
        assert arg == "INF-L1"

    def test_parse_result_multiline(self):
        eng = ReActEngine("/tmp", None)
        text = """Thought: 先检查推论引用
然后继续分析
Action: check_reference(INF-L1)"""
        thought, action, arg = eng._parse_result(text)
        assert action == "check_reference"
        assert arg == "INF-L1"

    def test_execute_read_fact_nonexistent(self, tmp_project):
        eng = ReActEngine(tmp_project, None)
        result = eng._execute("read_fact", "D-F999")
        assert "error" in result

    def test_execute_read_inference_nonexistent(self, tmp_project):
        eng = ReActEngine(tmp_project, None)
        result = eng._execute("read_inference", "INF-L999")
        assert "error" in result

    def test_execute_unknown_action(self, tmp_project):
        eng = ReActEngine(tmp_project, None)
        result = eng._execute("unknown_action", "")
        assert "未知Action" in result["error"]

    def test_execute_check_reference(self, tmp_project):
        eng = ReActEngine(tmp_project, None)
        result = eng._execute("check_reference", "D-F1")
        assert isinstance(result, dict)
