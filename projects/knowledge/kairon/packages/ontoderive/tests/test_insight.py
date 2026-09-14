from pathlib import Path

"""Tests for Insight, InsightCache, and InsightEngine"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import json

from ontoderive.intelligence.insight import Insight, InsightCache, InsightEngine


class TestInsight:
    """Test the Insight dataclass — data structure and serialization"""

    def test_defaults(self):
        ins = Insight(type="derivation", content="测试洞察", confidence=0.85)
        assert ins.type == "derivation"
        assert ins.content == "测试洞察"
        assert ins.confidence == 0.85
        assert ins.method == "llm"
        assert ins.cites == []
        assert ins.metadata == {}

    def test_with_model(self):
        ins = Insight(type="quality", content="质量洞察", confidence=0.9, method="llm", model="test-model")
        assert ins.type == "quality"
        assert ins.model == "test-model"

    def test_to_dict(self):
        """to_dict() converts dataclass to plain dict"""
        ins = Insight(
            type="derivation",
            content="测试洞察",
            confidence=0.85,
            cites=["D-F1"],
            method="rule",
            model="test-model",
            timestamp="2025-01-01T00:00:00",
            metadata={"source": "test"},
        )
        d = ins.to_dict()
        assert d["type"] == "derivation"
        assert d["content"] == "测试洞察"
        assert d["confidence"] == 0.85
        assert d["cites"] == ["D-F1"]
        assert d["method"] == "rule"
        assert d["model"] == "test-model"
        assert d["timestamp"] == "2025-01-01T00:00:00"
        assert d["metadata"] == {"source": "test"}

    def test_to_markdown_with_cites(self):
        """to_markdown() renders cites and confidence percentage"""
        ins = Insight(
            type="derivation",
            content="发现的连接关系",
            confidence=0.85,
            cites=["D-F1", "INF-L2"],
        )
        md = ins.to_markdown()
        assert "[derivation]" in md
        assert "发现的连接关系" in md
        assert "85%" in md
        assert "D-F1, INF-L2" in md
        assert "引用:" in md

    def test_to_markdown_no_cites(self):
        """to_markdown() falls back to '无' when cites is empty"""
        ins = Insight(type="recommendation", content="推荐使用工具X", confidence=0.50)
        md = ins.to_markdown()
        assert "[recommendation]" in md
        assert "推荐使用工具X" in md
        assert "50%" in md
        assert "无" in md
        assert "引用:" in md

    def test_to_markdown_zero_confidence(self):
        """to_markdown() handles 0% confidence edge case"""
        ins = Insight(type="contradiction", content="无矛盾", confidence=0.0)
        md = ins.to_markdown()
        assert "0%" in md


class TestInsightCache:
    """Test InsightCache — caching, key generation, persistence"""

    def test_default_cache_dir(self, tmp_path):
        """Default cache_dir falls back to _derivation_logs"""
        orig_cwd = Path.cwd()
        import os

        os.chdir(tmp_path)
        try:
            cache = InsightCache()
            assert cache.cache_dir.name == "_derivation_logs"
            assert cache.cache_dir.exists()
        finally:
            os.chdir(orig_cwd)

    def test_custom_cache_dir(self, tmp_path):
        """Custom cache_dir is used instead of default"""
        custom = tmp_path / "my_cache"
        cache = InsightCache(cache_dir=str(custom))
        assert cache.cache_dir == custom
        assert cache.cache_dir.exists()

    def test_cache_init_with_path_object(self, tmp_path):
        """cache_dir can be a pathlib.Path"""
        custom = tmp_path / "path_cache"
        cache = InsightCache(cache_dir=custom)
        assert cache.cache_dir == custom
        assert cache.cache_dir.exists()

    def test_key_format(self, tmp_project):
        """_key returns category prefix + 12 hex chars suffix"""
        cache = InsightCache()
        key = cache._key(str(tmp_project), "derive")
        assert key.startswith("derive-")
        # "derive-" (7) + 12 hex chars = 19 total
        assert len(key) == 19
        suffix = key[7:]  # part after "derive-"
        assert len(suffix) == 12
        assert all(c in "0123456789abcdef" for c in suffix)

    def test_key_deterministic(self, tmp_project):
        """Same project + category always yields same key"""
        cache = InsightCache()
        key1 = cache._key(str(tmp_project), "derive")
        key2 = cache._key(str(tmp_project), "derive")
        assert key1 == key2

    def test_key_different_categories(self, tmp_project):
        """Different categories produce different keys"""
        cache = InsightCache()
        k_derive = cache._key(str(tmp_project), "derive")
        k_quality = cache._key(str(tmp_project), "quality")
        assert k_derive != k_quality

    def test_key_no_md_files(self, tmp_path):
        """Empty project still produces a valid key using MD5 of empty string"""
        cache = InsightCache()
        key = cache._key(str(tmp_path), "derive")
        assert key == "derive-d41d8cd98f00"

    def test_get_miss(self, tmp_project):
        """get() returns None when no cache file exists"""
        cache = InsightCache(cache_dir="/tmp/nonexistent-cache-dir-for-test")
        result = cache.get(str(tmp_project), "derive")
        assert result is None

    def test_get_corrupted_file(self, tmp_project, tmp_path):
        """Corrupted cache JSON returns None gracefully"""
        cache = InsightCache(cache_dir=str(tmp_path / "corrupt"))
        key = cache._key(str(tmp_project), "derive")
        cache_file = cache.cache_dir / f"insight-{key}.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text("not valid json")
        assert cache.get(str(tmp_project), "derive") is None

    def test_get_corrupted_file_missing_insights_key(self, tmp_project, tmp_path):
        """Valid JSON without 'insights' key returns [] (empty list)"""
        cache = InsightCache(cache_dir=str(tmp_path / "no-insights"))
        key = cache._key(str(tmp_project), "derive")
        cache_file = cache.cache_dir / f"insight-{key}.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps({"cached_at": "2025-01-01"}))
        # get() returns [] since data.get("insights", []) defaults to []
        result = cache.get(str(tmp_project), "derive")
        assert result == []

    def test_set_and_get_roundtrip(self, tmp_project, tmp_path):
        """Round-trip: set insights, then get them back matches perfectly"""
        cache_dir = tmp_path / "roundtrip"
        cache = InsightCache(cache_dir=str(cache_dir))

        insights = [
            Insight(type="derivation", content="第一条洞察", confidence=0.85, cites=["D-F1"]),
            Insight(type="derivation", content="第二条洞察", confidence=0.65, cites=["INF-L1"]),
        ]
        cache.set(str(tmp_project), "derive", insights)

        loaded = cache.get(str(tmp_project), "derive")
        assert loaded is not None
        assert len(loaded) == 2
        assert loaded[0].content == "第一条洞察"
        assert loaded[0].confidence == 0.85
        assert loaded[0].cites == ["D-F1"]
        assert loaded[0].type == "derivation"
        assert loaded[1].content == "第二条洞察"

    def test_set_and_get_with_metadata(self, tmp_project, tmp_path):
        """Cached insights preserve metadata field"""
        cache_dir = tmp_path / "metadata-test"
        cache = InsightCache(cache_dir=str(cache_dir))

        insights = [
            Insight(type="quality", content="quality check", confidence=0.8, metadata={"score": 7}),
        ]
        cache.set(str(tmp_project), "derive", insights)
        loaded = cache.get(str(tmp_project), "derive")
        assert loaded is not None
        assert loaded[0].metadata == {"score": 7}


class TestInsightEngine:
    """Test InsightEngine — LLM integration, caching, export"""

    # ── Construction & Properties ──

    def test_create(self):
        engine = InsightEngine()
        assert engine is not None

    def test_create_no_enhancer(self):
        """When enhancer=None, fallback to get_enhancer() is attempted"""
        engine = InsightEngine(enhancer=None)
        assert isinstance(engine, InsightEngine)
        # Note: enhancer may be populated by get_enhancer() fallback from llm.py,
        # so we don't assert it's None here

    def test_create_with_mock_enhancer(self, mock_enhancer):
        engine = InsightEngine(enhancer=mock_enhancer)
        assert engine.enhancer is mock_enhancer
        assert engine.available is True

    def test_create_with_cache_dir(self, tmp_path):
        cache_dir = tmp_path / "engine-cache"
        engine = InsightEngine(enhancer=None, cache_dir=str(cache_dir))
        assert engine.cache.cache_dir == cache_dir
        assert engine.cache.cache_dir.exists()

    def test_available_false(self):
        engine = InsightEngine(enhancer=None)
        assert engine.available is False

    def test_available_true(self, mock_enhancer):
        engine = InsightEngine(enhancer=mock_enhancer)
        assert engine.available is True

    def test_available_missing_attr(self):
        """Enhancer without 'available' attribute raises AttributeError"""

        class BareEnhancer:
            def _call(self, prompt, system="", temperature=0.3):
                return "test"

        engine = InsightEngine(enhancer=BareEnhancer())
        import pytest

        with pytest.raises(AttributeError):
            _ = engine.available

    def test_history_starts_empty(self):
        engine = InsightEngine(enhancer=None)
        assert engine._history == []

    # ── _call ──

    def test_call_no_enhancer(self):
        engine = InsightEngine(enhancer=None)
        result = engine._call("some prompt")
        assert result is None

    def test_call_with_mock_enhancer(self, mock_enhancer):
        engine = InsightEngine(enhancer=mock_enhancer)
        result = engine._call("prompt", "system", 0.5)
        assert result == "模拟分析结论：建议增加事实引用"

    # ── derive_insights ──

    def test_derive_insights_no_enhancer(self, tmp_project):
        engine = InsightEngine(enhancer=None)
        insights = engine.derive_insights(
            project_root=tmp_project,
            facts_summary="测试事实",
            inferences_text="测试推论",
        )
        assert insights == []

    def test_derive_insights_with_mock_enhancer(self, tmp_project, mock_enhancer):
        engine = InsightEngine(enhancer=mock_enhancer)
        insights = engine.derive_insights(
            project_root=tmp_project,
            facts_summary="D-F1: 100",
            inferences_text="INF-L1: 测试推论",
        )
        assert isinstance(insights, list)
        # Mock returns "模拟分析结论：建议增加事实引用" which doesn't contain "洞察",
        # so the parser filters it out -> empty list
        assert len(insights) == 0

    def test_derive_insights_cache_hit(self, tmp_project, tmp_path):
        """Cache hit returns cached data before checking enhancer availability"""
        engine = InsightEngine(enhancer=None, cache_dir=str(tmp_path / "cache-hit"))
        cached = [Insight(type="derivation", content="缓存命中", confidence=0.95, cites=["D-F1"])]
        engine.cache.set(str(tmp_project), "derive", cached)

        result = engine.derive_insights(
            project_root=str(tmp_project),
            facts_summary="test",
            inferences_text="test",
        )
        assert len(result) == 1
        assert result[0].content == "缓存命中"
        # Also verifies _history is populated from cache
        assert len(engine._history) == 1
        assert engine._history[0].content == "缓存命中"

    def test_derive_insights_cache_hit_preserves_insights(self, tmp_project, tmp_path):
        """Cache hit returns all cached insights, same objects"""
        engine = InsightEngine(enhancer=None, cache_dir=str(tmp_path / "cache-preserve"))
        cached = [
            Insight(type="derivation", content="A", confidence=0.9),
            Insight(type="derivation", content="B", confidence=0.8),
        ]
        engine.cache.set(str(tmp_project), "derive", cached)
        result = engine.derive_insights(project_root=str(tmp_project), facts_summary="", inferences_text="")
        assert len(result) == 2
        assert result[0].content == "A"
        assert result[1].content == "B"

    # ── judge_quality ──

    def test_judge_quality_no_enhancer(self):
        engine = InsightEngine(enhancer=None)
        result = engine.judge_quality("project", {"test": "data"})
        assert result == {"verdict": "llm_unavailable", "score": None}

    def test_judge_quality_with_mock_enhancer(self, mock_enhancer):
        engine = InsightEngine(enhancer=mock_enhancer)
        result = engine.judge_quality("project", {"key": "value"})
        # Mock returns non-JSON string -> json.loads fails -> regex no match -> fallback
        assert result["verdict"] == "eval_failed"
        assert "raw" in result
        assert result["raw"] == "模拟分析结论：建议增加事实引用"
        # No insight appended when both JSON parse and regex fallback fail
        assert engine._history == []

    # ── check_contradiction ──

    def test_check_contradiction_no_enhancer(self):
        engine = InsightEngine(enhancer=None)
        result = engine.check_contradiction("A", "text a", "B", "text b", ["D-F1"])
        assert result is None

    def test_check_contradiction_with_mock_enhancer(self, mock_enhancer):
        engine = InsightEngine(enhancer=mock_enhancer)
        result = engine.check_contradiction("A", "text a", "B", "text b", ["D-F1"])
        assert result is not None
        assert isinstance(result, Insight)
        assert result.type == "contradiction"
        # Mock returns no "YES" -> is_contradiction=False -> confidence=0.75
        assert result.confidence == 0.75
        assert result.metadata["is_contradiction"] is False
        assert result.cites == ["D-F1"]
        # History is updated
        assert len(engine._history) == 1
        assert engine._history[0] is result

    # ── recommend_tools ──

    def test_recommend_tools_no_enhancer(self):
        engine = InsightEngine(enhancer=None)
        result = engine.recommend_tools("goal", "context", [{"id": "T1", "name": "T", "description": "d"}])
        assert result is None

    def test_recommend_tools_with_mock_enhancer(self, mock_enhancer):
        engine = InsightEngine(enhancer=mock_enhancer)
        tools = [
            {"id": "T1", "name": "Tool1", "description": "First tool"},
            {"id": "T2", "name": "Tool2", "description": "Second tool"},
        ]
        result = engine.recommend_tools("goal", "context", tools)
        # Mock returns a string without commas -> single element list
        assert isinstance(result, list)
        assert len(result) == 1
        assert engine._history[0].type == "recommendation"

    def test_recommend_tools_empty_list(self, mock_enhancer):
        """recommend_tools with empty tools list uses mock response directly"""
        engine = InsightEngine(enhancer=mock_enhancer)
        result = engine.recommend_tools("goal", "context", [])
        assert isinstance(result, list)
        assert len(result) == 1

    def test_recommend_tools_without_description(self, mock_enhancer):
        """Tools without description field don't crash"""
        engine = InsightEngine(enhancer=mock_enhancer)
        tools = [{"id": "T1", "name": "Tool1"}]  # no "description"
        result = engine.recommend_tools("goal", "context", tools)
        assert isinstance(result, list)

    # ── export_insights ──

    def test_export_insights_empty(self):
        engine = InsightEngine(enhancer=None)
        result = engine.export_insights("json")
        data = json.loads(result)
        assert data == []

    def test_export_insights_json(self, mock_enhancer):
        engine = InsightEngine(enhancer=mock_enhancer)
        engine.check_contradiction("A", "text a", "B", "text b", ["D-F1"])
        result = engine.export_insights("json")
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["type"] == "contradiction"
        assert data[0]["confidence"] == 0.75

    def test_export_insights_markdown(self, mock_enhancer):
        engine = InsightEngine(enhancer=mock_enhancer)
        engine.check_contradiction("A", "text a", "B", "text b", ["D-F1"])
        result = engine.export_insights("markdown")
        assert isinstance(result, str)
        assert "[contradiction]" in result
        assert "A vs B" in result

    def test_export_insights_raw_list(self, mock_enhancer):
        """Unknown format returns raw list of dicts"""
        engine = InsightEngine(enhancer=mock_enhancer)
        engine.check_contradiction("A", "text a", "B", "text b", ["D-F1"])
        result = engine.export_insights("unknown")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["type"] == "contradiction"

    def test_export_insights_multiple(self, mock_enhancer):
        """Multiple insights in history are all exported"""
        engine = InsightEngine(enhancer=mock_enhancer)
        # Run two methods that add to history
        engine.check_contradiction("A", "text a", "B", "text b", ["D-F1"])
        engine.recommend_tools("goal", "context", [{"id": "T1", "name": "T", "description": "d"}])
        result = engine.export_insights("json")
        data = json.loads(result)
        assert len(data) == 2
        assert data[0]["type"] == "contradiction"
        assert data[1]["type"] == "recommendation"

    # ── save_insights ──

    def test_save_insights(self, tmp_path, mock_enhancer):
        engine = InsightEngine(enhancer=mock_enhancer)
        engine.check_contradiction("A", "text a", "B", "text b", ["D-F1"])

        output_dir = tmp_path / "insights_out"
        engine.save_insights(str(output_dir))

        assert (output_dir / "insights.json").exists()
        assert (output_dir / "insights.md").exists()

        json_data = json.loads((output_dir / "insights.json").read_text(encoding="utf-8"))
        assert len(json_data) == 1
        assert json_data[0]["type"] == "contradiction"

        md_data = (output_dir / "insights.md").read_text(encoding="utf-8")
        assert "[contradiction]" in md_data

    def test_save_insights_empty(self, tmp_path):
        """Saving when _history is empty produces empty files"""
        engine = InsightEngine(enhancer=None)
        output_dir = tmp_path / "empty_out"
        engine.save_insights(str(output_dir))

        json_data = json.loads((output_dir / "insights.json").read_text(encoding="utf-8"))
        assert json_data == []

        md_data = (output_dir / "insights.md").read_text(encoding="utf-8")
        assert md_data == ""

    def test_save_insights_overwrites(self, tmp_path, mock_enhancer):
        """Repeated save overwrites existing files"""
        engine = InsightEngine(enhancer=mock_enhancer)
        engine.check_contradiction("A", "text a", "B", "text b", ["D-F1"])

        out = tmp_path / "overwrite"
        out.mkdir(parents=True, exist_ok=True)
        (out / "insights.json").write_text("old content")
        (out / "insights.md").write_text("old content")

        engine.save_insights(str(out))
        json_data = json.loads((out / "insights.json").read_text(encoding="utf-8"))
        assert len(json_data) == 1  # not the "old content"

    # ── clear_cache ──

    def test_clear_cache(self, tmp_project, tmp_path):
        cache_dir = tmp_path / "cache-to-clear"
        cache = InsightCache(cache_dir=str(cache_dir))
        cache.set(str(tmp_project), "derive", [Insight(type="derivation", content="test", confidence=0.5)])
        key = cache._key(str(tmp_project), "derive")
        assert (cache_dir / f"insight-{key}.json").exists()

        engine = InsightEngine(enhancer=None, cache_dir=str(cache_dir))
        engine.clear_cache()
        assert not (cache_dir / f"insight-{key}.json").exists()

    def test_clear_cache_empty_dir(self, tmp_path):
        """Clearing empty cache directory doesn't error"""
        cache_dir = tmp_path / "empty"
        cache_dir.mkdir(parents=True, exist_ok=True)
        engine = InsightEngine(enhancer=None, cache_dir=str(cache_dir))
        engine.clear_cache()  # Should not raise

    def test_clear_cache_no_cache_files(self, tmp_path, mock_enhancer):
        """clear_cache with no matching glob files doesn't error"""
        engine = InsightEngine(enhancer=mock_enhancer, cache_dir=str(tmp_path / "no-glob"))
        engine.clear_cache()  # Should not raise

    # ── judge_with_consensus ──

    def test_judge_with_consensus_no_enhancer(self):
        """When enhancer=None, fallback get_enhancer is used; _call returns None -> eval_failed"""
        engine = InsightEngine(enhancer=None)
        result = engine.judge_with_consensus("project", {})
        # The fallback get_enhancer() returns an LLMEnhancer (backend="none"),
        # so available=True but _call returns None -> "eval_failed"
        assert result == {"verdict": "eval_failed", "score": None}

    def test_judge_with_consensus_mock_enhancer_no_scores(self, mock_enhancer):
        """When judge_quality returns no score, consensus returns fallback"""
        engine = InsightEngine(enhancer=mock_enhancer)
        result = engine.judge_with_consensus("project", {})
        assert result["verdict"] == "eval_failed"
        assert result["score"] is None

    def test_judge_with_consensus_default_samples(self, mock_enhancer):
        """When no scores collected, result has no 'samples' key"""
        engine = InsightEngine(enhancer=mock_enhancer)
        result = engine.judge_with_consensus("project", {}, n_samples=3)
        # Mock returns non-JSON; judge_quality returns {"verdict":"eval_failed","raw":"..."}
        # score=None, so scores list stays empty -> returns {"verdict":"eval_failed","score":None}
        assert result["verdict"] == "eval_failed"
        assert result["score"] is None
        assert "samples" not in result

    # ── reflect_and_refine ──

    def test_reflect_and_refine_no_enhancer(self):
        """When enhancer=None, fallback get_enhancer might have available=False -> llm_unavailable"""
        engine = InsightEngine(enhancer=None)
        result = engine.reflect_and_refine("project", {})
        # reflect_and_refine returns the raw judge_quality result (unlike
        # judge_with_consensus which wraps it with "eval_failed" when no scores)
        assert result["verdict"] in ("llm_unavailable", "eval_failed")
        assert result.get("score") is None

    def test_reflect_and_refine_with_mock_enhancer(self, mock_enhancer):
        """When judge_quality returns no score key, reflect returns early"""
        engine = InsightEngine(enhancer=mock_enhancer)
        result = engine.reflect_and_refine("project", {})
        # Mock _call returns non-JSON -> judge_quality returns {"verdict":"eval_failed","raw":"..."}
        # score key not present -> initial.get("score") returns None -> returns initial early
        assert result["verdict"] == "eval_failed"
        assert "raw" in result

    def test_reflect_and_refine_default_max_refinements(self, mock_enhancer):
        """Default max_refinements=2 is accepted; returns early when no score"""
        engine = InsightEngine(enhancer=mock_enhancer)
        result = engine.reflect_and_refine("project", {}, max_refinements=2)
        # mock _call returns non-JSON -> judge_quality returns {"verdict":"eval_failed","raw":"..."}
        # no "score" key -> not initial.get("score") is True -> returns early
        assert result["verdict"] == "eval_failed"
        assert "raw" in result

    # ── end of TestInsightEngine ──
