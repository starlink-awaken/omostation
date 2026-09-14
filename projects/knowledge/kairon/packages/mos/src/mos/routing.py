"""Intent routing for MOS recall (aligned with memory-os.yaml)."""

from __future__ import annotations

import re
from collections.abc import Iterable

# Backend port names used by MemoryOS
BACKEND_KOS = "kos"
BACKEND_GBRAIN = "gbrain"
BACKEND_GBRAIN_FACTS = "gbrain_facts"
BACKEND_CARDS = "cards"
BACKEND_CODE = "codebase_memory"
BACKEND_GOV = "governance_omo"
BACKEND_MEM0 = "mem0"
BACKEND_TEMPORAL = "temporal"
BACKEND_NEO4J = "neo4j"
# Alias used in memory-os.yaml intent routes (graphiti production path → Neo4j FACT)
BACKEND_GRAPHITI = "neo4j"

INTENT_ROUTES: dict[str, list[str]] = {
    "file_note": [BACKEND_KOS],
    "preference_self": [BACKEND_GBRAIN_FACTS, BACKEND_GBRAIN, BACKEND_MEM0],
    "entity_relation": [BACKEND_NEO4J, BACKEND_GBRAIN, BACKEND_TEMPORAL],
    "temporal_fact": [BACKEND_NEO4J, BACKEND_TEMPORAL, BACKEND_GBRAIN],
    "code_structure": [BACKEND_CODE],
    "task_debt": [BACKEND_GOV],
    "card_ops": [BACKEND_CARDS, BACKEND_KOS],
    "general": [BACKEND_KOS, BACKEND_GBRAIN, BACKEND_NEO4J, BACKEND_TEMPORAL],
}

_CODE_RE = re.compile(
    r"\b(caller|callee|function|def |class |import |call graph|谁调用|调用了|函数)\b",
    re.I,
)
_PREF_RE = re.compile(r"\b(prefer|preference|过敏|素食|喜欢|不要|记住我|my preference)\b", re.I)
_ENTITY_RE = re.compile(r"\b(relation|related to|works at|invest(?:ed|or|ment|s)?|关系|谁投资)\b", re.I)
_TASK_RE = re.compile(r"\b(task|debt|todo|任务|债务|开放任务)\b", re.I)
_CARD_RE = re.compile(r"\b(card|知识卡片|卡片)\b", re.I)
_FILE_RE = re.compile(r"\b(ADR|文档|笔记|vault|readme|哪个文件|which (file|doc))\b", re.I)
# Note: avoid \b for CJK tokens (Python word-boundary is ASCII-oriented)
_TEMPORAL_RE = re.compile(
    r"(valid(?:_from|_to)?|expired|as[- ]of|until|effective|时效|有效期|何时生效|过期|before \d{4}|after \d{4})",
    re.I,
)


def classify_intent(query: str, explicit: str | None = None) -> str:
    if explicit and explicit in INTENT_ROUTES:
        return explicit
    q = query or ""
    if _CODE_RE.search(q):
        return "code_structure"
    if _TASK_RE.search(q):
        return "task_debt"
    if _TEMPORAL_RE.search(q):
        return "temporal_fact"
    if _PREF_RE.search(q):
        return "preference_self"
    if _ENTITY_RE.search(q):
        return "entity_relation"
    if _CARD_RE.search(q):
        return "card_ops"
    if _FILE_RE.search(q):
        return "file_note"
    return "general"


def backends_for_intent(intent: str) -> list[str]:
    return list(INTENT_ROUTES.get(intent, INTENT_ROUTES["general"]))


def rrf_fuse(
    ranked_lists: Iterable[list[dict]],
    *,
    k: int = 60,
    limit: int = 20,
) -> list[dict]:
    """Reciprocal rank fusion over backend hit lists."""
    scores: dict[str, float] = {}
    payload: dict[str, dict] = {}
    for hits in ranked_lists:
        for rank, hit in enumerate(hits):
            key = str(hit.get("id") or hit.get("uri") or hit.get("path") or hit.get("title") or id(hit))
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            # Prefer first-seen payload, merge backend tags
            if key not in payload:
                payload[key] = dict(hit)
                payload[key]["backends"] = [hit.get("backend")]
            else:
                b = hit.get("backend")
                if b and b not in payload[key].setdefault("backends", []):
                    payload[key]["backends"].append(b)
    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    out: list[dict] = []
    for key, score in ordered[:limit]:
        item = dict(payload[key])
        item["rrf_score"] = score
        out.append(item)
    return out
