"""Learning Loop — extracts reusable patterns from research results.

After each research execution, the learner:
1. Extracts the paradigm program that was used
2. Records which transitions succeeded/failed
3. Builds a knowledge base of effective patterns per domain
4. Suggests paradigm refinements for future similar questions
"""

from __future__ import annotations

import contextlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ResearchTrace:
    """A recorded research execution trace for learning."""

    query: str
    paradigm_name: str
    operations: list[str]
    transitions_fired: list[str] = field(default_factory=list)
    transitions_failed: list[str] = field(default_factory=list)
    source_count: int = 0
    entity_count: int = 0
    quality_score: int = 0
    iterations: int = 1
    completed: bool = False
    timestamp: str = ""
    domain: str = ""


class ParadigmLearner:
    """Learns from research traces to improve paradigm compilation."""

    def __init__(self, trace_dir: str = "~/sophia/traces"):
        self.trace_dir = Path(trace_dir).expanduser()
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self._cache: list[dict] | None = None
        self._cache_mtime: float = 0.0

    def _load_traces(self, limit: int = 500) -> list[dict]:
        """Load recent traces from disk with mtime-based caching."""
        files = sorted(self.trace_dir.glob("trace_*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        newest = files[0].stat().st_mtime if files else 0
        if self._cache is not None and newest <= self._cache_mtime:
            return self._cache[:limit]
        traces = []
        for f in files[:limit]:
            with contextlib.suppress(Exception):
                traces.append(json.loads(f.read_text()))
        self._cache = traces
        self._cache_mtime = newest
        return traces

    def record(self, trace: ResearchTrace) -> None:
        """Record a research trace for learning."""
        trace.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        entry = {
            "query": trace.query[:200],
            "paradigm": trace.paradigm_name,
            "ops": trace.operations,
            "fired": trace.transitions_fired,
            "failed": trace.transitions_failed,
            "sources": trace.source_count,
            "entities": trace.entity_count,
            "quality": trace.quality_score,
            "iterations": trace.iterations,
            "completed": trace.completed,
            "ts": trace.timestamp,
        }
        import hashlib
        import uuid

        ts_us = int(time.time() * 1_000_000)
        query_hash = hashlib.sha256(trace.query.encode()).hexdigest()[:16]
        unique_id = str(uuid.uuid4())[:8]
        path = self.trace_dir / f"trace_{ts_us}_{query_hash}_{unique_id}.json"
        with open(path, "w") as f:
            json.dump(entry, f, indent=2)
        self._cache = None  # Invalidate cache

    def get_effective_ops(self, domain_hint: str = "", min_samples: int = 3) -> dict[str, float]:
        """Analyze traces to find which operations correlate with high quality scores.

        Returns {operation_name: effectiveness_score}
        """
        traces = self._load_traces(200)
        op_scores: dict[str, list[int]] = {}
        for data in traces:
            if domain_hint and domain_hint.lower() not in data.get("query", "").lower():
                continue
            score = data.get("quality", 50)
            for op in data.get("ops", []):
                if op not in op_scores:
                    op_scores[op] = []
                op_scores[op].append(score)

        return {op: sum(scores) / len(scores) for op, scores in op_scores.items() if len(scores) >= min_samples}

    def suggest_ops(self, domain_hint: str = "", top_k: int = 6) -> list[str]:
        """Suggest effective operations based on past traces, optionally filtered by domain."""
        effective = self.get_effective_ops(domain_hint=domain_hint)
        ranked = sorted(effective.items(), key=lambda x: -x[1])
        return [op for op, _ in ranked[:top_k]]

    def find_similar_traces(self, query: str, top_k: int = 10) -> list[dict]:
        """Find past traces with similar queries for domain-specific learning."""
        traces = self._load_traces(500)
        q_words = set(query.lower().split())
        scored = []
        for t in traces:
            t_words = set(t.get("query", "").lower().split())
            overlap = len(q_words & t_words)
            if overlap > 0:
                scored.append((overlap, t))
        scored.sort(key=lambda x: -x[0])
        return [t for _, t in scored[:top_k]]

    def suggest_paradigm(self, query: str) -> dict:
        """Suggest an optimized paradigm based on similar past queries.

        Returns a dict with:
        - recommended_ops: best operations from similar high-quality traces
        - confidence: average quality score of supporting traces
        - sample_count: number of similar traces found
        - top_traces: best-matching past queries for reference
        """
        similar = self.find_similar_traces(query)
        if not similar:
            return {"recommended_ops": [], "confidence": 0, "sample_count": 0, "top_traces": []}

        high_quality = [t for t in similar if t.get("quality", 0) >= 60]
        if not high_quality:
            high_quality = similar

        op_scores: dict[str, list[int]] = {}
        for t in high_quality:
            for op in t.get("ops", []):
                if op not in op_scores:
                    op_scores[op] = []
                op_scores[op].append(t.get("quality", 50))

        ranked = sorted(op_scores.items(), key=lambda x: -sum(x[1]) / len(x[1]))
        return {
            "recommended_ops": [op for op, _ in ranked],
            "confidence": sum(t.get("quality", 0) for t in high_quality) / len(high_quality),
            "sample_count": len(high_quality),
            "top_traces": [
                {"query": t["query"][:100], "quality": t["quality"], "ops": t["ops"]} for t in high_quality[:5]
            ],
        }

    def get_patterns(self) -> list[dict]:
        """Extract reusable paradigm patterns from accumulated traces."""
        traces = self._load_traces(500)
        transition_stats: dict[str, int] = {}
        for data in traces:
            for t in data.get("fired", []):
                transition_stats[t] = transition_stats.get(t, 0) + 1
            for t in data.get("failed", []):
                key = f"FAIL:{t}"
                transition_stats[key] = transition_stats.get(key, 0) + 1

        patterns = []
        for trans, count in sorted(transition_stats.items(), key=lambda x: -x[1])[:20]:
            is_fail = trans.startswith("FAIL:")
            patterns.append(
                {
                    "transition": trans.replace("FAIL:", ""),
                    "count": count,
                    "reliable": not is_fail and count > 10,
                }
            )
        return patterns
