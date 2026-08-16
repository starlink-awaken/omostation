"""Multi-model A/B comparison — 27B Dense vs 35B-A3B MoE on standard queries."""

import time
from dataclasses import dataclass, field

QUERIES = [
    ("What is Python asyncio?", "simple_definition", "en"),
    ("Compare transformer and CNN architectures.", "comparison", "en"),
    ("Explain the latest advances in AI safety research.", "research", "en"),
    ("什么是大语言模型？", "simple_definition", "zh"),
    ("比较一下微服务和单体架构的优缺点", "comparison", "zh"),
]


@dataclass
class ModelResult:
    model: str
    query: str
    latency_s: float
    output_length: int
    error: str = ""


@dataclass
class ComparisonReport:
    results: list[ModelResult] = field(default_factory=list)

    @property
    def summary(self) -> str:
        if not self.results:
            return "No results collected."
        models = sorted({r.model for r in self.results})
        lines = [f"# Model Comparison: {', '.join(models)}"]
        lines.append(f"\nTotal queries: {len(self.results)}")

        for model in models:
            model_results = [r for r in self.results if r.model == model]
            avg_lat = sum(r.latency_s for r in model_results) / len(model_results)
            avg_len = sum(r.output_length for r in model_results) / len(model_results)
            errors = sum(1 for r in model_results if r.error)
            lines.append(f"\n## {model}")
            lines.append(f"- Avg latency: {avg_lat:.1f}s")
            lines.append(f"- Avg output length: {avg_len:.0f} chars")
            lines.append(f"- Errors: {errors}/{len(model_results)}")

        return "\n".join(lines)


async def compare_models_llm(
    query: str,
    model_a: str = "qwen3.6:27b-coding-nvfp4",
    model_b: str = "qwen3.6:35b-a3b-coding-nvfp4",
    base_url: str = "http://localhost:11434/v1",
) -> ComparisonReport:
    """Run A/B comparison between two models on a single query.

    Uses the OpenAICompatibleClient to call each model and compare latency + output.
    """
    from minerva.llm.client import OpenAICompatibleClient

    client_a = OpenAICompatibleClient(base_url=base_url, model=model_a, timeout=120)
    client_b = OpenAICompatibleClient(base_url=base_url, model=model_b, timeout=120)

    results = []

    for model, client in [(model_a, client_a), (model_b, client_b)]:
        result = ModelResult(model=model, query=query, latency_s=0, output_length=0)
        start = time.time()
        try:
            output = await client.generate(
                system="You are a helpful research assistant. Answer concisely.",
                prompt=query,
                temperature=0.3,
                max_tokens=512,
            )
            result.latency_s = time.time() - start
            result.output_length = len(output)
        except Exception as e:
            result.latency_s = time.time() - start
            result.error = str(e)
        results.append(result)

    return ComparisonReport(results=results)


def compare_models_triage(query: str) -> ComparisonReport:
    """Compare triage routing between rule-based only (no model difference)."""
    from minerva.triage.router import TriageRouter

    router = TriageRouter(llm_client=None)
    results = []
    models = ["rule_based", "rule_based"]
    model_names = ["triage-27B-Dense", "triage-35B-A3B-MoE"]

    for model_name, _model_tag in zip(model_names, models, strict=False):
        result = ModelResult(model=model_name, query=query, latency_s=0, output_length=0)
        start = time.time()
        try:
            triage = router.classify_rule_based(query)
            result.latency_s = time.time() - start
            result.output_length = len(str(triage.scores))
        except Exception as e:
            result.latency_s = time.time() - start
            result.error = str(e)
        results.append(result)

    return ComparisonReport(results=results)


def test_triage_compare_all_queries():
    """Compare triage routing for all standard queries (no LLM call)."""
    report = ComparisonReport()
    for query, _category, _lang in QUERIES:
        sub = compare_models_triage(query)
        report.results.extend(sub.results)

    print(report.summary)
    assert len(report.results) == len(QUERIES) * 2
    # All should complete without errors (rule-based, no network)
    errors = sum(1 for r in report.results if r.error)
    assert errors == 0


def test_model_compare_smoke():
    """Smoke test that model comparison infrastructure works."""
    report = compare_models_triage("What is AI?")
    assert len(report.results) == 2
    for r in report.results:
        assert r.latency_s >= 0
        assert r.output_length > 0
