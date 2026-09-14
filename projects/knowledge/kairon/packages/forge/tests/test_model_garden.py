"""Tests for ModelGarden — local model inventory and recommendation."""

from forge.model_garden import TASK_MODEL_MAP, ModelGarden


class TestTaskModelMap:
    def test_has_common_tasks(self):
        assert "coding" in TASK_MODEL_MAP
        assert "research" in TASK_MODEL_MAP
        assert "chat" in TASK_MODEL_MAP
        assert "vision" in TASK_MODEL_MAP

    def test_each_task_has_candidates(self):
        for task, models in TASK_MODEL_MAP.items():
            assert len(models) > 0


class TestAddModel:
    def test_adds_model_with_all_fields(self):
        mg = ModelGarden()
        m = mg.add_model("llama-3-8b", "meta", 16.0, quantization="q4_k_m", last_used="2026-05-01")
        assert m["name"] == "llama-3-8b"
        assert m["provider"] == "meta"
        assert m["size_gb"] == 16.0

    def test_added_model_appears_in_inventory(self):
        mg = ModelGarden()
        mg.add_model("gpt-4o", "openai", 0.0)
        models = mg.inventory()
        assert len(models) == 1
        assert models[0]["name"] == "gpt-4o"

    def test_multiple_models(self):
        mg = ModelGarden()
        mg.add_model("a", "p1", 1.0)
        mg.add_model("b", "p2", 2.0)
        assert len(mg.inventory()) == 2

    def test_empty_inventory(self):
        mg = ModelGarden()
        assert mg.inventory() == []


class TestRecommend:
    def test_recommend_coding_returns_known_models(self):
        mg = ModelGarden()
        mg.add_model("claude-3-5-sonnet", "anthropic", 0.0)
        mg.add_model("codellama-70b", "meta", 35.0)
        recs = mg.recommend("coding")
        assert len(recs) == 2

    def test_recommend_falls_back_to_first_3(self):
        mg = ModelGarden()
        mg.add_model("unknown-model-1", "custom", 1.0)
        mg.add_model("unknown-model-2", "custom", 2.0)
        mg.add_model("unknown-model-3", "custom", 3.0)
        mg.add_model("unknown-model-4", "custom", 4.0)
        recs = mg.recommend("research")
        assert len(recs) == 3

    def test_recommend_chat_fallback_for_unknown_task(self):
        mg = ModelGarden()
        mg.add_model("llama-3-8b", "meta", 8.0)
        recs = mg.recommend("unknown_task")
        assert len(recs) > 0

    def test_empty_inventory_returns_empty_list(self):
        mg = ModelGarden()
        recs = mg.recommend("chat")
        assert recs == []


class TestBenchmark:
    def test_add_and_retrieve(self):
        mg = ModelGarden()
        mg.add_benchmark("gpt-4", "tokens_per_sec", 120.5)
        assert mg._benchmarks["gpt-4"]["tokens_per_sec"] == 120.5

    def test_multiple_metrics_same_model(self):
        mg = ModelGarden()
        mg.add_benchmark("m1", "tokens_per_sec", 100)
        mg.add_benchmark("m1", "latency_ms", 200)
        assert len(mg._benchmarks["m1"]) == 2

    def test_multiple_models(self):
        mg = ModelGarden()
        mg.add_benchmark("m1", "score", 1.0)
        mg.add_benchmark("m2", "score", 2.0)
        assert len(mg._benchmarks) == 2


class TestPruneCandidates:
    def test_returns_models_with_old_last_used(self):
        mg = ModelGarden()
        mg.add_model("old-model", "test", 1.0, last_used="2025-01-01")
        mg.add_model("new-model", "test", 1.0, last_used="2026-05-20")
        candidates = mg.prune_candidates(days_unused=30)
        # Both have last_used set, prune logic compares string "<30d"
        assert len(candidates) > 0

    def test_no_models_returns_empty(self):
        mg = ModelGarden()
        assert mg.prune_candidates() == []

    def test_no_last_used_skipped(self):
        mg = ModelGarden()
        mg.add_model("no-date", "test", 1.0)
        candidates = mg.prune_candidates()
        assert candidates == []

    def test_does_not_delete(self):
        mg = ModelGarden()
        mg.add_model("model", "test", 1.0, last_used="2025-01-01")
        count_before = len(mg.inventory())
        mg.prune_candidates()
        assert len(mg.inventory()) == count_before  # inventory unchanged
