---
title: CONTRACTS
type: doc
---

# Minerva Shared Data Contracts

> Single source of truth for all shared interfaces. Every implementor references this document.

## 1. `OpenAICompatibleClient.generate()`

```python
class OpenAICompatibleClient:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 120):
        """base_url: e.g. http://localhost:11434/v1 or https://api.deepseek.com/v1"""

    async def generate(
        self,
        system: str | None,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Send chat completion. Returns raw text response.
        
        Wire protocol: POST {base_url}/chat/completions
        Request body:
          {"model": self.model,
           "messages": [{"role":"system","content":system}|None, {"role":"user","content":prompt}],
           "temperature": temperature,
           "max_tokens": max_tokens}
        Response: JSON → choices[0].message.content → str
        
        Errors: httpx.HTTPError on network/HTTP failures. Caller handles parsing.
        Does NOT support tool calling or streaming (Phase 2).
        """
```

## 2. `ResearchContext` field formats

```python
# Sub-questions: plain list of query strings
ctx.sub_questions = [
    "What is the transformer architecture?",
    "How does attention mechanism work?",
    "When was the transformer first introduced?",
]

# Search results: list of SearchResult dataclass instances
ctx.search_results = [
    SearchResult(
        title="Attention Is All You Need",
        url="https://arxiv.org/abs/1706.03762",
        snippet="The dominant sequence transduction models...",
        source="searxng",
        published_date="2017-06-12",
    )
]

# Entities: list of Entity dataclass instances
ctx.entities = [
    Entity(
        id="uuid",
        type="Concept",
        name="Self-Attention",
        properties={"description": "...", "first_proposed": "2017"},
        confidence="HIGH",
    )
]

# Relations: list of Relation dataclass instances
ctx.relations = [
    Relation(id="uuid", subject_id="entity-1", predicate="ENABLES", object_id="entity-2", confidence="HIGH")
]

# Contradictions: list of dict with source_a, source_b, claim_a, claim_b, resolution
ctx.contradictions = [
    {
        "topic": "Transformer efficiency",
        "source_a": {"url": "...", "claim": "Transformers scale quadratically"},
        "source_b": {"url": "...", "claim": "Linear attention solves scaling"},
        "resolution": "Linear attention variants reduce but don't eliminate scaling issues",
    }
]

# Report: plain markdown string
ctx.report = "# Research Report\n\n## Summary\n..."
ctx.report_path = "~/knowledge/reports/2026-05-09_transformer-architecture.md"
```

## 3. Entity dict shape (from knowledge/store.py)

```python
Entity(
    id="uuid",  # str, unique ID
    type="Concept",  # str: Domain|Organization|Person|Product|Publication|Concept|Metric|Event|Claim|Timeline
    name="Self-Attention",  # str, display name
    aliases=[],  # list[str]
    properties={},  # dict, type-specific
    valid_from=None,  # str|None, ISO-8601
    valid_until=None,  # str|None, ISO-8601, None=still valid
    superseded_by=None,  # str|None, entity ID
    source_ids=[],  # list[str], source document hashes
    confidence="HIGH",  # str: HIGH|MEDIUM|LOW
    recorded_at=None,  # str|None, ISO-8601
    last_verified=None,  # str|None, ISO-8601
)
```

## 4. Search result dict shape

```python
SearchResult(
    title="Attention Is All You Need",  # str, page title
    url="https://arxiv.org/abs/1706.03762",  # str, full URL
    snippet="The dominant...",  # str, short description
    source="searxng",  # str: searxng|metaso|exa|scholar|arxiv|ddg
    full_text=None,  # str|None, extracted full content
    published_date="2017-06-12",  # str|None, ISO date
    rank_score=0.0,  # float, RRF fusion score
)
```

## 5. Error handling conventions

- Network errors: raise `httpx.HTTPError`, caller catches and logs
- LLM parse errors: return empty/fallback result, log warning
- Search backend errors: return empty list `[]`, log error with backend name
- Missing config: raise `ConfigError` at startup, fail fast
- Pipeline stage failure: `QualityGateFailure` exception triggers retry (max 2)
